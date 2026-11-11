# InfraNodus Graph Memory plugin

The `infranodus-memory` plugin: memory for coding agents, stored as InfraNodus
knowledge graphs in your own account. Because memory is a graph, recall is
GraphRAG (it follows the links between concepts by hop distance, so it also
finds learnings reachable only through an intermediate concept) and can say
what the memory is missing.

It works in two ways:

- **Commands, through your InfraNodus connector.** `/infranodus-memory:recall`,
  `:save`, `:remember`, `:optimize` and `:dream` use the InfraNodus MCP tools
  you already have connected. No setup, no API key.
- **Automatic memory, with an optional API key.** On the first prompt of a
  session it recalls what earlier sessions learned about the project; at the
  end of a session it saves new learnings.

The plugin brings no MCP server of its own, so it never hides or duplicates
the InfraNodus connector or server you have.

## What is sent and when

Without an API key the plugin sends nothing by itself. The commands only do
what you ask, through your InfraNodus connector.

With an API key:

- **First prompt of a session:** that prompt and the project name, to recall
  related learnings. Later prompts send nothing.
- **End of a session and before a compaction:** a trimmed excerpt of the
  session (your prompts, Claude's final answers, failed tool calls, files
  edited, commands that worked). Secrets and `<private>…</private>` text are
  removed before it leaves your machine.
- **Where it goes:** to infranodus.com only, into graphs in your own
  InfraNodus account (`learn-<project>`, and `memory-<topic>` for facts about
  clients or subjects). The key is sent nowhere else.
- **Not sent:** anything from your home folder, temp folders, folders without
  a git repo or project file, and folders listed in `exclude_paths`.
- **Turning it off:** `/infranodus-memory:off` for one project;
  `INFRANODUS_MEMORY_DISABLE=1` for everything;
  `INFRANODUS_MEMORY_DISABLE_CAPTURE=1` keeps recall but sends no sessions;
  removing the key in `/plugin` stops all of it.
- **Kept on your machine,** in `~/.infranodus/`: which projects are off, which
  sessions were recalled and uploaded, uploads waiting for a retry, and a
  timing log. The key is not stored there.

## Install

### Claude Code

```
/plugin marketplace add infranodus/plugins
/plugin install infranodus-memory@infranodus-plugins
```

No setup is required. Connect the InfraNodus connector (claude.ai Settings →
Connectors, or `claude mcp add --transport http infranodus https://mcp.infranodus.com`)
and the commands work. The install dialog offers three optional fields; leave
them empty, or enter an API key from https://infranodus.com/api-access to turn
on automatic memory. You can add or remove the key later in `/plugin`.

