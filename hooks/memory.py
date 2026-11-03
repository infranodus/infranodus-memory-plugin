#!/usr/bin/env python3
"""InfraNodus memory: hook runtime and the /infranodus-memory:* commands.

Standard library only, so it starts fast and needs nothing installed.

    memory.py hook-prompt     UserPromptSubmit hook (stdin: the hook JSON)
    memory.py hook-flush      PreCompact / SessionEnd hook (stdin: the hook
                              JSON): starts the upload worker and returns
    memory.py ingest-worker   (detached) trims the new part of the session,
                              uploads it to /api/v1/ingest, retries the queue
    memory.py off|on|status|forget-last|save
                              the plugin's commands, for the project in cwd
                              (save: upload the current session now)

The hook never slows Claude down or gets in its way (design doc, "Performance:
never slow the agent down"): it does work only on the first prompt of a
session, calls /api/v1/recall once with a 2 s timeout, and on any failure
prints nothing and exits 0.

Local state lives in ~/.infranodus/ (design doc, "Where memory state lives"):
    memory.json     {"off": [projects], "told": [projects], "keyWarned": bool,
                     "reported": {project: last session reported as saved}}
    sessions/<id>   one empty file per session that already had its recall
    uploaded/<id>   the transcript line up to which the session was uploaded
    queue/*.json    uploads that failed, retried by the next worker
    timings.log     one line per hook run, rotated
The server stores no on/off state: a project listed in "off" is skipped here
before anything is sent.
"""

import json
import os
import sys
import time

CLIENT = "claude-code"
DEFAULT_API_BASE = "https://infranodus.com/api/v1"
RECALL_TIMEOUT_S = 2.0
INGEST_TIMEOUT_S = 30.0
MIN_EXCERPT_CHARS = 500  # less than this carries nothing worth an AI call
QUEUE_MAX_AGE_S = 7 * 24 * 3600
QUEUE_MAX_ITEMS = 20
SESSION_MARKER_MAX_AGE_S = 7 * 24 * 3600
TIMINGS_MAX_BYTES = 256 * 1024
PROJECT_MARKERS = (
    ".git",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "Gemfile",
    "composer.json",
    ".obsidian",
    os.path.join("infranodus", "manifest.json"),
)


# ---------------------------------------------------------------------------
# Local state
# ---------------------------------------------------------------------------


def home_dir():
    return os.environ.get("INFRANODUS_HOME") or os.path.join(
        os.path.expanduser("~"), ".infranodus"
    )


def settings_path():
    return os.path.join(home_dir(), "memory.json")


def load_settings():
    """A missing or unreadable file means the defaults: on, nobody told."""
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data):
    os.makedirs(home_dir(), exist_ok=True)
    tmp = settings_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, settings_path())


def listed(settings, key, project):
    return project in (settings.get(key) or [])


def set_listed(settings, key, project, present):
    items = [p for p in (settings.get(key) or []) if p != project]
    if present:
        items.append(project)
    settings[key] = sorted(items)


def first_prompt_of_session(session_id):
    """True once per session: leaves a marker file, prunes old ones."""
    if not session_id:
        return False
    folder = os.path.join(home_dir(), "sessions")
    os.makedirs(folder, exist_ok=True)
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:80]
    marker = os.path.join(folder, safe or "unknown")
    if os.path.exists(marker):
        return False
    open(marker, "w").close()
    if hash(safe) % 20 == 0:  # prune now and then, not on every session
        cutoff = time.time() - SESSION_MARKER_MAX_AGE_S
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
    return True


def log_timing(event, project, started, outcome):
    try:
        path = os.path.join(home_dir(), "timings.log")
        if os.path.exists(path) and os.path.getsize(path) > TIMINGS_MAX_BYTES:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as f:
            f.write(
                "%s\t%s\t%s\t%dms\t%s\n"
                % (
                    time.strftime("%Y-%m-%dT%H:%M:%S"),
                    event,
                    project or "-",
                    (time.time() - started) * 1000,
                    outcome,
                )
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Project identity
# ---------------------------------------------------------------------------


def find_up(start, name, stop):
    path = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(path, name)):
            return path
        parent = os.path.dirname(path)
        if parent == path or path == stop:
            return None
        path = parent


