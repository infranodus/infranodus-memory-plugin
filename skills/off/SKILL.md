---
name: off
description: Turn InfraNodus memory off for the current project on this machine: nothing is recalled or sent for it until /infranodus-memory:on. Run only when the user asks.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" off --key "${user_config.api_key}" --base "${user_config.api_base}"`

Relay the result above to the user in one or two plain sentences. Do not run anything else.
