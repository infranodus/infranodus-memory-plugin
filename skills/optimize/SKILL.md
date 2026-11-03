---
name: optimize
description: Optimize InfraNodus memory for the current project. Runs the InfraNodus optimize_knowledge_base analysis on the project's learnings and/or topic memory graphs, finds the clusters that never connect and the under-developed areas, and proposes new statements that bridge those gaps, to save after the user approves. Use when the user asks to optimize, improve, review or find gaps in their memory or learnings.
argument-hint: "[learnings | <topic> | all]"
allowed-tools: Bash(python3:*)
---

## Memory graphs here

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" graphs --key "${user_config.api_key}" --base "${user_config.api_base}"`

## What to do

1. **Choose the graphs.** If the list above has no graphs, tell the user there is nothing to optimize yet and stop. If the user named one in the command (`$ARGUMENTS`: `learnings`, a topic name, or `all`), use that. Otherwise, if there is more than one graph, ask which to optimize: the learnings, one topic, or all. With a single graph, use it.

2. **Analyze each graph** with the InfraNodus MCP tool `optimize_knowledge_base`: `graphName` set to the graph, `focus: "procedural"` for a `learn-` graph (how to work in a codebase), `focus: "general"` for `memory-` and `personal-` graphs, `includeLatent: true`. If the tool isn't available, say the InfraNodus MCP server needs authenticating in `/mcp` and stop.

3. **Read the result:** the diagnosis (biased / focused / diversified / dispersed), what dominates, the under-developed areas, and above all the gaps: clusters that never connect.

4. **Propose new statements** that improve the structure, up to 8 in total, best first:
   - Mostly bridges: each connects concepts from two clusters the analysis found unconnected, by stating a real relation between them.
   - Some may develop an under-developed area, or balance a structure the analysis calls biased (one idea dominating).
   - Every statement names at least two entities as `[[wikilinks]]`, because each wikilink becomes a node and the statement links them. One fact or relation per statement, under 300 characters, self-contained.
   - Only what is true. For learnings, check against this repo's code and docs before proposing; a relation you can't confirm becomes a question (type `question`). For topic and personal memory, use only what the graph and this conversation support. Never invent a fact to fill a gap.
   - For a learnings statement, give its type: location, trap, convention, decision (with its reason), workflow, question or approach.

5. **Show them to the user** as a numbered list: each statement, its type (for learnings), and in a few words which gap or area it addresses. Ask which to save. Save nothing without the user's answer.

6. **Save the approved ones:**
   - Learnings: `add_project_learnings` with the project name from the list above, `statements`, `types`, and `confirm: true` (the user already approved them).
   - A topic: `memory_add_relations` with `scope: "topic"`, `topic`, `statements` and `confirm: true`.
   - Personal: `memory_add_relations` with `scope: "personal"`, `statements` and `confirm: true`.

   Then say in one line how many were saved where.