def git_remote_name(repo_root):
    """Basename of the origin remote, read from .git/config (no subprocess)."""
    config = os.path.join(repo_root, ".git", "config")
    if not os.path.isfile(config):  # worktree or submodule: .git is a file
        return None
    try:
        with open(config, encoding="utf-8") as f:
            section, url = None, None
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    section = line
                elif section == '[remote "origin"]' and line.startswith("url"):
                    url = line.split("=", 1)[1].strip()
                    break
        if not url:
            return None
        name = url.rstrip("/").replace(":", "/").split("/")[-1]
        return name[:-4] if name.endswith(".git") else name
    except Exception:
        return None


def project_for(cwd):
    """The project name for cwd, or None when cwd isn't a project.

    The git remote's name when there is one, else the folder name of the repo
    (or of the nearest folder with a project marker). The same name an agent
    passes as `project` to get_project_learnings, so both reach one graph.
    Home, temp folders and folders without any project marker are not
    projects: nothing is recalled there.
    """
    if not cwd:
        return None
    home = os.path.expanduser("~")
    real = os.path.realpath(cwd)
    if real == os.path.realpath(home):
        return None
    for tmp in ("/tmp", "/private/tmp", "/var/folders", "/private/var/folders"):
        if real == tmp or real.startswith(tmp + "/"):
            return None
    repo = find_up(cwd, ".git", home)
    if repo:
        return git_remote_name(repo) or os.path.basename(repo)
    for marker in PROJECT_MARKERS[1:]:
        root = find_up(cwd, marker, home)
        if root and os.path.realpath(root) != os.path.realpath(home):
            return os.path.basename(root)
    return None


def excluded(cwd):
    """True when cwd matches the `exclude_paths` setting (globs separated by
    commas or new lines, ~ allowed): nothing is recalled or sent there."""
    raw = os.environ.get("CLAUDE_PLUGIN_OPTION_EXCLUDE_PATHS", "")
    if not raw.strip() or not cwd:
        return False
    import fnmatch

    real = os.path.realpath(cwd)
    for pattern in raw.replace("\n", ",").split(","):
        pattern = pattern.strip()
        if not pattern:
            continue
        pattern = os.path.expanduser(pattern).rstrip("/")
        if fnmatch.fnmatch(real, pattern) or fnmatch.fnmatch(real, pattern + "/*"):
            return True
    return False


def active_project(cwd, settings):
    """The project to work for, or None when memory must not run here."""
    if os.environ.get("INFRANODUS_MEMORY_DISABLE") == "1" or excluded(cwd):
        return None
    project = project_for(cwd)
    if not project or listed(settings, "off", project):
        return None
    return project


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def _setting(value):
    """A plugin setting, or "" when it is unset or arrived unsubstituted
    (a literal ${user_config.x})."""
    value = (value or "").strip()
    return "" if value.startswith("${") else value


def api_settings():
    """Hooks get the plugin settings as CLAUDE_PLUGIN_OPTION_* variables.
    Commands (skills) don't, so their command line passes them as
    --key / --base, which main() puts into the same variables."""
    key = _setting(os.environ.get("CLAUDE_PLUGIN_OPTION_API_KEY"))
    base = (
        _setting(os.environ.get("CLAUDE_PLUGIN_OPTION_API_BASE"))
        or DEFAULT_API_BASE
    ).rstrip("/")
    return key, base


SAVE_OPTIONS = ("learnings", "memories", "both")


def save_setting():
    """What uploads keep: both (default), learnings or memories."""
    value = _setting(os.environ.get("CLAUDE_PLUGIN_OPTION_SAVE")).lower()
    return value if value in SAVE_OPTIONS else "both"


def take_setting_args(argv):
    """Moves --key VALUE / --base VALUE from argv into the environment.
    The values are never printed."""
    names = {
        "--key": "CLAUDE_PLUGIN_OPTION_API_KEY",
        "--base": "CLAUDE_PLUGIN_OPTION_API_BASE",
        "--save": "CLAUDE_PLUGIN_OPTION_SAVE",
        "--session": "INFRANODUS_SESSION_ID",
    }
    rest, i = [], 0
    while i < len(argv):
        if argv[i] in names and i + 1 < len(argv):
            value = _setting(argv[i + 1])
            if value:
                os.environ[names[argv[i]]] = value
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return rest


