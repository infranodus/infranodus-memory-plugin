# Step 2: extraction test results (2026-10-31)

Two runs. Run 1 compared trimmed vs full excerpts and two models. Run 2
applied the fixes from run 1 and is what the design now uses (see
"Run 2" at the end). Outcome: **trimmed excerpt + commands list, the v2 prompt
with structured output, and a small model are enough.**

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

# Run 2 (2026-10-31): fixes applied

## What changed

- `trim.py` mode `trimmed2`: the trimmed excerpt plus a **COMMANDS RUN** list
  of successful shell commands, deduplicated, at most ~1.5k tokens. Left out:
  read-only commands (`ls`, `cat`, `grep`, `git status`…), heredocs (they are
  file-editing scripts) and `cd dir &&` / `VAR=x;` prefixes.
- `ingest-prompt-v2.md`: a `project` field per statement; a rule against
  snapshots (versions, release state, branches, committed/uncommitted,
  "currently", counts); a `personal`/`environment` type for facts about the
  user's machine or agent; at least one `[[wikilink]]`; no statements about a
  tool used once in the session.
- `schema-v2.json` passed with `--json-schema` (structured output).
- Same 8 sessions, trimmed2 only, Haiku and Sonnet. Results in `out2/`
  (gitignored). Run with
  `PROMPT=ingest-prompt-v2.md OUT=out2 SCHEMA=schema-v2.json ./run.sh`,
  then `python3 collect.py out2`.

## Numbers

| model | statements | to another repo | personal | avg input tokens | cost per session | avg time |
|---|---:|---:|---:|---:|---:|---:|
| haiku | 77 | 26 | 5 | ~12.6k* | $0.004 | 18 s |
| sonnet | 51 | 16 | 1 | ~10.5k* | $0.041 | 7 s |

\* Includes the longer prompt and cached system tokens; the excerpts are
1.8–28k chars (about 0.5–7k tokens).

## Did the fixes work?

1. **Other repos: fixed.** The ai-frontend session's facts about
   `infranodus-app/lib/ai.js` now carry `project: infranodus-app` (13 of 15
   with Haiku), the mcp-server session's GraphRAG findings go to
   infranodus-app, and pricing-table facts go to infranodus-web and
   keywordgraph-web. Statements about the widget's own code stayed in
   ai-frontend. No invented project names.
2. **Snapshots: mostly fixed.** Gone: "currently gpt-6.1-terra", "uncommitted
   on branch…", "working tree holds…". A few numbers remain, mostly from
   Sonnet ("should pass 87/87", "default tag v1.7.3", "~19k users", "all 15
   pages"). Acceptable; supersession handles the rest.
3. **Environment: fixed.** "auto mode blocks `gh pr merge`" and "the shell's
   cwd resets" came out as `personal/environment`, none in learnings.
4. **Malformed output: fixed.** 16 of 16 runs returned valid statements
   through the schema. One leftover: Haiku sometimes uses type `fact` with
   kind `learning`; tighten the schema so types depend on kind.

**Commands list:** it brought back how-to knowledge trimmed lost in run 1:
"starting the server with `pnpm run dev` applies pending migrations through
`runMigrations`" (legal-help), "run `scripts/recomputeProfiles.js` in dry-run
mode", "run `npm run build` so the challenger arm's generated nav updates",
"React views only change after `npm run webpack:production`".

## Model: the result flipped

With the v2 prompt **Sonnet became too strict**: 51 statements against 73 in
run 1, 1 statement for legal-help (Haiku: 10 good ones) and 2 for the
mcp-server session (Haiku: 8, all correct). **Haiku** produced more, with
equal quality per statement, and the facts I checked against the code were
right: FREE file cap 500 KB and Cloud PDF cap 2 MB
(`lib/planEntitlements.js`, the fact it got wrong in run 1), the
`fileSize > fileSize >` typo in `routes/imports/csv.js`, `runMigrations` in
`apps/server/src/db.ts`, `REMINDER_CHECK_INTERVAL_SEC` default 300.

Precision (hand-checked, my judgement): Haiku about 9 in 10 kept; Sonnet
similar per statement but misses a lot. Remaining drops: statements about the
Understand-Anything tool in infranodus-apis (rule 7 not followed by either
model), a few numbers.

**Recommendation:** a small, cheap model with the v2 prompt, about $0.004 per
session. In `/ingest` that means trying a small model from InfraNodus's list
(e.g. gpt-5.4-mini) against claude-sonnet-5 on these 8 sessions before
picking the default. That check needs the endpoint, so it moves to step 5.

## Decisions recorded in the design (Q2 closed)

- The hook pre-trims to ~6k tokens and adds the commands list (~1.5k tokens).
- `/ingest` uses structured output; each statement has `project`, `kind`,
  `type`; other-repo statements go to that repo's graph only if memory is on
  there; `personal` waits for phase 4.
- The default model is chosen from InfraNodus's list once `/ingest` exists.
