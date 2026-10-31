# Memory system TODO: `infranodus-memory` plugin

**Status:** proposal / todo (moved here from the skills repo on 2026-10-31)
**Plan (step by step):** [`../plan.md`](../plan.md)
**Design:** [`mcp-server-infranodus/docs/drafts/infranodus-memory-system.md`](../../../mcp-server-infranodus/docs/drafts/infranodus-memory-system.md)
**Depends on:** the `/api/v1/recall`, `/api/v1/ingest` and `/api/v1/memory/*` endpoints in `infranodus-app` (its `docs/todo/memory-system.md`)


## Why a new plugin, not hooks in `infranodus`

- Claude Code merges duplicate MCP servers across plugins (verified by the skills repo's `tests/split-test.sh`, section C), but it does not merge hooks. Hooks in `infranodus`, `infranodus-all` and `project-learnings` would capture each session two or three times.
- Installing it is the consent: memory is on from install in every project (opt-out per project). The other plugins and skills keep the per-project opt-in.
- It needs an API key (`userConfig`), which the core plugin shouldn't ask for.

Keep it out of `infranodus-all`: a bundle install would turn on background capture for users who only wanted the graph tools.

## Performance (applies to every phase)

Memory must never slow Claude down; see "Performance: never slow the agent down" in the design doc.

- [ ] Recall only on the first prompt; 2 s hard timeout; no foreground retries; skip recall for the rest of the session after two timeouts or a 429/5xx
- [ ] Capture hooks: append one line to the queue in under 50 ms; no network; truncate tool output before writing
- [ ] `PreCompact` / `SessionEnd`: spawn the detached ingest worker and return in under 100 ms
- [ ] Register hooks without output (capture, ingest) with `async: true`
- [ ] Standard library only, lazy imports, nothing installed or checked at hook time; no daemon
- [ ] Recall block capped at 5 items and about 1,500 characters
- [ ] Cap the queue size per session; trim the oldest tool output first
- [ ] Every failure path exits 0 with no output
- [ ] Log each hook's duration to `${CLAUDE_PLUGIN_DATA}/timings.log` (rotated)

## Phase 2: plugin skeleton and recall hook

- [ ] Repo root with `.claude-plugin/plugin.json`: name `infranodus-memory`, `mcpServers.infranodus` (same as the others, so it's merged), `userConfig.api_key` (`sensitive: true`, `required: true`, so Claude Code asks for it at install), `userConfig.exclude_paths` (globs, optional), `userConfig.mode` (`auto` default, or `review`)
- [ ] `hooks/hooks.json` with `UserPromptSubmit` only for now
- [ ] `hooks/memory_hook.py` (stdlib only, like `infranodus/scripts/repo2statements.py` in the skills repo): on the first prompt of a session, call `/api/v1/recall` with a 2 s timeout and return `hookSpecificOutput.additionalContext`; on any error or missing key, return nothing and exit 0
- [ ] Project identity: git remote slug when available, else the directory name; must match the `project` that `get_project_learnings` uses
- [ ] Track "first prompt" per `session_id` in `${CLAUDE_PLUGIN_DATA}`
- [ ] Keep the `enabled` and `mode` values from the first recall's response for the rest of the session (no separate cache)
- [ ] First-run line: when recall returns `firstRun: true`, show the user (a user-facing message, not only `additionalContext`) "InfraNodus memory is on for `<project>` → graph link. `/memory off` to stop for this project." Once per project
- [ ] Invalid key: hooks do nothing; say so once in the first-run line
- [ ] `/memory off` and `/memory on` (skill command → `/api/v1/memory/disable`, `/memory/enable-project`); `off` asks separately whether to delete the graph
- [ ] Version the plugin in `plugin.json` and tag releases; the skills marketplace entry points at this repo
- [ ] Release workflow: decide whether to build a zip (hooks don't work in Claude web; probably skip it)

## Phase 3: capture and ingest

- [ ] Add `PostToolUse`, `PostToolUseFailure`, `Stop` hooks: append to a local queue in `${CLAUDE_PLUGIN_DATA}/queue/<session>.jsonl`, with no network calls and a 3 s timeout
- [ ] Record nothing when the session's recall returned `enabled: false`, when the path matches `exclude_paths`, or in the home directory, temp folders, or a folder that is neither a git repo nor has a project marker
- [ ] Redact before writing to the queue: API keys and tokens (common prefixes and high-entropy strings), private key blocks, `.env` contents; drop text inside `<private>…</private>`
- [ ] Off switches checked first in every hook: `INFRANODUS_MEMORY_DISABLE=1`, `INFRANODUS_MEMORY_DISABLE_CAPTURE=1` (recall only)
- [ ] `PreCompact` and `SessionEnd`: pre-trim the queue (last turns, failures, final answers, files edited, at most about 6k tokens, plus a list of successful shell commands up to about 1.5k tokens; reference implementation `experiments/extraction/trim.py`, mode `trimmed2`), then start a detached worker that posts to `/api/v1/ingest` with the `session_id`; delete the queue on success
- [ ] Recover stuck queues on the next `SessionStart`: a queue whose worker died is retried
- [ ] `/memory forget-last` → `/api/v1/memory/forget` (deletes the last session's statements by their `session-<id>` category)
- [ ] Show the recall's `saved` line ("Saved 4 learnings from your last session") and `quotaPaused` notice
- [ ] `skills/memory/SKILL.md`: memory is on from install; `/memory off`/`on`, `/memory forget-last`, `exclude_paths` and `<private>` tags; `/memory review` for users in `review` mode; how to enable topic or personal memory

## Phase 5: hooks for other clients

See "Hooks for other clients" in the design doc.

- [ ] Restructure `hooks/memory_hook.py` into a small package: `core` (recall, queue, enable cache, ingest worker) and `adapters/<client>.py` (normalize stdin, format output); entry point `hook <client> <event>` with events `start`, `prompt`, `tool`, `stop`, `compact`
- [ ] Claude Code adapter first, with the existing behaviour unchanged (the plugin's `hooks.json` calls `hook claude-code <event>`)
- [ ] `raw` adapter that reads the internal event shape, used for unknown clients
- [ ] Codex CLI adapter: supports `additionalContext`, so recall works as in Claude Code
- [ ] Cursor adapter: no context injection; write recall to `.cursor/rules/infranodus-memory.mdc` (`alwaysApply: true`, "generated, do not edit" header), refreshed on `prompt` and after ingest
- [ ] Then Windsurf (`.windsurf/rules/`), Gemini CLI, Kimi: check each client's current hook docs for event names and payloads before writing the adapter
- [ ] Installer: `install --client <name>` / `uninstall --client <name>` writes and removes the client's hook config, the MCP entry if missing, the rules file, and a `.gitignore` line for it
- [ ] One table of per-client hook timeouts; recall's request budget derived from it; a test that the configs the installer writes match the table
- [ ] Off switches checked first in every hook: `INFRANODUS_MEMORY_DISABLE=1`, `INFRANODUS_MEMORY_DISABLE_CAPTURE=1`
- [ ] Send `client` with every recall and ingest; dedup queue entries by `toolUseId` where the client provides one
- [ ] OpenCode / OpenClaw: thin JS plugins that call the same command on their events
- [ ] Tests: a recorded payload fixture per client through its adapter → the expected internal event; output format per client; the rules file is written, refreshed and removed by uninstall


## Tests

- [ ] Hook unit tests: no key means no output and exit 0; a timeout means no output; only the first prompt per session triggers recall
- [ ] Timing tests: each capture hook under 50 ms and each ingest hook under 100 ms on a long fixture session; recall gives up at 2 s against a slow mock server; a session with Claude Code and the plugin is not measurably slower than without it
- [ ] Queue tests: nothing is written for a disabled or excluded project, the home directory or a non-project folder; secrets and `<private>` text are redacted; the queue is deleted after a successful ingest and kept after a failure
- [ ] First-run line appears once per project; `/memory off` stops capture from the next event
