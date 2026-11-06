---
name: save
description: Save what was learned in this session to InfraNodus memory right away, instead of waiting for the session to end. Use when the user asks to save this session or what we learned so far. Not for specific content the user names (rules, a list, a fact, a document), which is /infranodus-memory:remember.
---

When the user types this command, the plugin's hook runs first and puts its result into your context, in a block that starts with `[infranodus-memory]`. With an API key set, the hook uploads the session and InfraNodus extracts the learnings.

1. **The block says the session was sent** (or that there is nothing new to save, or that an upload is queued or already running): relay that in one or two plain sentences and stop.

2. **There is no block, or it says no API key is set** (also when you started this command yourself): save through the InfraNodus MCP tools.
   - The project: the project name from the block; without a block, the name of the git remote `origin` (the last part of its URL, without `.git`), else the name of the repository's folder.
   - Write what this session learned that a later session would need: where things are, traps, conventions, decisions with their reason, workflows, open questions. One fact per statement, self-contained, under 400 characters, with at least two `[[wikilinks]]` naming the things it connects. No secrets, credentials, host names or verbatim error output. Usually three to ten statements; if the session learned nothing durable, say so and save nothing.
   - Call `add_project_learnings` with `project`, `statements` and `types` (one of location, trap, convention, decision, workflow, question, approach per statement). It answers with a dry run. If the dry run keeps every statement as written, call it again with `confirm: true`: the user's request to save is the approval. If it drops or changes a statement, show that and ask before confirming.
   - If the tool answers that learnings are not enabled for this project, call `enable_project_learnings` for it (the user asked to save here), then repeat the call.
   - Say how many learnings were saved and in which graph.

3. **No InfraNodus tools are available and no upload happened:** say "Connect the InfraNodus connector (or add an API key in /plugin for automatic memory)." and stop.

If the user named specific content to keep (rules, a list, a document), also do what /infranodus-memory:remember describes for that content.

If no `[infranodus-memory]` block is in your context, the hook did not run. In Codex or Grok Build, which have no such hook, run `python3 <plugin root>/codex/key.py save` from the project folder (the plugin root is the folder two levels above this file) and use its output as the block.