def post(base, key, path, body, timeout):
    """Returns (status, json body or None). Raises on network errors."""
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "X-Infranodus-Client": "memory-plugin",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8"))
        except Exception:
            return error.code, None


# ---------------------------------------------------------------------------
# Hook: first prompt of a session
# ---------------------------------------------------------------------------


def hook_prompt(event):
    """Returns the hook's JSON output (dict) or None for no output."""
    settings = load_settings()
    project = active_project(event.get("cwd") or os.getcwd(), settings)
    if not project:
        return None
    if not first_prompt_of_session(event.get("session_id")):
        return None

    key, base = api_settings()
    if not key:
        return None
    status, body = post(
        base,
        key,
        "/recall",
        {"project": project, "prompt": event.get("prompt") or "", "client": CLIENT},
        RECALL_TIMEOUT_S,
    )

    output = {}
    if status in (401, 403):
        if not settings.get("keyWarned"):
            settings["keyWarned"] = True
            save_settings(settings)
            output["systemMessage"] = (
                "InfraNodus memory: the API key was rejected, so memory is "
                "inactive. Update it with /plugin (infranodus-memory > Configure)."
            )
        return output or None
    if status != 200 or not isinstance(body, dict):
        return None
    if settings.get("keyWarned"):
        settings.pop("keyWarned", None)
        save_settings(settings)

    block = body.get("block") or ""
    if block:
        output["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": block,
        }
    lines = []
    if not listed(settings, "told", project):
        set_listed(settings, "told", project, True)
        url = body.get("graphUrl") or ""
        lines.append(
            "InfraNodus memory is on for %s%s. "
            "/infranodus-memory:off to stop for this project."
            % (project, (" → " + url) if url else "")
        )
    saved = body.get("saved") or {}
    reported = settings.setdefault("reported", {})
    if saved.get("sessionId") and saved.get("count") and reported.get(project) != saved["sessionId"]:
        reported[project] = saved["sessionId"]
        lines.append(
            "InfraNodus memory saved %d learning%s from your last session in %s "
            "(/infranodus-memory:forget-last to undo)."
            % (saved["count"], "" if saved["count"] == 1 else "s", project)
        )
    if lines:
        save_settings(settings)
        output["systemMessage"] = " ".join(lines)
    return output or None


# ---------------------------------------------------------------------------
# Hook: session upload (PreCompact, SessionEnd)
# ---------------------------------------------------------------------------


