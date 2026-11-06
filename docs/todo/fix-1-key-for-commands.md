# Fix 1: the plugin reads no key from the machine

**Status:** todo. Rewritten 2026-11-06 (the first plan, a key copy in `~/.infranodus/config.json`, is cancelled).
**Affects:** Claude Code, plugin 0.7.0.
**Order:** fix 1 and [fix 2](fix-2-save-specific-content.md) are released together, then [fix 4](fix-4-no-own-mcp-server.md); [fix 5](fix-5-directory-version.md) is the submission to Anthropic's directory. There is no fix 3.

## Two problems, one cause

1. **The slash commands can't see the key.** The hooks get it from Claude
   Code, the commands don't: "In skill and agent content, only non-sensitive
   values are substituted, and a sensitive value there becomes a
   placeholder" (plugin manifest reference). So `save`, `forget-last` and
   `status` answer "The InfraNodus API key isn't set". Seen 2026-11-05.
2. **Anthropic's directory refuses a plugin that reads a key from the
   machine.** Feedback on the `infranodus` skills plugin 1.8.4, 2026-11-06,
   "Uses a credential from user's machine": "Something in the plugin reads a
   credential (a token or API key) from the user's environment or files and
   could send it to a server." Flagged there: the script that reads
   `INFRANODUS_API_KEY`, its test file, and the `SKILL.md` that names it.
   The fixes it offers: "pass a `${user_config.KEY}` value the user chose to
   share", or "remove every part that reads a credential".

The first plan for problem 1 copied the key into a file for the commands to
read. That is exactly what problem 2 forbids. `hooks/memory.py` today reads
the key from `INFRANODUS_API_KEY`, from `CLAUDE_PLUGIN_OPTION_API_KEY` and
from `~/.infranodus/memory.json` (`set-key`).

## The fix

The key has one source, the install dialog, and one user, the hooks.

- **Hooks** (recall at the first prompt, the upload at the end of a
  session): Claude Code hands them the key as an argument. "Plugin hooks
  additionally substitute `${user_config.*}` values, in exec form only: the
  value is substituted into `command` and into each `args` element as a
  plain string" (hooks reference).
- **Commands**: no key at all. Everything they did with the key goes through
  the InfraNodus MCP tools ([fix 2](fix-2-save-specific-content.md)).
- **The script** never looks for a key in the environment or in a file.

### Changes

- [ ] `hooks/hooks.json`, all three hooks in exec form:

  ```json
  { "type": "command", "command": "python3",
    "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/memory.py", "hook-prompt",
             "--key", "${user_config.api_key}"],
    "timeout": 5 }
  ```

- [ ] `hooks/memory.py`, `api_settings()`: the key comes only from `--key`.
      Remove the reads of `INFRANODUS_API_KEY`, `CLAUDE_PLUGIN_OPTION_API_KEY`
      and `apiKey` in `memory.json`; remove `set-key`, `clear-key` and
      `key_source()`
- [ ] `hook_flush`: the detached `ingest-worker` gets the key on its standard
      input from the hook, not from the environment or its command line
- [ ] `_setting()` also treats Claude Code's placeholder (a value starting
      with `[sensitive option`) as unset
- [ ] All skills: remove `--key "${user_config.api_key}"`. The script's
      `save`, `forget-last` and `graphs` actions, which needed the key, are
      removed (fix 2 replaces them)
- [ ] The hooks record the result of their last recall and upload in
      `~/.infranodus/memory.json` (time, ok or the error), so `status` can
      say whether the key works without having it
- [ ] An old `apiKey` in `memory.json` is deleted at the next hook run
- [ ] Codex and Grok Build have no install dialog, so they need a key from
      the machine. That code moves out of `hooks/memory.py` into one small
      file of its own, `codex/key.py`: it reads `INFRANODUS_API_KEY` or the
      key saved by `set-key`, then runs `memory.py` with `--key`. Codex's
      hooks call that file. It is left out of what Anthropic's directory
      receives (fix 5)
- [ ] `README.md`, the header comment of `hooks/memory.py`, the tests

### Known cost

The key is on the hook's command line while the hook runs (a few seconds),
where another process of the same user can see it. This is the form
Anthropic's rule asks for.

## Tests

- [ ] `hook-prompt --key K` recalls; with no `--key`, with the placeholder,
      or with `${user_config.api_key}` unsubstituted, the hook exits 0 with
      the "key isn't set" notice once
- [ ] With `INFRANODUS_API_KEY` set in the environment and no `--key`, the
      script makes no request
- [ ] `grep` over the plugin without `codex/`: no `INFRANODUS_API_KEY`, no
      `CLAUDE_PLUGIN_OPTION_API_KEY`, no `set-key`, no `user_config.api_key`
      outside `hooks/hooks.json`
- [ ] The upload worker receives the key and uploads; the key is not in its
      command line
- [ ] Live in Claude Code: a sensitive option is substituted into the hook's
      arguments; recall and the session-end upload work with the key set
      only in `/plugin`
- [ ] Codex: recall and upload still work through `codex/key.py`

## Done when

In Claude Code, with the key set only in the install dialog, automatic
recall and saving work, and no file of the Claude plugin reads a key from
the environment or from disk.
