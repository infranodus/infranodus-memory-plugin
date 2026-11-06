---
name: on
description: Turn InfraNodus memory back on for the current project after /infranodus-memory:off. Run only when the user asks.
disable-model-invocation: true
---

When the user types this command, the plugin's hook runs it and puts the result into your context, in a block that starts with `[infranodus-memory]`.

Relay that result to the user in one plain sentence.

If no `[infranodus-memory]` block is in your context, the hook did not run. In Codex or Grok Build, which have no such hook, run `python3 <plugin root>/codex/key.py on` from the project folder (the plugin root is the folder two levels above this file) and use its output as the block. If there is still no result, say the command could not be run here.

Do not run anything else.
