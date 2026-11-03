"""Build the ingest excerpt from a Claude Code session transcript (.jsonl).

The production form of experiments/extraction/trim.py, mode `trimmed2`, which
the step-2 test chose (docs/plan.md, Q2): a COMMANDS RUN list (successful shell
commands, read-only ones left out) plus the trimmed session (user prompts, the
agent's final answer of each turn, failed tool calls, files edited), about 6k
tokens, most recent turns kept. Secrets and <private> text are redacted.

One addition: `start_line`. The transcript only grows, and a session can be
uploaded more than once (before a compaction, then at its end), so each upload
covers only the lines after the previous one.

Two transcript formats are read, detected from the lines themselves:
Claude Code's (`type: user|assistant` with a `message`) and Codex's rollout
(`type: response_item|event_msg|session_meta` with a `payload`), which Codex
hands to hooks as `transcript_path` too.
"""

import json
import re

CHARS_PER_TOKEN = 4
EXCERPT_TOKENS = 6000
COMMANDS_TOKENS = 1500

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|xox[abp]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,})"), "[REDACTED KEY]"),
    (re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization)(\"?\s*[:=]\s*\"?)([^\s\"',]{8,})"), r"\1\2[REDACTED]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"), "Bearer [REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9_-]{40,}\b"), "[REDACTED LONG TOKEN]"),
]
PRIVATE_TAG = re.compile(r"<private>.*?</private>", re.S)

# User-role strings that are not prompts the person typed.
NOT_A_PROMPT = ("<local-command", "<command-", "<system-reminder", "Base directory for this skill",
                "<task-notification", "Caveat:", "[Request interrupted", "Another Claude session sent a message",
                "<agent-message", "<system-notification")

# First words of shell commands that only look around; they carry no how-to.
READ_ONLY = {"ls", "cat", "head", "tail", "grep", "rg", "find", "pwd", "wc", "echo", "sed", "awk", "which",
             "file", "stat", "tree", "less", "diff", "sort", "uniq", "jq", "true", "sleep",
             "mv", "rm", "cp", "mkdir", "touch", "chmod", "export", "source", "open"}
READ_ONLY_GIT = ("git status", "git diff", "git log", "git show", "git branch", "git rev-parse", "git remote")
# Leading "cd dir &&" or "VAR=value;" that only sets up the real command.
SETUP_PREFIX = re.compile(r"^\s*(cd\s+\S+|[A-Z_][A-Z0-9_]*=\S+)\s*(&&|;|\n)\s*")


def redact(text):
    text = PRIVATE_TAG.sub("[PRIVATE]", text)
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def clip(text, n):
    text = text.strip()
    return text if len(text) <= n else text[: n - 20] + " …[truncated]"


def result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


CODEX_TYPES = ("response_item", "event_msg", "session_meta", "turn_context")
# Codex tool names that run a shell command, and the argument that holds it.
CODEX_SHELL_TOOLS = ("shell", "shell_command", "exec_command", "local_shell", "bash", "container.exec")
CODEX_TAG = re.compile(r"^\s*<[a-z][a-z0-9_:-]*[\s>/]")
EXIT_CODE = re.compile(r"(?i)\bexit[ _]code\W{0,4}(\d+)")


def transcript_format(lines):
    """'codex' or 'claude', from the first lines that parse."""
    for line in lines[:50]:
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if isinstance(o, dict) and o.get("type") in CODEX_TYPES:
            return "codex"
    return "claude"


def _codex_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text")
        )
    return ""


def _codex_shell_command(name, args):
    """The shell command of a Codex tool call, or None when it isn't one."""
    if name not in CODEX_SHELL_TOOLS:
        return None
    cmd = args.get("cmd") or args.get("command") or ""
    if isinstance(cmd, list):  # ["bash", "-lc", "npm test"]
        cmd = cmd[-1] if len(cmd) >= 3 and cmd[1] in ("-lc", "-c") else " ".join(str(c) for c in cmd)
    return str(cmd)


def _codex_patched_files(patch):
    return re.findall(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", patch or "", re.M)


def events_codex(lines):
    """The Codex rollout: the same (kind, data) events as events() yields
    for Claude Code, so trimmed() and commands_run() need no second path.
    Tool calls become ("tool", (id, "Bash"|"Edit"|name, input)) and their
    outputs ("result", (id, is_error, text)); an error is a non-zero exit
    code or an output that starts with an error word."""
    for line in lines:
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict):
            continue
        p = o.get("payload") or {}
        t, pt = o.get("type"), p.get("type")
        if t == "response_item" and pt == "message":
            text = _codex_text(p.get("content"))
            if p.get("role") == "user":
                # Codex wraps context and app events in XML-like tags; a prompt
                # the person typed doesn't start with one.
                if text.strip() and not CODEX_TAG.match(text):
                    yield "prompt", text
            elif p.get("role") == "assistant" and text.strip():
                yield "text", text
        elif t == "event_msg" and pt == "task_complete" and p.get("last_agent_message"):
            yield "text", p["last_agent_message"]
        elif t == "response_item" and pt in ("function_call", "custom_tool_call"):
            name = p.get("name") or "?"
            raw = p.get("arguments") if pt == "function_call" else p.get("input")
            try:
                args = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except ValueError:
                args = {"input": raw}
            if not isinstance(args, dict):
                args = {"input": args}
            cmd = _codex_shell_command(name, args)
            if cmd is not None:
                yield "tool", (p.get("call_id"), "Bash", {"command": cmd})
            elif name == "apply_patch":
                patch = args.get("input") or args.get("patch") or (raw if isinstance(raw, str) else "")
                for path in _codex_patched_files(patch):
                    yield "tool", (p.get("call_id"), "Edit", {"file_path": path})
            else:
                yield "tool", (p.get("call_id"), name, args)
        elif t == "response_item" and pt in ("function_call_output", "custom_tool_call_output"):
            text = _codex_text(p.get("output"))
            m = EXIT_CODE.search(text[:400])
            is_error = bool(m and m.group(1) != "0") or text.lstrip()[:6].lower().startswith("error")
            yield "result", (p.get("call_id"), is_error, text)


