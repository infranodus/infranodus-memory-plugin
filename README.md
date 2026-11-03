# infranodus-memory-plugin

The `infranodus-memory` plugin: automatic memory for coding agents, stored as
InfraNodus knowledge graphs in your own account. On the first prompt of a
session it recalls what earlier sessions learned about the project; at the end
of a session it saves new learnings. Because memory is a graph, recall can also
say what the memory is missing.

**Status:** the full cycle works (saving and recall), not released yet.

## Install

```
/plugin marketplace add infranodus/infranodus-memory-plugin
/plugin install infranodus-memory@infranodus-memory-dev
```

From a local clone: `/plugin marketplace add ~/path/to/infranodus-memory-plugin`,
then the same install line. Claude Code asks for your API key. Later the plugin
is also listed in the InfraNodus skills marketplace.

## What it does

- **On the first prompt of a session** in a project, it sends the prompt and
  the project name to InfraNodus (`/api/v1/recall`) and gives Claude up to 5
  related learnings from the project's `learn-<project>` graph, plus at most one
  gap the memory doesn't cover. Later prompts send nothing.
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
| `/infranodus-memory:forget-last` | Remove the learnings saved from the last session |

They are namespaced, so they don't clash with Claude Code's own `/memory`.
`INFRANODUS_MEMORY_DISABLE=1` turns everything off;
`INFRANODUS_MEMORY_DISABLE_CAPTURE=1` keeps recall but sends no sessions.

## Settings and local files

- `api_key` (required): your InfraNodus API key, asked for at install and kept
  in your system's secure store. Change it later in `/plugin`.
- `api_base` (optional): only for your own InfraNodus server.
- `save` (optional): what sessions save. `both` (the default), `learnings`
  (how to work in each project) or `memories` (facts about clients,
  companies, cases, each in its own `memory-<topic>` graph).
- `exclude_paths` (optional): folders where memory never runs, e.g.
  `~/clients/*, ~/private`.
- `~/.infranodus/memory.json`: the projects turned off, and the projects you
  were already told about. Kept outside the project so a setting is never
  committed for your teammates.
- `~/.infranodus/sessions/`, `~/.infranodus/uploaded/`: which sessions already
  had their recall, and how far each was uploaded.
- `~/.infranodus/queue/`: uploads that failed, retried later (kept 7 days).
- `~/.infranodus/timings.log`: how long each hook run took.

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
