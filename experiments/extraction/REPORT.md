# Step 2: extraction test results (2026-10-31)

**Question:** can one AI call turn a coding session into memory worth keeping,
with no human review (auto mode)? And should the hook send a trimmed excerpt
(~6k tokens) or the full session?

**Short answer:** yes. Most statements are worth keeping in every setup tested.
Trimmed holds up: it finds most of the key learnings at a tenth of the cost.
It misses some "how to run / how to test" knowledge, which lives in successful
tool calls that trimming drops. Four fixes are needed before Phase 3 (below);
none needs a redesign.

## Setup

- 8 recent sessions from 8 different projects (`sessions.txt`): infranodus-app
  (×2), infranodus-web, legal-help, InfraNodus-Skills, infranodus-ai-frontend,
  infranodus-apis, mcp-server-infranodus. Raw transcripts 1.4–6.7 MB.
- `trim.py` builds two excerpts per session, redacted:
  - **trimmed** (what the capture hooks would record): user prompts, the final
    answer of each turn, failed tool calls, files edited; most recent turns
    kept up to ~6k tokens.
  - **full**: everything readable (all agent text, every tool call and result,
    each result cut at 3k chars), capped at ~100k tokens.
- `ingest-prompt.md`: one prompt, output = JSON list of
  `{kind: learning|personal|topic, type, statement}`.
- Models: Claude Haiku (cheap) and Claude Sonnet, via `claude -p` with hooks,
  tools and MCP off (`run.sh`). 32 runs. `collect.py` builds the tables;
  `out/review.md` has every statement (gitignored, it quotes private sessions).

## Numbers

| mode | model | statements | personal | avg input tokens | cost per session | avg time |
|---|---|---:|---:|---:|---:|---:|
| trimmed | haiku | 75 | 4 | 6,485 | $0.003 | 14 s |
| trimmed | sonnet | 73 | 1 | 6,464 | $0.035 | 6 s |
| full | haiku | 83 | 4 | 62,459 | $0.031 | 14 s |
| full | sonnet | 93 | 1 | 62,438 | $0.27 (up to $0.68) | 11 s |

Topic memory was never produced, which fits v1 (topic statements are dropped).

## What was good (all four setups)

- Concrete and anchored: file paths, function names, env vars, commands.
  "Running `scripts/recomputeProfiles.js` locally without dry-run writes to
  production…", "`gpt-6.1-sol` rejects `reasoning_effort: 'none'` with HTTP 400…".
- Decisions come with reasons, as the prompt asks: "FREE file cap is 500 KB and
  Cloud PDF 2 MB so that upgrading always raises both limits…".
- Almost no session diary: 1–2 borderline lines per setup out of 73–93.
- No secrets leaked. Env var names appear, values don't.
- Personal facts went into `personal`, not learnings. Haiku's personal items
  were accurate (they match the user's own memory notes: one clear
  recommendation, no commits unless asked, confirm publishing step by step).

## Trimmed vs full

Trimmed found most of the key learnings in 7 of 8 sessions. What it missed is
**workflow knowledge that only shows in successful tool calls**:

- legal-help: "new agents need a role in `AGENT_ROLES` + registry + prompt +
  `MODEL_<ROLE>` env entries", "generate migrations with `drizzle-kit generate`"
- ai-frontend: "run `lib/ai.js` in tests with `babel-node`, not `node`"
- infranodus-apis: a session that was one `/understand` command had a 482-char
  trimmed excerpt; trimmed got 2 statements about the tool, full got a useful
  map of the codebase.

**Cheap fix:** add a **"commands run"** list to the trimmed excerpt (successful
Bash commands, deduplicated, ~150 chars each, ~1–2k tokens). That carries the
how-to knowledge without the tool output. Keep trimming as the default (your
call in step 1), re-test with this added.

## Haiku vs Sonnet

- **Sonnet** was more consistent: more `[[entities]]`, no empty results, and
  no factual errors in the one statement I checked against code.
- **Haiku** returned **0 statements** for infranodus-web (trimmed), where
  Sonnet found 7 good ones, and wrote one **wrong fact** (FREE PDF cap "2 MB";
  the code says 1 MB, `lib/planEntitlements.js:40`). It's 10× cheaper.
- Recommendation: a Sonnet-class model for ingest. On trimmed excerpts that's
  about $0.035 per session, one call per session.

## Problems to fix before Phase 3

1. **Statements about other repos.** Sessions often touch neighbouring repos.
   The ai-frontend session produced mostly facts about `infranodus-app/lib/ai.js`;
   the infranodus-app session produced facts about infranodus-web and
   infranodus-backend. Saved into the cwd project's graph, they'd be in the
   wrong place. Fix: a `project` field per statement; write it to that
   project's graph if memory is on there, otherwise drop it.
2. **Snapshot facts that go stale.** "currently gpt-6.1-terra", "released at
   v1.8.0", "the reminder work is uncommitted on branch feat/reminders", "the
   infranodus-web working tree holds unrelated uncommitted work". Fix: a prompt
   rule against version numbers, branch or commit state and "currently"; rely
   on supersession for the rest.
3. **Environment traps, not project traps.** "zsh doesn't word-split unquoted
   variables", "the shell's cwd resets", "auto mode denies `gh pr merge`". True,
   but about the user's machine and agent, so they'd repeat in every project
   graph. Fix: classify as `personal` (type `environment`) or drop.
4. **Malformed output.** Sonnet broke the JSON in 3 of 32 runs (an extra `","`);
   4 items had the type in the `kind` field (`trap/trap`, `question/question`).
   Fix: use structured output (a JSON schema / tool call) in `/ingest`, never
   free-text parsing.

Smaller: some statements have no `[[wikilinks]]` (require at least one);
statements about a tool used in the session (the understand-anything
dashboard) rather than the project.

## Precision (hand-checked, my judgement)

Counting a statement as "keep" if it would help a later session in that
project and is correctly attributed:

- trimmed / Sonnet: about 8 in 10 kept. Most drops are problem 1 (other repo)
  or 2–3 (snapshot, environment).
- trimmed / Haiku: a bit lower, plus the one empty result and the wrong fact.

With fixes 1–3 most of the drops become either correctly routed or filtered.

## Next

1. Apply fixes 1–4 to the prompt and add "commands run" to `trim.py`.
2. Re-run on the same 8 sessions (Sonnet, trimmed) and compare.
3. If it holds, record in the design: trimmed excerpt + commands run, a
   Sonnet-class model, structured output, the `project` field per statement.
