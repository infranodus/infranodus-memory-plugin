# Plan: building the InfraNodus memory plugin

> Status: **plan, 2026-10-31; revised 2026-11-02** after the consent model
> changed (memory state is the graph type; `/infranodus-memory:off` is local). Step 2
> done, step 3 built. The design (what the
> system does and why) is in the design doc; this is the order to build it in.
> Each step depends on the one before it, except step 2, which runs alongside
> step 3.

## Related plans in other repos

Paths are relative to this repo's root and assume the repos sit side by side in
`~/Software`.

| Repo | File | What it covers |
|---|---|---|
| `mcp-server-infranodus` | [`docs/drafts/infranodus-memory-system.md`](../../mcp-server-infranodus/docs/drafts/infranodus-memory-system.md) | **The design.** Three kinds of memory, the recall → capture → ingest cycle, API, consent, performance budgets, other clients, open questions |
| `mcp-server-infranodus` | [`docs/drafts/memory-tools-comparison-analysis.md`](../../mcp-server-infranodus/docs/drafts/memory-tools-comparison-analysis.md) | Comparison with other memory tools, popularity data, proposed edits (analytical layer, importers) not yet in the design |
| `mcp-server-infranodus` | [`docs/drafts/project-learnings-graph.md`](../../mcp-server-infranodus/docs/drafts/project-learnings-graph.md) | The existing project-learnings feature this builds on, including its consent rules |
| `mcp-server-infranodus` | [`docs/todo/memory-system.md`](../../mcp-server-infranodus/docs/todo/memory-system.md) | MCP tools moved onto the new endpoints, `scope`/`topic`, `enable_memory`, `review_memory` |
| `infranodus-app` | [`docs/todo/memory-system.md`](../../infranodus-app/docs/todo/memory-system.md) | The single implementation: `/api/v1/learnings/*`, `/memory/*`, `/recall`, `/ingest` |
| `infranodus-backend` | [`docs/custom-api-quota.md`](../../infranodus-backend/docs/custom-api-quota.md) | How `recall` (API call) and `ingest` (AI call) count against quota |
| `Skills/InfraNodus-Skills` | [`docs/todo/memory-system.md`](../../Skills/InfraNodus-Skills/docs/todo/memory-system.md) | Marketplace listing for this plugin, `split-test.sh`, edits to `project-learnings` and `infranodus` skills, README privacy table |
| this repo | [`docs/todo/memory-system.md`](todo/memory-system.md) | The plugin itself: hooks, recall, capture, ingest worker, other clients, tests |

## Step 1: lock in the design (about a day)

- [ ] Commit the design draft and the task lists in `mcp-server-infranodus`, `Skills/InfraNodus-Skills` and this repo
- [ ] Publish this repo on GitHub
- [x] Q1 decided (2026-10-31): **v1 recall uses only the project's learnings
      graph** (plus personal memory once phase 4 adds it). Topic graphs are
      not linked to projects and not searched by recall; the plugin doesn't
      write to them either. Topic memory stays available on demand through the
      MCP memory tools. Linking topics to projects (a `linkedTopics` marker in
      `learn-<project>`) can be added later without changing anything else
- [x] Q2 decided (2026-10-31, from step 2): the hook pre-trims to about 6k
      tokens plus a list of successful commands. The other open questions
      can wait

## Step 2: test extraction quality first (alongside step 3)

The biggest risk in the design. Auto mode writes without review, so precision
has to be good before step 5 ships. Needs no new code.

- [ ] Write the ingest prompt: extract short statements with `[[entities]]`,
      classify each as learning / memory / personal
- [ ] Run it on 5–10 real Claude Code transcripts from `~/.claude/projects/`
- [ ] Hand-check: no facts about the user in learnings, no trivia, decisions
      come with reasons, no "today I did X" diary lines
- **Done when** most statements are worth keeping. If not, fix the prompt now
- [x] First run done 2026-10-31: 8 sessions × trimmed/full × Haiku/Sonnet.
      Results in [`experiments/extraction/REPORT.md`](../experiments/extraction/REPORT.md):
      most statements worth keeping; trimmed finds most key learnings at a
      tenth of the cost but misses how-to knowledge from successful commands
- [x] Second run done 2026-10-31: commands list, `project` field, snapshot and
      environment rules, structured output. All four fixes work; a small
      model is enough with the v2 prompt. Q2 decided and recorded in the
      design (trimmed + commands list)

## Step 3: phase 1, one implementation (`infranodus-app`, `mcp-server-infranodus`)

- [x] `infranodus-app`: `/api/v1/learnings/{enable,get,add}` and
      `/memory/{enable,add,get}`, with naming, dedup and consent moved out of
      the MCP server
- [x] `mcp-server-infranodus`: learnings and memory tools call the new
      endpoints, same inputs and outputs; `scope`, `topic`, `language`,
      `enable_memory`
