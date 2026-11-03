---
name: save
description: The way to save to InfraNodus memory when the infranodus-memory plugin is installed. Saves what was learned in this session right away, instead of waiting for the session to end (learnings about the project, and facts about clients or subjects when the plugin's "What to save" setting allows). Use it whenever the user asks to save this session, what we learned, or something to memory or to InfraNodus; prefer it over add_project_learnings and memory_add_relations for that, since it needs no opt-in or approval and writes to the same graphs.
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" save --key "${user_config.api_key}" --base "${user_config.api_base}" --save "${user_config.save}" --session "${CLAUDE_SESSION_ID}"`


If nothing appears above, the client did not run that command line (Codex and Grok Build load this skill but only Claude Code executes the `!` preamble): run it yourself from the project folder, `python3 <plugin root>/hooks/memory.py save`, where the plugin root is the folder two levels above this SKILL.md. There the API key comes from `INFRANODUS_API_KEY` or from `memory.py set-key`, not from `/plugin`.

Relay the result above to the user in one or two plain sentences. Do not run anything else.
