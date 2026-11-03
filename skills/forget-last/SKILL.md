---
name: forget-last
description: Remove the learnings InfraNodus memory saved from the last session in the current project. Run only when the user asks.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" forget-last --key "${user_config.api_key}" --base "${user_config.api_base}"`

Relay the result above to the user in one or two plain sentences. Do not run anything else.
