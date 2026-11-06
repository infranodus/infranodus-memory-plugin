---
name: recall
description: GraphRAG recall from InfraNodus Graph Memory. Look something up in the project's memory graph mid-session by following its links, instead of matching text. For a concept ("what do we know about webpack?", "what is X connected to?") it returns what the concept is connected to, by hop distance, with the learnings on those links; for a question or task it returns the most relevant learnings, including ones linked through an intermediate concept. Use when the user asks what memory or the learnings say about something, or before working on an area the memory may cover.
argument-hint: "<concept or question>"
---

## Memory here

When the user types this command, the plugin's hook puts a block starting with `[infranodus-memory]` into your context: the project name, its learnings graph and, when an API key is set, the memory graphs and a recall through the API for the query.

If no `[infranodus-memory]` block is in your context, the hook did not run. In Codex or Grok Build, which have no such hook, run `python3 <plugin root>/codex/key.py recall <query>` from the project folder (the plugin root is the folder two levels above this file) and use its output as the block.

## What to do

The user is asking about: $ARGUMENTS (if empty, use what the user asked in the conversation).

1. **With InfraNodus MCP tools available** (from any InfraNodus server or connector; with several, the one for infranodus.com):
   - **Pick the graphs.** The project's learnings graph, plus a topic graph when the question is about that topic (a client, company, case). Take them from the block; without a list there, call `list_graphs` and take the memory graphs: `learn-<project>` for the project name from the block; without a block, the name of the git remote `origin` (the last part of its URL, without `.git`), else the name of the repository's folder, and `memory-<topic>`. If there are no memory graphs, say there is no memory here yet and stop.
   - **A concept** (one to three words: a module, file, tool, idea): `get_node_neighborhood` with `graphName`, `node` (pass likely spellings together, e.g. `["webpack", "webpack.config.js"]`) and `hops: 2`. If it answers `notFound`, retry once with the closest of its `suggestions`; if none fits, use the question lookup.
   - **A question or task:** `get_project_learnings` with the project name, `prompt` set to the question and `hops: 2` (for a topic graph: `memory_get_relations` with `scope: "topic"`, `topic`, `prompt`, `hops: 2`).
   - If the block holds a recall through the API, use it as well.

2. **Without the tools, when the block holds a recall through the API:** answer from that.

3. **With neither:** say "Connect the InfraNodus connector (or add an API key in /plugin for automatic memory)." and stop.

4. **Answer briefly:**
   - For a concept: what it is directly connected to, then what is one step further and through which node (e.g. "[[babel]] via [[webpack]]"), then the learnings on those links, the direct ones first, with their type (trap, workflow…).
   - For a question: the relevant learnings, the direct matches first, then the ones linked through another concept.
   - Quote learnings as they are stored; add nothing they don't say. If the memory has nothing on it, say so in one line.
