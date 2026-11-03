---
name: on
description: Turn InfraNodus memory back on for the current project after /infranodus-memory:off. Run only when the user asks.
disable-model-invocation: true
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" on --key "${user_config.api_key}" --base "${user_config.api_base}"`


If nothing appears above, the client did not run that command line (Codex and Grok Build load this skill but only Claude Code executes the `!` preamble): run it yourself from the project folder, `python3 <plugin root>/hooks/memory.py on`, where the plugin root is the folder two levels above this SKILL.md. There the API key comes from `INFRANODUS_API_KEY` or from `memory.py set-key`, not from `/plugin`.

Relay the result above to the user in one or two plain sentences. Do not run anything else.