[`infranodus/plugins`](https://github.com/infranodus/plugins) is the marketplace
for InfraNodus plugins; it also lists the core `infranodus` plugin (the
`/infranodus` skill). Straight from this repo instead:
`/plugin marketplace add infranodus/infranodus-memory-plugin`, then
`/plugin install infranodus-memory@infranodus-memory`; from a local clone,
`/plugin marketplace add ~/path/to/infranodus-memory-plugin` and the same
install line. The skills have their own marketplace,
[`infranodus/skills`](https://github.com/infranodus/skills).

### Other clients (experimental)

Claude Code is the supported client. The same files also load in Codex
(OpenAI) and Grok Build (xAI); that support is built on their published hook
formats and not tested against every release. See
[`codex/README.md`](https://github.com/infranodus/infranodus-memory-plugin/blob/master/codex/README.md)
in the repository.

## What automatic memory does

With an API key set:

- **On the first prompt of a session** in a project, it sends the prompt and
  the project name to InfraNodus (`/api/v1/recall`) and gives Claude up to 5
  related learnings from the project's `learn-<project>` graph: the direct
  matches, then learnings linked to them through a shared concept, plus at most
  one gap the memory doesn't cover. Up to two of the five are learnings a
  dream marked `core`, given whatever the prompt is. Later prompts send
  nothing.
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
- **It never slows Claude down:** a 2 s limit on the one call; on any error
  or timeout it does nothing and says nothing.
- **Without an API key** none of the above runs and nothing is sent. The
  first prompt in a project says once: "InfraNodus memory: add an API key in
  /plugin to turn on automatic memory for `<project>`."
- **Not a project, nothing sent:** your home folder, temp folders and folders
  without a git repo or project file are skipped.

## Commands

| Command | What it does |
|---|---|
| `/infranodus-memory:recall <concept or question>` | Look something up in memory mid-session, following the graph's links: for a concept, what it is connected to by hop distance and the learnings on those links; for a question, the most relevant learnings, including ones linked through another concept. Claude also runs it when you ask what memory says about something |
| `/infranodus-memory:remember <what>` | Save specific content you name (rules, a list, a fact, a decision) to memory, one statement per item. Claude also runs it when you say "remember this" or "save these to InfraNodus" |
| `/infranodus-memory:save` | Save what this session learned now instead of at its end. Claude also runs it when you ask in plain words ("save what we learned to memory") |
| `/infranodus-memory:optimize [learnings \| <topic> \| claude \| claude-mem \| mem0 \| all]` | Analyse the project's memory with InfraNodus `optimize_knowledge_base`: its InfraNodus learnings and topic graphs, and also Claude's own memory notes, claude-mem or mem0 when present (sent as they are, not stored). Then it proposes statements that bridge the gaps it finds and saves only the ones you approve |
| `/infranodus-memory:dream [area or concept]` | Consolidate the project's learnings. Claude replays up to 30 of them, the oldest unchecked ones first, against the repo and the transcripts of the sessions they came from, then shows one plan: which to correct, which to retire as outdated or duplicate, which gaps to bridge, and which few to mark `core` so that every session gets them. Nothing changes until you approve it. Retired learnings are kept in the graph, left out of recall. Each dream goes on where the last one stopped |
| `/infranodus-memory:forget-last` | Remove the learnings automatic memory saved from the last session |
| `/infranodus-memory:status` | Show the project name, whether memory is on, whether a key is set, whether the InfraNodus tools are available, and which features are active |
| `/infranodus-memory:off`, `:on` | Turn automatic memory off or back on for the current project on this machine. The graph is kept |

What each command needs:

| Command | InfraNodus connector | API key, no connector | Neither |
|---|---|---|---|
| `recall` | works | works when you type the command | asks you to connect the connector |
| `remember`, `optimize`, `dream` | work | need the connector | ask you to connect the connector |
| `save` | works (with a key it uploads the session, otherwise Claude writes the learnings) | works when you type the command | asks you to connect the connector |
| `forget-last` | needs the key | works | says it needs the key |
| `status`, `off`, `on` | work | work | work |

A command is never given the API key. When you type one, a hook of the plugin
does the part that needs the key and hands Claude the result.

They are namespaced, so they don't clash with Claude Code's own `/memory`.

## Settings and local files

- `api_key` (optional): your InfraNodus API key, kept in your system's secure
  store. It turns on automatic memory. Add, change or remove it in `/plugin`.
- `save` (optional): what sessions save. `both` (the default), `learnings`
  (how to work in each project) or `memories` (facts about clients,
  companies, cases, each in its own `memory-<topic>` graph).
- `exclude_paths` (optional): folders where memory never runs, e.g.
  `~/clients/*, ~/private`.
- `~/.infranodus/memory.json`: the projects turned off and the projects you
  were already told about. Kept outside the project so a setting is never
  committed for your teammates.
- `~/.infranodus/sessions/`, `~/.infranodus/uploaded/`: which sessions already
  had their recall, and how far each was uploaded.
- `~/.infranodus/queue/`: uploads that failed, retried later (kept 7 days).
- `~/.infranodus/timings.log`: how long each hook run took.

## Development

```
python3 -m unittest discover -s tests          # hook and command tests (no network)
claude plugin validate . --profile directory   # manifest and plugin directory checks
claude --plugin-dir .                          # load the plugin from this folder
```

For a local InfraNodus server, start Claude Code with
`INFRANODUS_API_BASE=http://localhost:3000/api/v1` in the shell and set the
key in `/plugin`. The key is only sent to infranodus.com or to a server on
this machine; any other address is refused.

- Build plan and tasks: `docs/plan.md` and `docs/todo/` in the
  [repository](https://github.com/infranodus/infranodus-memory-plugin)
- The copy for Anthropic's plugin directory: `scripts/release-directory.sh`
- Design: `mcp-server-infranodus/docs/drafts/infranodus-memory-system.md`
