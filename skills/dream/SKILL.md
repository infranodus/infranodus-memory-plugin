---
name: dream
description: Consolidate the InfraNodus Graph Memory of the current project. Replays a batch of the project's saved learnings against the repo and the session transcripts they came from, then corrects the ones that are wrong, retires the outdated ones, merges the ones that say the same thing, asks the questions that connect its insight clusters and answers them from the repo, and promotes the few that every session should see. Changes are applied only after the user approves the plan. With `transcend` as the first word it also looks outward: a few unverified ideas that link the memory to concepts beyond it, kept apart from the learnings and out of recall. Use when the user asks to dream, consolidate, clean up, verify or prune their memory or learnings, or to expand it with ideas from outside. To only find gaps and add statements, use /infranodus-memory:optimize.
argument-hint: "[transcend] [area or concept to focus on]"
allowed-tools: Read, Grep, Glob
---

## Memory here

When the user types this command, the plugin's hook puts a block starting with `[infranodus-memory]` into your context: the project name, its learnings graph, the memory graphs when an API key is set, and the folder that holds this project's session transcripts.

If no `[infranodus-memory]` block is in your context, the hook did not run. In Codex or Grok Build, which have no such hook, run `python3 <plugin root>/codex/key.py dream` from the project folder (the plugin root is the folder two levels above this file) and use its output as the block.

Without a block, the project name is the name of the git remote `origin` (the last part of its URL, without `.git`), else the name of the repository's folder; its learnings graph is `learn-<project>`.

This command works through the InfraNodus MCP tools, from whatever InfraNodus server or connector is connected (with several, the one for infranodus.com). If `get_project_learnings`, `optimize_knowledge_base` or `update_statements` isn't available, say "Connect the InfraNodus connector to consolidate memory." and stop.

## What a dream is for

Learnings are written at the end of a session, by a model that saw only that session. Some are wrong from the start, some go out of date as the code changes, and several sessions say the same thing in different words. A dream looks back over them with the repo and the transcripts as the ground truth. It changes the project's learnings graph only; topic and personal memory have no ground truth here and are left alone.

A dream should leave the memory smaller or the same size, and more correct. It is not a reason to add statements.

The one exception is asked for by name. When the arguments begin with `transcend`, or the user asks in their own words for ideas beyond the memory, the dream also looks outward after consolidating (see "Looking outward" below). Without that, it never does. Take the word `transcend` off the arguments before reading the rest as an area.

## What to do

1. **Read the shape of the memory.** Call `optimize_knowledge_base` with `graphName` set to the learnings graph, `focus: "procedural"`, `optimize: "optimize"`, `gapDepth: 0`, `includeLatent: false`. Keep the whole report for step 4. Two things in it matter here:
   - `state`: how the learnings are spread: **biased**, **focused**, **diversified** or **dispersed**. It is context for the user, with the report's `meaning`. Do not branch on it yourself.
   - `insightClusters`: one line per set, each naming one to three clusters and their role. InfraNodus has already chosen them for this state, the same clusters the app highlights on the graph: the ones whose connection improves this structure most. The first line is the set this call's `suggestions` are about.

   If the graph has no learnings, say there is nothing to consolidate yet and stop.

2. **Choose what to replay: at most 30 statements.** Call `get_project_learnings` for the project with no prompt, `order: "oldest"`, `uncheckedFor: 30` and `limit: 50`. It returns the overview (main concepts, areas, gaps) and the oldest learnings that no dream checked in the last 30 days, each with its `categories` and `createdAt`, plus `unchecked`: how many are left in the whole graph. Each dream starts where the last one stopped, so repeated dreams work through all of the memory.

   From those, take up to 30. When there are more than 30, take first:
   - statements about the overview's main concepts (a mistake there spreads furthest);
   - `location` and `trap` statements that name files, functions, commands or settings (they go out of date fastest);
   - then the oldest.

   If the user named an area or concept (`$ARGUMENTS`, without a leading `transcend`), call `get_project_learnings` with that as `entity` and `hops: 2` instead, and replay what it returns, leaving out statements with a `dream-<date>` category less than 30 days old.

   If the tool has no `order` input (an older InfraNodus server), call it with no prompt and `limit: 50`, and once more with `type: "trap"`, skip the statements with a recent `dream-<date>` category yourself, and tell the user in the report that only the newest learnings could be reached.

   If `unchecked` is 0, say every learning was checked in the last 30 days and stop, unless the user named an area.

