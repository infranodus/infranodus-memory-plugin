---
name: optimize
description: Optimize the InfraNodus Graph Memory of the current project. Runs the InfraNodus optimize_knowledge_base graph analysis on the project's InfraNodus learnings and topic memory graphs, and also on other memories when present (Claude's own memory notes, claude-mem, mem0), finds the clusters that never connect and the under-developed areas, and proposes new statements that bridge those gaps, to save after the user approves. Use when the user asks to optimize, improve, review or find gaps in their memory or learnings.
argument-hint: "[learnings | <topic> | claude | claude-mem | mem0 | all]"
allowed-tools: Bash(python3:*), Read
---

## Memory here

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" graphs --key "${user_config.api_key}" --base "${user_config.api_base}"`


If nothing appears above, the client did not run that command line (Codex and Grok Build load this skill but only Claude Code executes the `!` preamble): run it yourself from the project folder, `python3 <plugin root>/hooks/memory.py graphs`, where the plugin root is the folder two levels above this SKILL.md. There the API key comes from `INFRANODUS_API_KEY` or from `memory.py set-key`, not from `/plugin`.

## What to do

1. **Find the memory sources.** Possible sources:
   - each InfraNodus memory graph listed above (learnings, a topic, personal);
   - Claude's own memory, when the notes folder above has notes;
   - claude-mem, when its MCP search tools are available in this session;
   - mem0, when its `search_memories` MCP tool is available.

   If there is none, say there is no memory to optimize yet and stop. If the user named one in the command (`$ARGUMENTS`), use that. With one source, use it. With several, ask with the AskUserQuestion tool (multiSelect) which to optimize, one option per source with a few words on what it holds.

2. **Analyze each chosen source on its own** with the InfraNodus MCP tool `optimize_knowledge_base`, `includeLatent: true`, `focus: "procedural"` for project learnings and Claude's notes about how to work in a project, `"general"` otherwise. If the tool isn't available, say the InfraNodus MCP server needs authenticating in `/mcp` (Claude Code) or connecting as the plugin's MCP server (Codex, Grok) and stop.
   - **An InfraNodus graph:** `graphName` set to the graph.
   - **Any other memory:** send the memories as they are, one per item in `statements`, without rewriting them or adding wikilinks, and without `saveAs`, so nothing is stored in InfraNodus.
     - Claude's own memory: Read each note in the folder (skip `MEMORY.md`); one statement per note, its text without the frontmatter.
     - claude-mem: search its observations for this project and fetch them; one statement per observation (its title and text). Up to 200, the most recent first.
     - mem0: `search_memories` with a few queries (the project name, then the main subjects the first results name), duplicates removed; one statement per memory.

3. **Read the result:** the diagnosis (biased / focused / diversified / dispersed), what dominates, the under-developed areas, and above all the gaps: clusters that never connect.

4. **Propose new statements** that improve the structure, up to 8 per source, best first:
   - Mostly bridges: each connects concepts from two clusters the analysis found unconnected, by stating a real relation between them.
   - Some may develop an under-developed area, or balance a structure the analysis calls biased (one idea dominating).
   - Every statement names at least two entities as `[[wikilinks]]`, because each wikilink becomes a node and the statement links them. One fact or relation per statement, under 300 characters, self-contained.
   - Only what is true. For project knowledge, check against this repo's code and docs before proposing; a relation you can't confirm becomes a question (type `question`). For other memory, use only what the memories and this conversation support. Never invent a fact to fill a gap.
   - For a learnings statement, give its type: location, trap, convention, decision (with its reason), workflow, question or approach.

5. **Show them to the user** as a numbered list per source: each statement, its type (for learnings), and in a few words which gap or area it addresses. Ask which to save, and for a source outside InfraNodus, where. Save nothing without the user's answer.

6. **Save the approved ones:**
   - InfraNodus learnings: `add_project_learnings` with the project name from the list above, `statements`, `types`, and `confirm: true` (the user already approved them).
   - An InfraNodus topic: `memory_add_relations` with `scope: "topic"`, `topic`, `statements` and `confirm: true`.
   - InfraNodus personal: `memory_add_relations` with `scope: "personal"`, `statements` and `confirm: true`.
   - Claude's own memory: a new note in that folder in the same format as the others, plus its line in `MEMORY.md`.
   - claude-mem: its save tool (`save_memory`), one call per statement.
   - mem0 can't be written to with the tools here: offer InfraNodus learnings or a topic instead.
   - Outside InfraNodus, write the statements without the `[[ ]]` brackets.

   Then say in one line how many were saved where.
