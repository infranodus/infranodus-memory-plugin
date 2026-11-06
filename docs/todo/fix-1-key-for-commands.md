# Fix 1: one optional key, taken only from the install dialog

**Status:** built on branch `connector-first`, 2026-11-06. Not merged, not released.
**Order:** fix 1, [fix 2](fix-2-save-specific-content.md) and [fix 4](fix-4-no-own-mcp-server.md) are one release (0.8.0). [Fix 5](fix-5-directory-version.md) is the submission to Anthropic's directory. The skills repo has its own plan: [skills-repo.md](skills-repo.md). There is no fix 3.

## The problems

1. **The slash commands can't see the key.** "In skill and agent content,
   only non-sensitive values are substituted, and a sensitive value there
   becomes a placeholder" (plugin manifest reference). So `save`,
   `forget-last` and `status` answer "The InfraNodus API key isn't set".
2. **Anthropic's directory refuses a plugin that reads a key from the
   machine** ("Uses a credential from user's machine", feedback on the
   `infranodus` skills plugin 1.8.4, 2026-11-06). `hooks/memory.py` reads
   `INFRANODUS_API_KEY`, `CLAUDE_PLUGIN_OPTION_API_KEY` and a key saved by
   `set-key`.
3. **The key is required at install**, although the commands can work
   through the InfraNodus connector without one.

## The fix

- The key is optional. Its only source is the install dialog, and its only
  user is the hooks. Claude Code hands every plugin option to the plugin's
  hooks as `CLAUDE_PLUGIN_OPTION_<KEY>` (plugin manifest reference), and
  leaves the variable out when the option was left empty.
- Not used: the key as a hook argument (`"args": [… "${user_config.api_key}"]`).
  Tested on 2026-11-06 with a throwaway plugin: when the option is not set,
  Claude Code does not run such a hook at all and reports "Hook failed to
  run: Plugin option "token" isn't set" on every prompt, even for an option
  with a default. An optional key can't work that way.
- With a key: hooks work as today (recall on the first prompt, upload at
  `SessionEnd` and `PreCompact`, 2 s limit, silent on failure).
- Without a key: hooks send nothing and fail on nothing. The commands still
  work through the connector (fix 2).
- The script never looks for a key in the environment or in a file.

### Changes

- [ ] `.claude-plugin/plugin.json`, `userConfig.api_key`: not required,
      sensitive, description "Optional. Turns on automatic memory (recall at
      session start, saving at session end). Without it, use the skills
      through the InfraNodus connector."
- [x] `hooks/memory.py`: the key comes only from
      `CLAUDE_PLUGIN_OPTION_API_KEY`. Removed: the reads of
      `INFRANODUS_API_KEY` and of `apiKey` in `memory.json`, `set-key`,
      `clear-key`, `key_source()`, the `--key` and `--base` arguments. An
      empty value, an unsubstituted `${…}` and Claude Code's
      `[sensitive option` placeholder all count as no key
- [x] The detached upload worker inherits the hook's environment, as before
- [x] No key: replace the first-run notice with "InfraNodus memory: add an
      API key in /plugin to turn on automatic memory for <project>", shown
      once per project, only when no key is set. With a key the old notice
      stays
- [x] `status` reads the last recall and upload from `timings.log`
- [x] An old `apiKey` in `memory.json` is left alone: Claude Code ignores it,
      and it is where `codex/key.py set-key` keeps the Codex key
- [x] Codex and Grok Build have no install dialog, so they need a key from
      the machine. That code moved into `codex/key.py`: it reads
      `INFRANODUS_API_KEY` or the key saved by its own `set-key`, then runs
      `memory.py` in the same process. Codex gets its own hooks file,
      `codex/hooks.json`, named in `.codex-plugin/plugin.json` ("An explicit
      value replaces default-file discovery", Codex plugin docs). The
      `codex/` folder is left out of what Anthropic receives (fix 5)

### Open point for the directory

The script still reads one variable, `CLAUDE_PLUGIN_OPTION_API_KEY`. It is
the value the user typed into the plugin's settings, delivered the way the
docs describe, not a credential "already set in the user's environment". The
local check (`claude plugin validate . --profile directory`) reports nothing,
but it is only a subset of what the portal runs, so the portal's Validate is
the real test.

## Tests

- [x] Unit tests (74 pass): no key is silent and shows the notice once per
      project; `INFRANODUS_API_KEY` or a stored key alone gives the script no
      key; the address rule; `codex/key.py`
- [x] No file Claude Code loads contains `INFRANODUS_API_KEY`, `set-key`,
      `--key` or `user_config.api_key` (a unit test checks it)
- [x] Live in Claude Code 2.1.318, no key, `claude --plugin-dir .`: hooks run
      with status 0, the notice shows once, nothing is sent
- [ ] Live with a key set in `/plugin`: recall and the session-end upload.
      Not run: the key lives in the system's secure store under the installed
      plugin, and a plugin loaded from a folder does not get it
- [ ] Codex: recall and upload through `codex/key.py`. Not run: Codex is not
      installed on this machine

## Done when

Install asks for an optional key. With it, automatic memory works. Without
it, nothing is sent. No file of the Claude plugin reads a key from the
environment or from disk.