def events(lines):
    """Yield (kind, data) in transcript order, for either format."""
    if transcript_format(lines) == "codex":
        yield from events_codex(lines)
        return
    for line in lines:
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("isSidechain"):
            continue
        t = o.get("type")
        if t not in ("user", "assistant"):
            continue
        content = (o.get("message") or {}).get("content")
        if t == "user" and isinstance(content, str):
            if not content.lstrip().startswith(NOT_A_PROMPT):
                yield "prompt", content
            continue
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            bt = b.get("type")
            if t == "user" and bt == "text":
                txt = b.get("text", "")
                if not txt.lstrip().startswith(NOT_A_PROMPT):
                    yield "prompt", txt
            elif t == "user" and bt == "tool_result":
                yield "result", (b.get("tool_use_id"), bool(b.get("is_error")), result_text(b.get("content")))
            elif t == "assistant" and bt == "text":
                yield "text", b.get("text", "")
            elif t == "assistant" and bt == "tool_use":
                yield "tool", (b.get("id"), b.get("name", "?"), b.get("input") or {})


def tool_summary(name, inp):
    for key in ("file_path", "command", "pattern", "url", "query", "description", "prompt"):
        if key in inp:
            return "%s(%s=%s)" % (name, key, clip(str(inp[key]), 200))
    return "%s(%s)" % (name, clip(json.dumps(inp)[:200], 200))


def command_key(cmd):
    if "<<" in cmd:  # heredocs are file-editing or throwaway scripts, not how-to
        return None
    prev = None
    while prev != cmd:
        prev, cmd = cmd, SETUP_PREFIX.sub("", cmd.strip())
    first = cmd.split()[0] if cmd.split() else ""
    if first in READ_ONLY or cmd.startswith(READ_ONLY_GIT):
        return None
    return " ".join(cmd.split())


def commands_run(lines, budget_chars):
    calls, seen, out = {}, set(), []
    for kind, data in events(lines):
        if kind == "tool" and data[1] == "Bash":
            calls[data[0]] = data[2].get("command", "")
        elif kind == "result" and data[0] in calls and not data[1]:
            key = command_key(calls.pop(data[0]))
            if key and key not in seen:
                seen.add(key)
                out.append(clip(key, 150))
    kept, size = [], 0
    for c in reversed(out):  # keep the most recent that fit
        if size + len(c) + 3 > budget_chars:
            break
        kept.append(c)
        size += len(c) + 3
    return list(reversed(kept))


def trimmed(lines, budget_chars):
    """Returns (text, number of turns with a user prompt)."""
    turns, files, calls = [], [], {}
    cur = None
    for kind, data in events(lines):
        if kind == "prompt":
            cur = {"prompt": clip(data, 1500), "answer": "", "failures": []}
            turns.append(cur)
        elif cur is None:
            continue
        elif kind == "text":
            cur["answer"] = data  # last text of the turn wins = final answer
        elif kind == "tool":
            tid, name, inp = data
            calls[tid] = (name, inp)
            if name in ("Edit", "Write", "NotebookEdit") and inp.get("file_path") and inp["file_path"] not in files:
                files.append(inp["file_path"])
        elif kind == "result":
            tid, is_err, txt = data
            if is_err and tid in calls:
                cur["failures"].append("%s -> %s" % (tool_summary(*calls[tid]), clip(txt, 300)))
    blocks = []
    for t in turns:
        parts = ["USER: %s" % t["prompt"]]
        for f in t["failures"][-3:]:
            parts.append("TOOL FAILED: %s" % f)
        if t["answer"]:
            parts.append("AGENT (final answer): %s" % clip(t["answer"], 2000))
        blocks.append("\n".join(parts))
    header = "FILES EDITED: " + (", ".join(files[-40:]) or "none") + "\n\n"
    kept, size = [], len(header)
    for b in reversed(blocks):  # keep the most recent turns that fit
        if size + len(b) + 2 > budget_chars and kept:
            break
        kept.append(b)
        size += len(b) + 2
    dropped = len(blocks) - len(kept)
    note = "[%d earlier turns omitted]\n\n" % dropped if dropped else ""
    return header + note + "\n\n".join(reversed(kept)), len(turns)


def build_excerpt(path, start_line=0, tokens=EXCERPT_TOKENS):
    """Returns (excerpt, end_line, turns) for the transcript lines from
    start_line on. `turns` counts user prompts, so the caller can skip a
    session with nothing in it."""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    new = lines[start_line:]
    cmds = commands_run(new, COMMANDS_TOKENS * CHARS_PER_TOKEN)
    block = "COMMANDS RUN (succeeded):\n" + ("\n".join("- %s" % c for c in cmds) or "none") + "\n\n"
    body, turns = trimmed(new, tokens * CHARS_PER_TOKEN)
    return redact(block + body), len(lines), turns
