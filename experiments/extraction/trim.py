#!/usr/bin/env python3
"""Turn a Claude Code session transcript (.jsonl) into an ingest excerpt.

Two modes, for the step-2 extraction test (docs/plan.md):

  trimmed  What the plugin's capture hooks would record, cut to a budget
           (default ~6k tokens): user prompts, the agent's final answer of each
           turn, failed tool calls, and the list of files edited.
  full     Everything readable in order (prompts, all agent text, every tool
           call and result, each result truncated), cut to a large budget
           (default ~100k tokens) from the start, keeping the end.

Secrets are redacted in both modes. Standard library only.

Usage: trim.py <transcript.jsonl> {trimmed|full} [--tokens N]
"""
import argparse
import json
import re
import sys

CHARS_PER_TOKEN = 4

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


def events(path):
    """Yield (kind, data) in transcript order."""
    for line in open(path, encoding="utf-8", errors="replace"):
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
            return f"{name}({key}={clip(str(inp[key]), 200)})"
    return f"{name}({clip(json.dumps(inp)[:200], 200)})"


def trimmed(path, budget_chars):
    turns, files, calls = [], [], {}
    cur = None
    for kind, data in events(path):
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
                cur["failures"].append(f"{tool_summary(*calls[tid])} -> {clip(txt, 300)}")
    blocks = []
    for t in turns:
        parts = [f"USER: {t['prompt']}"]
        for f in t["failures"][-3:]:
            parts.append(f"TOOL FAILED: {f}")
        if t["answer"]:
            parts.append(f"AGENT (final answer): {clip(t['answer'], 2000)}")
        blocks.append("\n".join(parts))
    header = "FILES EDITED: " + (", ".join(files[-40:]) or "none") + "\n\n"
    # keep the most recent turns that fit the budget
    kept, size = [], len(header)
    for b in reversed(blocks):
        if size + len(b) + 2 > budget_chars and kept:
            break
        kept.append(b)
        size += len(b) + 2
    dropped = len(blocks) - len(kept)
    note = f"[{dropped} earlier turns omitted]\n\n" if dropped else ""
    return header + note + "\n\n".join(reversed(kept))


def full(path, budget_chars):
    out = []
    for kind, data in events(path):
        if kind == "prompt":
            out.append(f"USER: {data}")
        elif kind == "text":
            out.append(f"AGENT: {data}")
        elif kind == "tool":
            out.append(f"TOOL CALL: {tool_summary(data[1], data[2])}")
        elif kind == "result":
            out.append(f"TOOL RESULT{' (error)' if data[1] else ''}: {clip(data[2], 3000)}")
    text = "\n\n".join(out)
    if len(text) > budget_chars:
        text = "[beginning of session omitted]\n\n" + text[-budget_chars:]
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("mode", choices=["trimmed", "full"])
    ap.add_argument("--tokens", type=int)
    a = ap.parse_args()
    tokens = a.tokens or (6000 if a.mode == "trimmed" else 100000)
    fn = trimmed if a.mode == "trimmed" else full
    sys.stdout.write(redact(fn(a.transcript, tokens * CHARS_PER_TOKEN)))


if __name__ == "__main__":
    main()