- Built 2026-11-02 and checked live against the local app; not deployed.
  Built with marker statements, which the consent model of 2026-11-02
  replaces (design: "Where memory state lives"), so before deploying:

### 3a. Memory state from the graph type (`infranodus-app`)

Done 2026-11-02, live-checked. `enable` creates the empty graph through the
backend's `contexts/graph`; two empty-graph failures fixed on the way (see the
app todo).

- [x] Find out how `enable` can create an empty graph of type `MEMORY`
      through the existing write path (or the smallest call that can)
- [x] State check from the cached graph list: the graph exists and is
      `MEMORY`. Legacy: a `learn-*` graph that isn't `MEMORY` counts if it has
      a `learnings-enabled` statement
- [x] Remove marker statements, `mode`, the `memory-disabled` marker,
      `/memory/disable` and `/memory/enable-project`; leave existing marker
      statements out of `get`
- [x] Update the tests (graph type, hand-made graph refused, legacy graph
      accepted, a learning mentioning a marker changes nothing); live check
      against the local app, including that `knownAreas` no longer shows a
      marker topic

### 3b. MCP server follows

- [x] Drop the `disabled` test and any `mode` mentions; full test suite;
      live run of every tool against the local app

### 3c. Ship

- [ ] Commit both repos (on request), deploy the app, then release the MCP
      server; never the other way round
- [ ] Ask before the optional cleanup: remove the old marker statements from
      the user's existing `learn-*` graphs with `update_statements` /
      `delete_statements`
- **Done when** the tool tests pass against mocks of the new endpoints,
  clients notice nothing, and production serves the new endpoints

## Step 4: phase 2, recall only, nothing written

- [x] `infranodus-app`: `/recall` (p95 < 1.5 s; 30–40 ms locally, no AI call): searches `learn-<project>`
      and `personal-<user>` when they exist as memory graphs; empty for a
      project with no graph; no on/off or "told" state on the server
- [x] This repo (built 2026-11-02, tested with `claude -p --plugin-dir .`):
  - `.claude-plugin/plugin.json` with the shared `mcpServers.infranodus`
    entry and the `api_key` setting
  - `~/.infranodus/memory.json` (off list, mode, projects already told),
    read first by every hook
  - `hooks/hooks.json` with `UserPromptSubmit` only
  - `hooks/memory_hook.py`: standard-library Python, 2 s timeout, exits 0
    with no output on any failure, and does nothing for a project in the
    off list
  - the first-run line, `/infranodus-memory:off` and `/infranodus-memory:on` (local only)
- [ ] Publish this repo on GitHub first (open in step 1; you)
- [ ] `Skills/InfraNodus-Skills`: marketplace entry pointing at this repo;
      extend `tests/split-test.sh`
- [ ] Test locally by loading the plugin from this folder, then install it
      from the marketplace
- **Done when** a new session in a project with an existing `learn-*` graph
  shows the recall block, a project in the off list shows nothing and sends
  nothing, and the timing tests pass

## Step 5: phase 3, the full cycle

Built 2026-11-02 and checked end to end with real Claude Code sessions against
a test instance of the app: a session's end uploads it, the app saves the
learnings, the next session recalls them with a "saved" line, and
`/infranodus-memory:forget-last` undoes it. The upload reads Claude Code's
transcript at `PreCompact`/`SessionEnd` instead of capture hooks (see the
plugin todo).

- [x] `infranodus-app`: `/ingest` (202 at once, background extraction with
      `claude-haiku-5-5` and the v2 prompt plus supersession, retried uploads
      write nothing twice, graph created on the first useful session,
      `session-<id>` tags), `saved` in `/recall`, `/memory/forget`
- [x] This repo: upload worker on `PreCompact` and `SessionEnd` (reads the
      transcript; redaction, exclusions, retry queue),
      `/infranodus-memory:forget-last`, the "saved" line, `exclude_paths`
- [ ] Default model: re-run the 8 test sessions through `/ingest` and compare
      `claude-haiku-5-5` with a model from InfraNodus's list (e.g.
      gpt-5.4-mini)
- [ ] Quota pause notice; review mode (inbox, `/infranodus-memory:review`)
- [ ] `mcp-server-infranodus`: `review_memory` tool and `inboxCount`
- [ ] Before release: the skills README's "What gets uploaded and where" table
      and the InfraNodus privacy policy describe the default-on behaviour
- **Done when** a week of your own use on 2–3 projects saves things worth
  keeping. Then release

## Step 6: later

- [ ] Phase 4: personal memory; device login replacing the API key
- [~] Phase 5: adapters for Codex and Grok Build built 2026-11-03 (manifests, payload normalization, Codex rollout parser, key without plugin settings); Cursor and installers open
- [ ] Optional: the analytical-layer and importer edits from the comparison doc