3. **Check each statement against the ground truth.** One verdict per statement:
   - **For anything the repo can show** (where something lives, what a function does, a command, a setting, a convention): look. Find each named `[[entity]]` with Glob and Grep and read the code. A file or symbol that no longer exists, or that no longer does what the statement says, makes the statement outdated or wrong.
   - **For what the repo can't show** (why a decision was made, what went wrong first, an approach): the statement's `session-<id>` category names the session it came from, and that session's transcript is `<transcripts folder>/<id>.jsonl`. Search that file with Grep for the statement's entities and read around the hits. Never read a whole transcript.
   - Verdicts: **holds**, **wrong** (and you can say what is right), **outdated** (true once, the code moved on), **duplicate** (says the same as another statement in different words: keep the more precise one), **can't tell** (neither source settles it). A statement you can't check stays as it is. Never rewrite one on a guess.

   Statements that begin with "Confirmed again:" are deliberate: each one raises the weight of a learning that came up again. They are not duplicates. Leave them.

4. **Ask what connects the insight clusters.** Start with the first set in `insightClusters` from step 1. Which clusters are in it already follows from the state of the graph, so every state is handled the same way here.

   When the limit below leaves room for more than one addition, go on to the next set: call `optimize_knowledge_base` again with the same inputs and `gapDepth: 1`, then `2`, and use the first line of each report. Three sets at most.

   For each set:
   - **Write the question** that connects its clusters, as a new agent would ask it: "does X depend on Y?", "what has to happen to Y after X changes?". The report's `suggestions` are a lead, not the answer. Ask only about what the clusters already hold. A dream brings in no new topics.
   - **Try to answer it from the ground truth,** as in step 3: the repo first, then the transcripts of the sessions the clusters' statements came from.
   - **Answered:** propose the answer as a learning of the type it is (location, trap, convention, decision with its reason, workflow, approach).
   - **Not answered:** propose the question itself as a learning of type `question`, worded as what is not known ("Not established: whether [[X]] has to be rebuilt after [[Y]] changes"). The next session that touches either cluster then meets it and may settle it. Never answer a question on a guess.

   Each proposal names entities from both clusters with `[[wikilinks]]`, at least two, holds one fact and stays under 300 characters. Either kind links the clusters, so the next dream is given different sets.

   Propose no more of these than the number of statements this dream retires, and never more than 5; with nothing retired, at most 2.

   If the report has no `insightClusters` (an older InfraNodus server), work from its `missingBridges` in the same way, one set, and say so in the report.

5. **Choose the core.** Core statements carry the category `core`, and automatic recall gives them to every session whatever its first prompt is, two at a time. So the core is small: at most 7 statements in the whole graph. A statement belongs there when it held in step 3 (or in an earlier dream), a new agent would get something wrong without it, and it isn't about one narrow corner of the project. Prefer traps and conventions the overview shows as central or often confirmed. A statement that is `core` and no longer qualifies loses the label.

6. **Show the plan and ask once.** Start with one line on the state of the memory and what it means for this dream. Then one numbered list, grouped:
   - **Correct:** the statement now → the statement after, and what in the repo or transcript shows it (a path and line, or the session).
   - **Retire:** the statement, and why (outdated, or a duplicate of which one).
   - **Add:** for each set of insight clusters, the question, then either the answer with its type and what in the repo or transcript shows it, or the question as it will be saved.
   - **Core:** what joins and what leaves.
   - **Ideas from outside (unverified):** only when looking outward. Each idea, the concept in memory it starts from and the outside concept it brings in. Then any kept idea to retire, and why.
   - One line: how many statements were checked, how many hold, how many you couldn't tell.

   Ask which changes to apply. Apply nothing without the user's answer. If every statement holds and nothing is missing, say so; step 7 then only records the check.

