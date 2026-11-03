---
name: status
description: Show whether InfraNodus memory is on for the current project, which project name it uses, and whether the API key is set.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" status --key "${user_config.api_key}" --base "${user_config.api_base}"`

Relay the result above to the user in one or two plain sentences. Do not run anything else.
