#!/usr/bin/env python3
"""InfraNodus memory: hook runtime and the /infranodus-memory:* commands.

Standard library only, so it starts fast and needs nothing installed.

    memory.py hook-prompt     UserPromptSubmit hook (stdin: the hook JSON)
    memory.py off|on|status   the plugin's commands, for the project in cwd

The hook never slows Claude down or gets in its way (design doc, "Performance:
never slow the agent down"): it does work only on the first prompt of a
session, calls /api/v1/recall once with a 2 s timeout, and on any failure
prints nothing and exits 0.

Local state lives in ~/.infranodus/ (design doc, "Where memory state lives"):
    memory.json     {"off": [projects], "told": [projects], "keyWarned": bool}
    sessions/<id>   one empty file per session that already had its recall
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


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def api_settings():
    key = os.environ.get("CLAUDE_PLUGIN_OPTION_API_KEY", "").strip()
    base = (
        os.environ.get("CLAUDE_PLUGIN_OPTION_API_BASE", "").strip()
        or DEFAULT_API_BASE
    ).rstrip("/")
    return key, base


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
    if os.environ.get("INFRANODUS_MEMORY_DISABLE") == "1":
        return None
    project = project_for(event.get("cwd") or os.getcwd())
    if not project:
        return None
    settings = load_settings()
    if listed(settings, "off", project):
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
    if not listed(settings, "told", project):
        set_listed(settings, "told", project, True)
        save_settings(settings)
        url = body.get("graphUrl") or ""
        output["systemMessage"] = (
            "InfraNodus memory is on for %s%s. "
            "/infranodus-memory:off to stop for this project."
            % (project, (" → " + url) if url else "")
        )
    return output or None


# ---------------------------------------------------------------------------
# Commands: /infranodus-memory:off, :on, :status
# ---------------------------------------------------------------------------


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
    state = "off" if listed(settings, "off", project) else "on"
    key, base = api_settings()
    lines = [
        "Project: %s" % project,
        "Memory: %s for this project (settings: %s)" % (state, settings_path()),
        "API key: %s" % ("set" if key else "missing (configure it in /plugin)"),
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
    if action in ("off", "on", "status"):
        print(command(action, os.getcwd()))
        return 0
    print("usage: memory.py hook-prompt | off | on | status", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
