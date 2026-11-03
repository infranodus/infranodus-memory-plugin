# infranodus-memory-plugin

The `infranodus-memory` plugin: automatic memory for coding agents, stored as
InfraNodus knowledge graphs in your own account. On the first prompt of a
session it recalls what earlier sessions learned about the project; at the end
of a session it saves new learnings. Because memory is a graph, recall can also
say what the memory is missing.

Runs in **Claude Code**, **Codex** (OpenAI) and **Grok Build** (xAI) from the
same files: one `hooks/hooks.json`, one hook runtime, a Claude Code manifest
(`.claude-plugin/`), a Codex manifest (`.codex-plugin/`, `.mcp.json`,
`.agents/plugins/marketplace.json`), and Grok's Claude Code compatibility.

**Status:** the full cycle works (saving and recall) in Claude Code, not
released yet. Codex support is built on the documented hook and rollout
formats and tested against recorded sessions; Grok Build support is built on
its published hook contract and not yet run against the real client (see
"Grok Build" below for what is verified and what is not).

## Install

### Claude Code

```
/plugin marketplace add infranodus/infranodus-memory-plugin
/plugin install infranodus-memory@infranodus-memory-dev
```

From a local clone: `/plugin marketplace add ~/path/to/infranodus-memory-plugin`,
then the same install line. Claude Code asks for your API key. Later the plugin
is also listed in the InfraNodus skills marketplace.

### Codex (OpenAI)

```
codex plugin marketplace add infranodus/infranodus-memory-plugin
```

Then install `infranodus-memory` from the marketplace in the Codex app or the
`/plugins` screen of the CLI, and trust its three hooks in `/hooks` (Codex
skips untrusted hooks). Codex has no plugin settings screen, so set the API
key once, from any project folder:

```
python3 ~/.codex/plugins/<path-to>/infranodus-memory/hooks/memory.py set-key YOUR_INFRANODUS_API_KEY
```

or export `INFRANODUS_API_KEY` in your shell. The key is kept in
`~/.infranodus/memory.json` (mode 600). The plugin's `.mcp.json` adds the
InfraNodus MCP server (OAuth) for the `recall` and `optimize` skills. Codex runs
the same hooks as Claude Code, with the same payload, and its session rollout
is read as the transcript; its `SessionEnd` hooks are limited to 3 s, which the
upload hook meets by handing the work to a background process in about 5 ms.

### Grok Build (xAI)

Grok loads Claude Code plugins, marketplaces and hooks as they are, so install
the Claude Code plugin (the marketplace line above, or `grok --plugin-dir
~/path/to/infranodus-memory-plugin`), trust the hooks with `/hooks-trust`, and
set the key with `set-key` or `INFRANODUS_API_KEY` as for Codex. Grok sends
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

## What it does

- **On the first prompt of a session** in a project, it sends the prompt and
  the project name to InfraNodus (`/api/v1/recall`) and gives Claude up to 5
  related learnings from the project's `learn-<project>` graph: the direct
  matches, then learnings linked to them through a shared concept, plus at most
  one gap the memory doesn't cover. Later prompts send nothing.
- **At the end of a session** (and before a compaction), it trims what
  happened (your prompts, Claude's final answers, failed tool calls, files
  edited, commands that worked; secrets and `<private>…</private>` text
  removed) and sends it to InfraNodus (`/api/v1/ingest`), which extracts the
  durable learnings into `learn-<project>`, creating it the first time. This
  runs in the background and never delays exit or compaction.
- **The next session** tells you once what was saved: "InfraNodus memory
  saved 3 learnings from your last session (/infranodus-memory:forget-last to
  undo)."
- **The first time in a project**, it tells you once: "InfraNodus memory is on
  for `<project>` → graph link."
- **It never slows Claude down:** a 2 s limit on the one call; on any error,
  timeout or missing key it does nothing and says nothing.
- **Not a project, nothing sent:** your home folder, temp folders and folders
  without a git repo or project file are skipped.

## Commands

