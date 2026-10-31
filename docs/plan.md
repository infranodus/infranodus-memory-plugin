# Plan: building the InfraNodus memory plugin

> Status: **plan, 2026-10-31.** Nothing implemented yet. The design (what the
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

- [ ] `infranodus-app`: `/api/v1/learnings/{enable,get,add}` and
      `/memory/{enable,add,get}`, with naming, dedup and consent markers moved
      out of `mcp-server-infranodus/src/utils/learnings.ts`
- [ ] `mcp-server-infranodus`: learnings and memory tools call the new
      endpoints, same inputs and outputs; add `scope` and `topic` to the memory
      tools
- **Done when** the existing tool tests pass against mocks of the new endpoints
  and clients notice nothing. Deploy

## Step 4: phase 2, recall only, nothing written

- [ ] `infranodus-app`: `/recall` (p95 < 1.5 s) and `/memory/disable`
- [ ] This repo:
  - `.claude-plugin/plugin.json` with the shared `mcpServers.infranodus`
    entry and the `api_key` setting
  - `hooks/hooks.json` with `UserPromptSubmit` only
  - `hooks/memory_hook.py`: standard-library Python, 2 s timeout, exits 0
    with no output on any failure
  - the first-run line, `/memory off` and `/memory on`
- [ ] `Skills/InfraNodus-Skills`: marketplace entry pointing at this repo;
      extend `tests/split-test.sh`
- [ ] Test locally by loading the plugin from this folder, then install it
      from the marketplace
- **Done when** a new session in a project with an existing `learn-*` graph
  shows the recall block and the timing tests pass

## Step 5: phase 3, the full cycle

- [ ] `infranodus-app`:
  - `/ingest`: returns 202 at once, extracts in the background, a retried
    upload with the same `sessionId` writes nothing twice; uses the v2 prompt
    and schema from `experiments/extraction/`; default model picked by
    re-running the 8 test sessions through it
  - creates the learnings graph on the first ingest that yields statements;
    tags each statement with `session-<id>`
  - `/memory/forget`, quota pause, inbox for review mode
- [ ] This repo:
  - capture hooks writing to a local queue, with redaction and exclusion guards
  - background ingest worker on `PreCompact` and `SessionEnd`
  - `/memory forget-last` and `/memory review`
- [ ] `mcp-server-infranodus`: `review_memory` tool and `inboxCount`
- [ ] Before release: the skills README's "What gets uploaded and where" table
      and the InfraNodus privacy policy describe the default-on behaviour
- **Done when** a week of your own use on 2–3 projects saves things worth
  keeping. Then release

## Step 6: later

- [ ] Phase 4: personal memory; device login replacing the API key
- [ ] Phase 5: adapters for Codex CLI and Cursor, then installers
- [ ] Optional: the analytical-layer and importer edits from the comparison doc
