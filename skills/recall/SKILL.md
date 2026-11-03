---
name: recall
description: Look something up in InfraNodus memory mid-session, following the graph's links. For a concept ("what do we know about webpack?", "what is X connected to?") it returns what the concept is connected to, by hop distance, with the learnings on those links; for a question or task it returns the most relevant learnings, including ones linked through an intermediate concept. Use when the user asks what memory or the learnings say about something, or before working on an area the memory may cover.
argument-hint: "<concept or question>"
allowed-tools: Bash(python3:*)
---

## Memory here

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" graphs --key "${user_config.api_key}" --base "${user_config.api_base}"`


If nothing appears above, the client did not run that command line (Codex and Grok Build load this skill but only Claude Code executes the `!` preamble): run it yourself from the project folder, `python3 <plugin root>/hooks/memory.py graphs`, where the plugin root is the folder two levels above this SKILL.md. There the API key comes from `INFRANODUS_API_KEY` or from `memory.py set-key`, not from `/plugin`.

## What to do

The user is asking about: $ARGUMENTS (if empty, use what the user asked in the conversation).

1. **Pick the graphs.** The project's learnings graph from the list above, plus a topic graph when the question is about that topic (a client, company, case). If there are no memory graphs, say there is no memory here yet and stop.

2. **Look it up** with the InfraNodus MCP tools (if they aren't available, say the InfraNodus MCP server needs authenticating in `/mcp` (Claude Code) or connecting as the plugin's MCP server (Codex, Grok) and stop):
   - **A concept** (one to three words: a module, file, tool, idea): `get_node_neighborhood` with `graphName`, `node` (pass likely spellings together, e.g. `["webpack", "webpack.config.js"]`) and `hops: 2`. If it answers `notFound`, retry once with the closest of its `suggestions`; if none fits, fall back to the question lookup below.
   - **A question or task:** `get_project_learnings` with the project name from the list, `prompt` set to the question and `hops: 2` (for a topic graph: `memory_get_relations` with `scope: "topic"`, `topic`, `prompt`, `hops: 2`).

3. **Answer briefly:**
   - For a concept: what it is directly connected to, then what is one step further and through which node (e.g. "[[babel]] via [[webpack]]"), then the learnings on those links, the direct ones first, with their type (trap, workflow…).
   - For a question: the relevant learnings, the direct matches first, then the ones linked through another concept.
   - Quote learnings as they are stored; add nothing they don't say. If the memory has nothing on it, say so in one line.