| Command | What it does |
|---|---|
| `/infranodus-memory:off` | Turn memory off for the current project on this machine: nothing is recalled or sent. The graph is kept |
| `/infranodus-memory:on` | Turn it back on |
| `/infranodus-memory:status` | Show the project name, whether memory is on, and whether the key is set |
| `/infranodus-memory:save` | Save this session now instead of at its end. Claude also runs it when you ask in plain words ("save what we learned to memory") |
| `/infranodus-memory:optimize [learnings \| <topic> \| claude \| claude-mem \| mem0 \| all]` | Analyse the project's memory with InfraNodus `optimize_knowledge_base`: its InfraNodus learnings and topic graphs, and also Claude's own memory notes, claude-mem or mem0 when present (sent as they are, not stored). With several, it asks which. Then it proposes statements that bridge the gaps it finds and saves only the ones you approve. Needs the InfraNodus MCP server authenticated in `/mcp` |
| `/infranodus-memory:recall <concept or question>` | Look something up in memory mid-session, following the graph's links: for a concept, what it is connected to by hop distance and the learnings on those links; for a question, the most relevant learnings, including ones linked through another concept. Claude also runs it when you ask what memory says about something. Needs the InfraNodus MCP server authenticated in `/mcp` |
| `/infranodus-memory:forget-last` | Remove the learnings saved from the last session |

They are namespaced, so they don't clash with Claude Code's own `/memory`.
`INFRANODUS_MEMORY_DISABLE=1` turns everything off;
`INFRANODUS_MEMORY_DISABLE_CAPTURE=1` keeps recall but sends no sessions.

## Settings and local files

- `api_key` (required): your InfraNodus API key, asked for at install and kept
  in your system's secure store. Change it later in `/plugin`. Codex and
  Grok have no plugin settings: there the hooks read `INFRANODUS_API_KEY`
  or the key stored by `hooks/memory.py set-key` (`clear-key` removes it).
- `api_base` (optional): only for your own InfraNodus server.
- `save` (optional): what sessions save. `both` (the default), `learnings`
  (how to work in each project) or `memories` (facts about clients,
  companies, cases, each in its own `memory-<topic>` graph).
- `exclude_paths` (optional): folders where memory never runs, e.g.
  `~/clients/*, ~/private`.
- `~/.infranodus/memory.json`: the projects turned off, the projects you
  were already told about, and the API key when set with `set-key`. Kept outside the project so a setting is never
  committed for your teammates.
- `~/.infranodus/sessions/`, `~/.infranodus/uploaded/`: which sessions already
  had their recall, and how far each was uploaded.
- `~/.infranodus/queue/`: uploads that failed, retried later (kept 7 days).
- `~/.infranodus/timings.log`: how long each hook run took.

## Clients

| | Claude Code | Codex | Grok Build |
|---|---|---|---|
| Manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` + `.mcp.json`, catalog in `.agents/plugins/marketplace.json` | the Claude Code manifest, through Grok's compatibility layer |
| Hooks | `hooks/hooks.json` | the same file (`${CLAUDE_PLUGIN_ROOT}` is set by Codex too) | the same file |
| Payload | `session_id`, `cwd`, `prompt`, `transcript_path` | the same | `hookEventName`, `sessionId`, `cwd`, `workspaceRoot`, `GROK_*` variables |
| Recall reaches the model through | `additionalContext` | `additionalContext` | `.grok/rules/infranodus-memory.md` (stdout is ignored) |
| Transcript read for the upload | Claude Code `.jsonl` | Codex rollout `.jsonl` | only if passed as `transcript_path` |
| API key | plugin setting | `INFRANODUS_API_KEY` or `set-key` | `INFRANODUS_API_KEY` or `set-key` |
| Skills' `!` preamble | runs | shown as text; the skill tells the agent the command to run | shown as text, same |
| `client` sent to the API | `claude-code` | `codex` | `grok` |

## Development

```
python3 -m unittest discover -s tests          # hook and command tests (no network)
claude --plugin-dir .                          # load the plugin from this folder
```

For a local InfraNodus server, set `CLAUDE_PLUGIN_OPTION_API_KEY` and
`CLAUDE_PLUGIN_OPTION_API_BASE=http://localhost:3000/api/v1` in the shell
before starting `claude --plugin-dir .`.

- Build plan, with links to the related plans in other repos: [`docs/plan.md`](docs/plan.md)
- Tasks for this repo: [`docs/todo/memory-system.md`](docs/todo/memory-system.md)
- Design: `mcp-server-infranodus/docs/drafts/infranodus-memory-system.md`
