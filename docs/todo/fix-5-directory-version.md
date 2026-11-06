# Fix 5: submitting the plugin to Anthropic's directory

**Status:** the copy is built and checked locally (2026-11-06, branch `claude-directory`, from the unmerged `connector-first`). The submission itself is not done.
**Depends on:** [fix 1](fix-1-key-for-commands.md), [fix 2](fix-2-save-specific-content.md), [fix 4](fix-4-no-own-mcp-server.md).
**Repos:** this one only.

## What the directory's rules say (read 2026-11-06)

Sources: claude.com/docs/plugins/submit, /plugins/pre-submission-checklist,
/plugins/platform-support, /directory/publish.

- **The form** asks for a repository, an optional plugin path and an
  optional branch or tag. It does not ask for an MCP server. "If the plugin
  references a remote MCP server you run, submit that server as an MCP
  connector too."
- **Credentials:** "Don't read a credential that is already set in the
  user's environment […] and send it to a server, even in a README example.
  Ask for it through `userConfig` instead." This is what stopped the
  `infranodus` skills plugin 1.8.4 on 2026-11-06 ("Uses a credential from
  user's machine"); its script, its test file and its `SKILL.md` were all
  named.
- **Scripts:** "the validator follows only plain shell scripts. When a hook
  […] or a `` !`…` `` line in a skill or command runs a non-shell file from
  the plugin […] that file is held" for a reviewer ("Scripts the validator
  couldn't follow").
- **One listing reaches three apps**, and each loads a different part:

  | Part of this plugin | Chat (claude.ai) | Cowork | Claude Code |
  |---|---|---|---|
  | Skills (the commands) | Loads | Loads | Loads |
  | Hooks (automatic recall and save) | Ignored | Loads | Loads |
  | The install dialog (the key) | Not asked | Not asked | Asked |

  So automatic memory works in Claude Code only. In chat and Cowork the
  plugin is its commands, which after fix 2 need only the connector.
- **Listing fields** in `plugin.json` (`documentationUrl`, `supportUrl`,
  `privacyPolicyUrl`, `termsOfServiceUrl`, `icon`) are read by the directory;
  the "Unrecognized field" note about them needs no action.

## The fix

The directory receives a copy of the plugin that contains no line reading a
key from the machine, and no text that names one.

After fixes 1, 2 and 4 the Claude plugin itself is already clean. What is
left in the repository is Codex's key code and the files that mention it.

- [x] A branch `claude-directory`, rebuilt by
      `scripts/release-directory.sh` at each release, without: `codex/`,
      `.codex-plugin/`, `.agents/`, `mcp.json`, `tests/`, `experiments/`,
      `docs/`, `scripts/`. The script stops if a remaining file names
      `INFRANODUS_API_KEY`, `set-key` or `user_config.api_key`. 16 files
      remain. Rebuild it after `connector-first` is merged, then enter it in
      the form's "Branch or tag" field
- [x] The Codex and Grok instructions (`INFRANODUS_API_KEY`, `set-key`) are
      in `codex/README.md` (fix 4), so the main README has no key example
- [x] Check on the branch: the only key-related line left is the read of
      `CLAUDE_PLUGIN_OPTION_API_KEY` in `hooks/memory.py`, the value Claude
      Code passes from the plugin's settings (see the open point in fix 1)
- [x] The README's "What is sent and when" section (fix 4) also names the
      files kept in `~/.infranodus/`, as the checklist asks ("Describe in
      the README everything the plugin runs, sends, or fetches")
- [x] `README.md` and the description: automatic memory needs Claude Code;
      in claude.ai chat and Cowork the plugin gives the memory commands
      through the InfraNodus connector
- [x] `.claude-plugin/plugin.json`: add `documentationUrl` and `icon`
- [ ] Submit the InfraNodus server as a connector if it is not listed yet
- [ ] **Validate** the branch in the portal before submitting; fix whatever
      it reports

## The risk that stays

The hooks run a Python script, and the rules send every such plugin to a
reviewer. The script can't be turned into plain shell: it trims and redacts
the session transcript. The portal's **Validate** on the branch shows the
result before anything is submitted. If this is refused too, the automatic
part can't be listed in the directory as it is built, and the listing would
be the commands only.

## Not planned: a server entry in the plugin

The directory's guide suggests it for a vendor's own product ("Point the
bundle's MCP server configuration at the same URL"), but does not require
it. It would bring back the plugin's own server next to the connector, which
fix 4 removes. Add it only if a reviewer asks.

## Tests before submitting

- [x] `claude plugin validate . --profile directory` on a checkout of the
      branch: nothing to report (a subset of the portal's checks)
- [x] The branch loaded in Claude Code with `--plugin-dir`, no key:
      `/infranodus-memory:status` works
- [ ] The branch with a key: recall, the session-end upload and every
      command
- [ ] The branch uploaded as a zip in claude.ai chat and in Cowork:
      `remember` and `recall` work through the connector; nothing mentions a
      key or a script
- [ ] The portal's validation report for the branch

## Done when

The plugin is listed, and nothing in the submitted copy reads a key from the
user's machine.
