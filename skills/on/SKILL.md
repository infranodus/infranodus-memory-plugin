---
name: on
description: Turn InfraNodus memory back on for the current project after /infranodus-memory:off. Run only when the user asks.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" on`

Relay the result above to the user in one or two plain sentences. Do not run anything else.
