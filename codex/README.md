# Codex and Grok Build (experimental)

Claude Code is the supported client of the `infranodus-memory` plugin. The
same hook runtime also works in Codex (OpenAI) and Grok Build (xAI). Codex
support is built on the documented hook and rollout formats and tested
against recorded sessions; Grok Build support is built on its published hook
contract and not yet run against the real client.

These clients have no plugin settings screen, so the API key can't come from
one. `codex/key.py` finds it (the `INFRANODUS_API_KEY` variable, else the key
stored with `set-key`) and runs `hooks/memory.py` with it. Nothing in this
folder is used by Claude Code.

### Codex (OpenAI)

```
codex plugin marketplace add infranodus/plugins
```

(or `codex plugin marketplace add infranodus/infranodus-memory-plugin` for this
repo alone). Then install `infranodus-memory` from the marketplace in the Codex app or the
`/plugins` screen of the CLI, and trust its three hooks in `/hooks` (Codex
skips untrusted hooks). Codex has no plugin settings screen, so set the API
key once, from any project folder:

```
python3 ~/.codex/plugins/<path-to>/infranodus-memory/codex/key.py set-key YOUR_INFRANODUS_API_KEY
```

or export `INFRANODUS_API_KEY` in your shell. The key is kept in
`~/.infranodus/memory.json` (mode 600); `key.py clear-key` removes it. The
plugin's `mcp.json` adds the InfraNodus MCP server (OAuth) for the skills.
Codex runs its own hooks file, `codex/hooks.json`, which calls `codex/key.py`:
that finds the key and runs the same hook runtime as Claude Code
(`hooks/memory.py`) with the same payload. Its session rollout
is read as the transcript; its `SessionEnd` hooks are limited to 3 s, which the
upload hook meets by handing the work to a background process in about 5 ms.

### Grok Build (xAI)

Grok loads Claude Code plugins, marketplaces and hooks as they are, so install
the Claude Code plugin (the marketplace lines above, or `grok --plugin-dir
~/path/to/infranodus-memory-plugin`), trust the hooks with `/hooks-trust`, and
point its hooks at `codex/key.py` instead of `hooks/memory.py` (copy the three
entries of `codex/hooks.json` into your Grok hooks settings), then set the key
with `set-key` or `INFRANODUS_API_KEY` as for Codex. Grok loads the plugin's
own `hooks/hooks.json` as it is, and that file has no key outside Claude Code.
Grok sends
hooks a camelCase payload (`hookEventName`, `sessionId`, `cwd`,
`workspaceRoot`) and `GROK_*` variables; the runtime reads both. Because Grok
ignores what a hook writes to stdout, the recall is also written to
`<project>/.grok/rules/infranodus-memory.md`, a rules file Grok loads at session
start (so it is current from the next session on; add the file to
`.git/info/exclude` if you don't want it in the repo). Saving needs the
session transcript: Grok keeps sessions under `~/.grok/sessions/` in a format
its docs don't describe, so the upload runs only when Grok passes a
`transcript_path` the runtime can read; otherwise nothing is sent and nothing
breaks.

## Clients

| | Claude Code | Codex | Grok Build |
|---|---|---|---|
| Manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` + `mcp.json`, catalog in `.agents/plugins/marketplace.json` | the Claude Code manifest, through Grok's compatibility layer |
| Hooks | `hooks/hooks.json` | `codex/hooks.json` (`${CLAUDE_PLUGIN_ROOT}` is set by Codex too) | `hooks/hooks.json`, or the `codex/hooks.json` entries for a key |
| Payload | `session_id`, `cwd`, `prompt`, `transcript_path` | the same | `hookEventName`, `sessionId`, `cwd`, `workspaceRoot`, `GROK_*` variables |
| Recall reaches the model through | `additionalContext` | `additionalContext` | `.grok/rules/infranodus-memory.md` (stdout is ignored) |
| Transcript read for the upload | Claude Code `.jsonl` | Codex rollout `.jsonl` | only if passed as `transcript_path` |
| API key | plugin setting (optional) | `INFRANODUS_API_KEY` or `codex/key.py set-key` | the same, through `codex/key.py` |
| Typed commands | a hook runs the part that needs the key | the skill tells the agent to run `codex/key.py <command>` | the same |
| `client` sent to the API | `claude-code` | `codex` | `grok` |