def hook_flush(event):
    """Starts the upload in a detached process and returns at once, so
    compaction and exit never wait on it."""
    if os.environ.get("INFRANODUS_MEMORY_DISABLE_CAPTURE") == "1":
        return
    cwd = event.get("cwd") or os.getcwd()
    if not active_project(cwd, load_settings()) or not api_settings()[0]:
        return
    transcript = event.get("transcript_path") or ""
    if not transcript or not os.path.isfile(transcript):
        return
    import subprocess

    subprocess.Popen(
        [
            sys.executable,
            os.path.abspath(__file__),
            "ingest-worker",
            transcript,
            event.get("session_id") or "",
            cwd,
            event.get("hook_event_name") or "",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )


def _safe(session_id):
    return "".join(c for c in session_id if c.isalnum() or c in "-_")[:80]


def _queue_dir():
    return os.path.join(home_dir(), "queue")


def _upload(base, key, item):
    """'done', 'retry' (network, 429, 5xx) or 'drop' (refused for good)."""
    try:
        status, _ = post(
            base,
            key,
            "/ingest",
            {
                "project": item["project"],
                "excerpt": item["excerpt"],
                "sessionId": item["sessionId"],
                "client": CLIENT,
                "save": item.get("save") or "both",
            },
            INGEST_TIMEOUT_S,
        )
    except Exception:
        return "retry"
    if status in (200, 202):
        return "done"
    # 404: the server doesn't have /ingest yet (an older or restarting
    # server), so keep the upload for later instead of losing it.
    if status in (404, 429) or status >= 500:
        return "retry"
    return "drop"


def _retry_queue(base, key):
    folder = _queue_dir()
    if not os.path.isdir(folder):
        return
    cutoff = time.time() - QUEUE_MAX_AGE_S
    for name in sorted(os.listdir(folder))[:QUEUE_MAX_ITEMS]:
        path = os.path.join(folder, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                continue
            with open(path, encoding="utf-8") as f:
                item = json.load(f)
            outcome = _upload(base, key, item)
            if outcome == "retry":
                return  # still failing: leave the rest for later
            os.remove(path)
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass


def ingest_worker(transcript, session_id, cwd, event_name):
    """Upload the part of the session not uploaded yet. Returns an outcome
    word for the timings log."""
    settings = load_settings()
    project = active_project(cwd, settings)
    key, base = api_settings()
    if not project or not key or not session_id:
        return "skipped"
    _retry_queue(base, key)

    folder = os.path.join(home_dir(), "uploaded")
    os.makedirs(folder, exist_ok=True)
    marker = os.path.join(folder, _safe(session_id))
    lock = marker + ".lock"
    try:  # one worker per session at a time (PreCompact and SessionEnd)
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        if time.time() - os.path.getmtime(lock) < 300:
            return "busy"
    try:
        try:
            with open(marker) as f:
                start = int(f.read().strip() or 0)
        except (OSError, ValueError):
            start = 0
        import excerpt as excerpt_module

        text, end, turns = excerpt_module.build_excerpt(transcript, start)
        if turns == 0 or len(text) < MIN_EXCERPT_CHARS:
            if event_name != "SessionEnd":
                return "too-small"  # keep it for the next upload
            with open(marker, "w") as f:
                f.write(str(end))
            return "too-small"
        item = {
            "project": project,
            "excerpt": text,
            "sessionId": session_id,
            "save": save_setting(),
        }
        outcome = _upload(base, key, item)
        if outcome == "retry":
            os.makedirs(_queue_dir(), exist_ok=True)
            name = "%d-%s-%d.json" % (time.time(), _safe(session_id), start)
            with open(os.path.join(_queue_dir(), name), "w", encoding="utf-8") as f:
                json.dump(item, f)
        with open(marker, "w") as f:
            f.write(str(end))
        return "uploaded" if outcome == "done" else outcome
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Commands: /infranodus-memory:off, :on, :status
# ---------------------------------------------------------------------------


def transcripts_dir(cwd):
    """Where Claude Code keeps this folder's session transcripts:
    ~/.claude/projects/<the path with every non-alphanumeric as '-'>."""
    import re

    root = os.environ.get("INFRANODUS_TRANSCRIPTS") or os.path.join(
        os.path.expanduser("~"), ".claude", "projects"
    )
    return os.path.join(root, re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cwd)))


def current_transcript(cwd, session_id):
    """(path, session id) of the session to save: the one named by
    --session when Claude Code filled it in, else the folder's most recently
    written transcript, which is the session running the command."""
    folder = transcripts_dir(cwd)
    if session_id and os.path.isfile(os.path.join(folder, session_id + ".jsonl")):
        return os.path.join(folder, session_id + ".jsonl"), session_id
    try:
        files = [
            os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".jsonl")
        ]
    except OSError:
        return None, None
    if not files:
        return None, None
    newest = max(files, key=os.path.getmtime)
    return newest, os.path.basename(newest)[: -len(".jsonl")]


