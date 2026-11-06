---
name: status
description: Show whether InfraNodus memory is on for the current project, which project name it uses, whether an API key is set, whether the InfraNodus tools are available, and which features are active.
disable-model-invocation: true
---

When the user types this command, the plugin's hook runs it and puts the result into your context, in a block that starts with `[infranodus-memory]`.

1. Relay that result in two or three plain sentences: the project, whether memory is on for it, whether an API key is set, and whether automatic memory (recall at the first prompt, saving at the end of a session) is active.
2. Add one line on whether InfraNodus MCP tools are available in this session: look for tools such as `get_project_learnings`, `retrieve_from_knowledge_base` or `list_graphs`, from any InfraNodus server or connector. If they are, the recall, optimize, remember and save commands work through them. If they are not, say: "Connect the InfraNodus connector (or add an API key in /plugin for automatic memory)."

If no `[infranodus-memory]` block is in your context, the hook did not run. In Codex or Grok Build, which have no such hook, run `python3 <plugin root>/codex/key.py status` from the project folder (the plugin root is the folder two levels above this file) and use its output as the block. If there is still no result, say the status could not be read here and do step 2.

Do not run anything else.
