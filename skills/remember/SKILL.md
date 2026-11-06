---
name: remember
description: Save specific content the user names to InfraNodus memory - rules, a list, facts, a decision, a document. Use when the user says remember this, save this or these to memory or to InfraNodus, or add this to memory. For saving the session itself use /infranodus-memory:save.
argument-hint: "<what to remember>"
---

The user wants this kept in InfraNodus memory: $ARGUMENTS (if empty, the content they named in the conversation).

This command works through the InfraNodus MCP tools, from whatever InfraNodus server or connector is connected. If none of them is available, say "Connect the InfraNodus connector (or add an API key in /plugin for automatic memory)." and stop. The plugin's hook may have put a block starting with `[infranodus-memory]` into your context; it names the project.

1. **Decide where it goes.**
   - How to work in this project (a convention, a trap, a decision with its reason): `add_project_learnings`, with the project name from the block; without a block, the name of the git remote `origin` (the last part of its URL, without `.git`), else the name of the repository's folder.
   - An outside subject (a book's rules, a framework, a client, a case): `memory_add_relations` with `scope: "topic"` and a short `topic`, so it lands in `memory-<topic>`.
   - A graph the user names: `memory_add_relations` with `graphName`.
   - Something about the user (preferences, setup): `scope: "personal"`, only when the user asked for personal memory. Otherwise ask first.

2. **Write the statements.** One per item the user gave: nothing merged, dropped or shortened, and wording kept apart from what a statement needs. Keep IDs, numbers and checks. Each statement names at least two things as `[[wikilinks]]`, stays under 400 characters and holds no secrets, credentials or host names. An item longer than 400 characters becomes two statements that share its ID as a wikilink (the rule, then its check). Give each group of items a category.

3. **Save in batches of about 25**, so one refused statement does not hold up the rest. Pass `confirm: true`: the user's request is the approval, so each batch is saved in one call, without a preview. If a batch is rejected (a statement looks like a secret, is too long, or names fewer than two things), fix or leave out the statements it lists and send that batch again.
   - If the tool answers that the project or topic is not enabled, enable it (`enable_project_learnings`, or `enable_memory` for a topic or personal memory) because the user asked to save there, then repeat the call.

4. **Report** how many statements were saved, the graph's name and link, and anything that was refused, with the reason.

With several InfraNodus servers connected, use the one for infranodus.com, not a local one.