def save_now(cwd):
    """/infranodus-memory:save: upload the part of the current session not
    uploaded yet, as the session-end hook would. It stays counted, so the
    session end sends only what comes after."""
    started = time.time()
    settings = load_settings()
    project = active_project(cwd, settings)
    if not project:
        return (
            "InfraNodus memory isn't running here (it's off for this project, "
            "the folder is excluded, or it isn't a project), so nothing was saved."
        )
    if not api_settings()[0]:
        return "The InfraNodus API key isn't set (configure it in /plugin)."
    transcript, session_id = current_transcript(
        cwd, _setting(os.environ.get("INFRANODUS_SESSION_ID"))
    )
    if not transcript:
        return "Couldn't find this session's transcript, so nothing was saved."
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    outcome = ingest_worker(transcript, session_id, cwd, "Manual")
    log_timing("save", project, started, outcome)
    graph = "learn-" + project
    return {
        "uploaded": (
            "Sent this session to InfraNodus (saving: %s). Learnings appear in %s "
            "within about a minute%s; the next session here says how many were saved."
            % (
                save_setting(),
                graph,
                ", and facts about clients or subjects, if any, in their memory-<topic> graphs"
                if save_setting() != "learnings"
                else "",
            )
        ),
        "too-small": "Nothing new to save since the last save (or too little to be worth it).",
        "retry": "InfraNodus couldn't be reached; the upload is queued and retried automatically.",
        "drop": "InfraNodus refused the upload (check the API key and address with /infranodus-memory:status).",
        "busy": "An upload for this session is already running; try again in a moment.",
    }.get(outcome, "Nothing was saved (%s)." % outcome)


def command(name, cwd):
    project = project_for(cwd)
    if not project:
        return (
            "This folder isn't a project (no git repo or project file found), "
            "so InfraNodus memory doesn't run here anyway."
        )
    settings = load_settings()
    if name == "off":
        set_listed(settings, "off", project, True)
        save_settings(settings)
        return (
            "InfraNodus memory is now off for %s on this machine: nothing is "
            "recalled or sent for it. The graph learn-%s is kept; "
            "/infranodus-memory:on turns memory back on." % (project, project)
        )
    if name == "on":
        set_listed(settings, "off", project, False)
        save_settings(settings)
        return "InfraNodus memory is on for %s again." % project
    if name == "save":
        return save_now(cwd)
    if name == "forget-last":
        key, base = api_settings()
        if not key:
            return "The InfraNodus API key isn't set (configure it in /plugin)."
        try:
            status, body = post(base, key, "/memory/forget", {"project": project}, 15)
        except Exception as error:
            return "Couldn't reach InfraNodus: %s" % error
        if status != 200 or not isinstance(body, dict):
            return "InfraNodus refused (%s): %s" % (status, (body or {}).get("error", ""))
        count = body.get("forgotten", 0)
        if not count:
            return body.get("message") or "Nothing to forget for %s." % project
        return "Removed the %d learning%s saved from the last session in %s." % (
            count, "" if count == 1 else "s", project)
    state = "off" if listed(settings, "off", project) else "on"
    key, base = api_settings()
    lines = [
        "Project: %s" % project,
        "Memory: %s for this project (settings: %s)" % (state, settings_path()),
        "API key: %s" % ("set" if key else "missing (configure it in /plugin)"),
        "Saves: %s" % save_setting(),
    ]
    if base != DEFAULT_API_BASE:
        lines.append("API address: %s" % base)
    return "\n".join(lines)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "hook-prompt":
        started = time.time()
        project, outcome = None, "skipped"
        try:
            event = json.load(sys.stdin)
            project = project_for(event.get("cwd") or os.getcwd())
            result = hook_prompt(event)
            if result:
                sys.stdout.write(json.dumps(result))
                outcome = "recalled"
        except Exception as error:  # never block or disturb the prompt
            outcome = "error:%s" % type(error).__name__
        log_timing("prompt", project, started, outcome)
        return 0
    if action == "hook-flush":
        started = time.time()
        outcome = "started"
        try:
            hook_flush(json.load(sys.stdin))
        except Exception as error:
            outcome = "error:%s" % type(error).__name__
        log_timing("flush", None, started, outcome)
        return 0
    if action == "ingest-worker" and len(sys.argv) >= 6:
        started = time.time()
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            outcome = ingest_worker(*sys.argv[2:6])
        except Exception as error:
            outcome = "error:%s" % type(error).__name__
        log_timing("upload", project_for(sys.argv[4]), started, outcome)
        return 0
    if action in ("off", "on", "status", "forget-last", "save"):
        take_setting_args(sys.argv[2:])
        print(command(action, os.getcwd()))
        return 0
    print("usage: memory.py hook-prompt | hook-flush | off | on | status | forget-last", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
