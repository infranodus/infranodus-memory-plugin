# Fix 4: the plugin brings no MCP server of its own

**Status:** built on branch `connector-first`, 2026-11-06. Not merged, not released.
**Depends on:** same release as [fix 1](fix-1-key-for-commands.md) and [fix 2](fix-2-save-specific-content.md).
**Repos:** this one only.

## The problem

- The plugin declares its own InfraNodus MCP server. For a user who already
  has one, Claude Code hides the claude.ai connector ("same URL as your
  server plugin:infranodus-memory:infranodus") and asks for a new sign-in on
  the plugin's copy. Seen 2026-11-05.
- The install dialog shows an "API address" and an "MCP address" field that
  almost nobody needs.

## The fix

The plugin stops declaring an MCP server. Its commands use the InfraNodus
server the user already has (fix 2). This is the version for every channel,
Anthropic's directory included.

### Changes

- [x] `.claude-plugin/plugin.json`: delete `mcpServers`; delete `mcp_url` and
      `api_base` from `userConfig`
- [ ] The install dialog then shows three optional fields: the key, `save`,
      `exclude_paths`. The docs give no way to keep a setting and hide it
      from the dialog ("`userConfig` declares values Claude Code prompts the
      user for when the plugin is enabled"). To show only the key, `save`
      and `exclude_paths` would have to leave the settings. Decision taken
      for now: keep all three; check live what the dialog shows
- [x] Rename the Codex server file `.mcp.json` to `mcp.json` and point
      `mcpServers` in `.codex-plugin/plugin.json` at it. Claude Code loads a
      root `.mcp.json` ("Claude Code loads `.mcp.json` at the plugin root
      first"), so with the plugin's own entry gone it would load the Codex
      address. `mcp.json` is the name in Codex's docs ("Keep `plugin.json`,
      `mcp.json`, `skills/`, and `assets/` at the plugin root"), and only
      the manifest may sit in `.codex-plugin/`. No build step is needed
- [x] `hooks/memory.py`: the API address is the built-in default. For
      development, `INFRANODUS_API_BASE` in the shell overrides it. Update
      the Development section of the README (it uses
      `CLAUDE_PLUGIN_OPTION_API_BASE`)
- [x] `hooks/memory.py`: send the key only to `infranodus.com`, its
      subdomains, or this machine. Any other address is refused with a clear
      message and no request. Same rule as `key_allowed_for` in the skills
      repo's `upload_scopes.py`
- [x] `README.md`: install needs no setup. The InfraNodus connector enables
      the skills; an optional API key turns on automatic memory. A "What is
      sent and when" section near the top, for key mode only: trimmed
      transcripts at session end, secret and `<private>` redaction,
      `exclude_paths`, `/infranodus-memory:off`, `INFRANODUS_MEMORY_DISABLE`,
      `INFRANODUS_MEMORY_DISABLE_CAPTURE`, storage in the user's own
      InfraNodus account; without a key nothing is sent automatically.
      Claude Code is the supported client; Codex and Grok notes are marked
      experimental and live in `codex/README.md`
- [ ] Release note: an update removes the plugin's server entry; the tools
      come from the connector or the user's own entry
- [x] Version 0.8.0

## Tests

- [x] `claude -p … --plugin-dir .` (2.1.318): the debug log has no
      `plugin:infranodus-memory` server, and the claude.ai InfraNodus
      connector and the user's own `infranodus` server both connect
- [ ] The install dialog itself (which fields it shows) and `/plugin`: needs
      an interactive session
- [x] An address on another host: nothing is sent; `localhost` works (unit
      test)
- [ ] In Codex: the server from `mcp.json` is still offered

## Not chosen

- A server entry that sends the key in a header: no second sign-in, but two
  servers.
- A tool that hands the key to the plugin: any agent could call it.

## Done when

A user with the claude.ai InfraNodus connector installs the plugin and sees
one InfraNodus server, the one they had.