7. **Apply what the user approved,** with today's date as `dream-<YYYY-MM-DD>`. The user's approval of the plan is the approval for these calls, so each one is sent with `confirm: true`:
   - **Correct:** `update_statements` on the learnings graph, one call per statement: `query` set to the statement's current text, `replace: { pattern: <current text>, with: <new text> }`, `set: { addCategories: ["dream-<date>"] }`. The query also matches the "Confirmed again:" repeats of that statement, so they are corrected with it.
   - **Retire:** `update_statements`, one call per statement: `query` set to its text, `set: { addCategories: ["superseded", "dream-<date>"] }`. A superseded statement stays in the graph but is left out of recall, so retiring can be undone by removing the label. Never use `delete_statements` here.
   - **Add:** `add_project_learnings` with the project name, `statements`, `types`, `confirm: true`.
   - **Core:** `update_statements` with `statements` set to the texts that join and `set: { addCategories: ["core"] }`; another call with `set: { removeCategories: ["core"] }` for the ones that leave.
   - **Ideas from outside:** see "Looking outward", step d.
   - **Record the check:** one `update_statements` call with `statements` set to every statement that held or that you couldn't tell about, and `set: { addCategories: ["dream-<date>"] }`, so the next dream moves on to other statements instead of meeting these again.

   If a call reports fewer matches than expected, say which statement was not changed instead of trying another selector.

8. **Report** in a few lines: the state of the memory, checked, corrected, retired, added (answers and open questions apart), core now, and how many learnings are still unchecked (`unchecked` minus the ones this dream recorded). Then list each correction as before → after, because the earlier text of a corrected statement is kept nowhere else. Say that retired statements can be brought back by removing their `superseded` category in InfraNodus.

   When the dream did not look outward, and it corrected or retired fewer than a third of the statements it checked, end with one line: "To look outward from this memory for ideas beyond it, run `/infranodus-memory:dream transcend`." Leave the line out when the memory needed more repair than that.

## Looking outward

Only when asked, as described above. It runs after step 5 and before the plan in step 6, on a memory this dream has just checked.

The ideas it produces are not learnings. Nothing in the repo or a transcript can confirm them, so they carry the category `transcend`, which keeps them out of automatic recall, out of `/infranodus-memory:recall`, and out of the replay in step 2. A user sees them in the graph, or with `/infranodus-memory:recall transcend`. They are never `core`.

If `get_project_learnings` has no `transcend` input (an older InfraNodus server), the ideas could not be kept out of recall: say so and skip this part.

a. **Review the ideas already kept.** Call `get_project_learnings` with the project name, `transcend: "only"`, `order: "oldest"`, `limit: 50`. For each idea older than 60 days (`createdAt`), look up the outside concept it brought in: `get_project_learnings` with that concept as `entity` and `transcend: "include"`. If the idea is the only statement that mentions it, no session took it up: propose retiring it. An idea that other statements now link to stays.

b. **Find the doors.** Call `develop_conceptual_bridges` with `graphName` set to the learnings graph. Its `latentConceptsToDevelop` are the conceptual gateways: concepts in the memory with wide reach for the few links they have, the places where it connects most easily to other fields. Its `ideas` are a lead.

c. **Write at most two ideas.** Each one:
   - starts from a gateway concept and links it to one concept from outside the memory (a practice, a pattern, a tool, another field), both marked with `[[wikilinks]]`;
   - is worded as something to explore, not as a fact ("Worth exploring: whether [[X]] could use [[Y]] to …");
   - holds one idea, under 300 characters;
   - repeats no idea already kept (step a), and builds on nothing this dream found wrong or outdated.

   Two is the limit for one dream, and it is separate from the limit in step 4.

d. **After approval** (each idea is approved or declined on its own in the plan):
   - Save the approved ideas with `add_project_learnings`: the project name, `statements`, `types` set to `question` for each, `confirm: true`.
   - Label them straight away: `update_statements` on the learnings graph with `statements` set to the same texts, `set: { addCategories: ["transcend", "dream-<date>"] }`, `confirm: true`. Until this call succeeds the ideas are stored as ordinary learnings and would be recalled as such. If it fails or reports fewer matches than ideas, say which ideas are not labelled.
   - Retire the kept ideas the user agreed to drop: `update_statements` with `statements` set to their texts and `set: { addCategories: ["superseded", "dream-<date>"] }`, `confirm: true`.

In the report, list the ideas added and retired apart from the learnings, and say they are read with `/infranodus-memory:recall transcend`.
