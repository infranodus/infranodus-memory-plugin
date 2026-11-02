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
- [ ] Log each hook's duration to `~/.infranodus/timings.log` (rotated)

## Phase 2: plugin skeleton and recall hook

> Built 2026-11-02 (not released): `.claude-plugin/plugin.json` (`api_key` sensitive and required, optional `api_base`), `hooks/hooks.json`, `hooks/memory.py` (the hook and the commands in one stdlib file), `skills/{off,on,status}` (invoked as `/infranodus-memory:off` etc., namespaced so they never clash with Claude Code's `/memory`; `disable-model-invocation`, so Claude can't turn memory off by itself), `tests/test_memory.py` (9 tests, fake `/recall` server). Checked with `claude -p --plugin-dir .` against the local app: the model receives the block, the first-run line shows as a notice ("UserPromptSubmit says: …"), the hook takes ~170 ms, and the three commands work. `exclude_paths` isn't in yet (capture guard, phase 3).

- [x] Repo root with `.claude-plugin/plugin.json`: name `infranodus-memory`, `mcpServers.infranodus` (same as the others, so it's merged), `userConfig.api_key` (`sensitive: true`, `required: true`, so Claude Code asks for it at install), `userConfig.exclude_paths` (globs, optional)
- [x] `hooks/hooks.json` with `UserPromptSubmit` only for now
- [x] `hooks/memory.py` (stdlib only, like `infranodus/scripts/repo2statements.py` in the skills repo): on the first prompt of a session, call `/api/v1/recall` with a 2 s timeout and return `hookSpecificOutput.additionalContext`; on any error or missing key, return nothing and exit 0
- [x] Project identity: git remote slug when available, else the directory name; must match the `project` that `get_project_learnings` uses
- [x] `~/.infranodus/memory.json`, the one local settings file for every client (design: "Where memory state lives"): `{ "off": [projects], "mode": "auto"|"review", "told": [projects] }`. Read it first in every hook; a missing or unreadable file means defaults (on, `auto`, nobody told yet)
- [x] Track "first prompt" per `session_id` in `~/.infranodus/`
- [x] First-run line: when the project isn't in `told` yet, show the user (a user-facing message, not only `additionalContext`) "InfraNodus memory is on for `<project>` → graph link. `/infranodus-memory:off` to stop for this project." Then add it to `told`
- [x] Invalid key: hooks do nothing; say so once in the first-run line
- [x] `/infranodus-memory:off` and `/infranodus-memory:on`: add or remove the project in `~/.infranodus/memory.json` (no server call). The graph is kept; deleting it is a separate, explicit action through the MCP `delete_graph` tool
- [ ] Version the plugin in `plugin.json` and tag releases; the skills marketplace entry points at this repo
- [ ] Release workflow: decide whether to build a zip (hooks don't work in Claude web; probably skip it)

## Phase 3: session upload and forget

> Built 2026-11-02 (not released), checked with real Claude Code sessions against a test instance of the app. **Changed from the design:** no capture hooks and no capture queue. Claude Code already writes the session to a transcript, and `PreCompact`/`SessionEnd` give its path, so the upload reads it then. That is exactly what step 2 tested (`trim.py` `trimmed2` on transcripts), needs no per-tool hook, and adds nothing to tool calls. Clients without a transcript (phase 5) will still need capture hooks.

- [x] `PreCompact` and `SessionEnd`: `memory.py hook-flush` checks the off switches, the project and the key, starts a detached `ingest-worker` and returns (~5 ms)
- [x] Worker: builds the excerpt (`hooks/excerpt.py`, the production `trimmed2`: commands run + trimmed turns, ~6k tokens, redacted) from the transcript lines after the last upload (`~/.infranodus/uploaded/<session>`), skips excerpts under 500 characters, posts to `/api/v1/ingest`; one worker per session at a time
- [x] Failed uploads (network, 429, 5xx) go to `~/.infranodus/queue/` and are retried first by the next worker (kept 7 days)
- [x] Record nothing when the project is in the `off` list, when the path matches `exclude_paths` (new optional setting), or in the home directory, temp folders, or a folder that is neither a git repo nor has a project marker
- [x] Redaction: API keys and tokens (common prefixes and long tokens), private key blocks, `key=value` secrets; text inside `<private>…</private>` is dropped
- [x] Off switches checked first: `INFRANODUS_MEMORY_DISABLE=1`, `INFRANODUS_MEMORY_DISABLE_CAPTURE=1` (recall only)
- [x] `/infranodus-memory:forget-last` → `/api/v1/memory/forget`
- [x] Show the recall's `saved` line once per session ("InfraNodus memory saved 3 learnings from your last session in <project> (/infranodus-memory:forget-last to undo)")
- [ ] `quotaPaused` notice (a quota refusal is currently queued and retried silently)
- [ ] Review mode (`mode` in `memory.json`, inbox, `/infranodus-memory:review`)

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

- [x] Hook unit tests: no key means no output and exit 0; a timeout means no output; only the first prompt per session triggers recall
- [ ] Timing tests: each capture hook under 50 ms and each ingest hook under 100 ms on a long fixture session; recall gives up at 2 s against a slow mock server; a session with Claude Code and the plugin is not measurably slower than without it
- [x] Upload tests: nothing is sent for a disabled or excluded project or a non-project folder; secrets are redacted; each upload covers only new lines; a failed upload is queued and retried
- [x] First-run line appears once per project; `/infranodus-memory:off` stops recall and upload
