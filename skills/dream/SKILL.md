---
name: dream
description: Consolidate the InfraNodus Graph Memory of the current project. Replays a batch of the project's saved learnings against the repo and the session transcripts they came from, then corrects the ones that are wrong, retires the outdated ones, merges the ones that say the same thing, bridges gaps between clusters, and promotes the few that every session should see. Changes are applied only after the user approves the plan. Use when the user asks to dream, consolidate, clean up, verify or prune their memory or learnings. To only find gaps and add statements, use /infranodus-memory:optimize.
argument-hint: "[area or concept to focus on]"
allowed-tools: Read, Grep, Glob
---

## Memory here

When the user types this command, the plugin's hook puts a block starting with `[infranodus-memory]` into your context: the project name, its learnings graph, the memory graphs when an API key is set, and the folder that holds this project's session transcripts.

If no `[infranodus-memory]` block is in your context, the hook did not run. In Codex or Grok Build, which have no such hook, run `python3 <plugin root>/codex/key.py dream` from the project folder (the plugin root is the folder two levels above this file) and use its output as the block.

Without a block, the project name is the name of the git remote `origin` (the last part of its URL, without `.git`), else the name of the repository's folder; its learnings graph is `learn-<project>`.

This command works through the InfraNodus MCP tools, from whatever InfraNodus server or connector is connected (with several, the one for infranodus.com). If `get_project_learnings` or `update_statements` isn't available, say "Connect the InfraNodus connector to consolidate memory." and stop.

## What a dream is for

Learnings are written at the end of a session, by a model that saw only that session. Some are wrong from the start, some go out of date as the code changes, and several sessions say the same thing in different words. A dream looks back over them with the repo and the transcripts as the ground truth. It changes the project's learnings graph only; topic and personal memory have no ground truth here and are left alone.

A dream should leave the memory smaller or the same size, and more correct. It is not a reason to add statements.

## What to do

1. **Choose what to replay: at most 30 statements.** Read the memory with `get_project_learnings` for the project: once with no prompt (the overview and the newest learnings), once each with `type: "trap"` and `type: "location"`, `limit: 50`. If the user named an area or concept (`$ARGUMENTS`), also call it with that as `entity` and `hops: 2`, and replay only what those calls return for it. Each learning comes with its `categories` and `createdAt`.

   Leave out any statement with a `dream-<date>` category less than 30 days old: an earlier dream checked it. Among the rest, take first:
   - statements about the overview's main concepts (a mistake there spreads furthest);
   - `location` and `trap` statements that name files, functions, commands or settings (they go out of date fastest);
   - the oldest ones.

   If the graph has no learnings, say there is nothing to consolidate yet and stop.

2. **Check each statement against the ground truth.** One verdict per statement:
   - **For anything the repo can show** (where something lives, what a function does, a command, a setting, a convention): look. Find each named `[[entity]]` with Glob and Grep and read the code. A file or symbol that no longer exists, or that no longer does what the statement says, makes the statement outdated or wrong.
   - **For what the repo can't show** (why a decision was made, what went wrong first, an approach): the statement's `session-<id>` category names the session it came from, and that session's transcript is `<transcripts folder>/<id>.jsonl`. Search that file with Grep for the statement's entities and read around the hits. Never read a whole transcript.
   - Verdicts: **holds**, **wrong** (and you can say what is right), **outdated** (true once, the code moved on), **duplicate** (says the same as another statement in different words: keep the more precise one), **can't tell** (neither source settles it). A statement you can't check stays as it is. Never rewrite one on a guess.

   Statements that begin with "Confirmed again:" are deliberate: each one raises the weight of a learning that came up again. They are not duplicates. Leave them.

3. **Look for what is missing.** Call `optimize_knowledge_base` with `graphName` set to the learnings graph, `focus: "procedural"`, `includeLatent: false`. For the clusters it reports as unconnected, propose a statement that bridges two of them only where the repo or a transcript shows the relation is real, with at least two `[[wikilinks]]`, one fact, under 300 characters, and a type (location, trap, convention, decision with its reason, workflow, question, approach). Propose no more bridges than the number of statements this dream retires, and never more than 5; with nothing retired, at most 2.

4. **Choose the core.** Core statements carry the category `core`, and automatic recall gives them to every session whatever its first prompt is, two at a time. So the core is small: at most 7 statements in the whole graph. A statement belongs there when it held in step 2 (or in an earlier dream), a new agent would get something wrong without it, and it isn't about one narrow corner of the project. Prefer traps and conventions the overview shows as central or often confirmed. A statement that is `core` and no longer qualifies loses the label.

5. **Show the plan and ask once.** One numbered list, grouped:
   - **Correct:** the statement now → the statement after, and what in the repo or transcript shows it (a path and line, or the session).
   - **Retire:** the statement, and why (outdated, or a duplicate of which one).
   - **Add:** each bridge, its type, and the two areas it connects.
   - **Core:** what joins and what leaves.
   - One line: how many statements were checked, how many hold, how many you couldn't tell.

   Ask which changes to apply. Apply nothing without the user's answer. If every statement holds and nothing is missing, say so; step 6 then only records the check.

6. **Apply what the user approved,** with today's date as `dream-<YYYY-MM-DD>`. The user's approval of the plan is the approval for these calls, so each one is sent with `confirm: true`:
   - **Correct:** `update_statements` on the learnings graph, one call per statement: `query` set to the statement's current text, `replace: { pattern: <current text>, with: <new text> }`, `set: { addCategories: ["dream-<date>"] }`. The query also matches the "Confirmed again:" repeats of that statement, so they are corrected with it.
   - **Retire:** `update_statements`, one call per statement: `query` set to its text, `set: { addCategories: ["superseded", "dream-<date>"] }`. A superseded statement stays in the graph but is left out of recall, so retiring can be undone by removing the label. Never use `delete_statements` here.
   - **Add:** `add_project_learnings` with the project name, `statements`, `types`, `confirm: true`.
   - **Core:** `update_statements` with `statements` set to the texts that join and `set: { addCategories: ["core"] }`; another call with `set: { removeCategories: ["core"] }` for the ones that leave.
   - **Record the check:** one `update_statements` call with `statements` set to every statement that held and `set: { addCategories: ["dream-<date>"] }`, so the next dream skips them.

   If a call reports fewer matches than expected, say which statement was not changed instead of trying another selector.

7. **Report** in a few lines: checked, corrected, retired, added, core now. Then list each correction as before → after, because the earlier text of a corrected statement is kept nowhere else. Say that retired statements can be brought back by removing their `superseded` category in InfraNodus.
