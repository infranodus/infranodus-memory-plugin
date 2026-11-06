# Fix 4: the plugin brings no MCP server of its own; install asks for one key

**Status:** todo, written 2026-11-05. Not started.
**Depends on:** [fix 1](fix-1-key-for-commands.md) and [fix 2](fix-2-save-specific-content.md).
**Repos:** this one only.
**Order:** fix 1 and fix 2 together, then this one; [fix 5](fix-5-directory-version.md) is the submission to Anthropic's directory. There is no fix 3.

## The problem

- The plugin declares its own InfraNodus MCP server. For a user who already
  has one (the claude.ai InfraNodus connector, or a server they added),
  Claude Code then shows two: it hides the claude.ai connector ("same URL as
  your server plugin:infranodus-memory:infranodus") and asks for a new
  sign-in on the plugin's copy. Seen 2026-11-05. One service should not show
  up as two servers.
- The install dialog also shows an "API address" and an "MCP address" field
  that almost nobody needs.

## The fix

The plugin stops declaring an MCP server. Its commands use the InfraNodus
MCP server the user already has.

This is the version for every channel, Anthropic's directory included: its
submission form does not ask for a server. A second version that does
declare the server is kept in reserve in
[fix 5](fix-5-directory-version.md).

- The automatic part (recall at the first prompt, the upload at the end of a
  session) never used MCP: it is the script with the key from the install
  dialog. Unchanged.
- The commands use the MCP tools ([fix 2](fix-2-save-specific-content.md))
  and name them without a server ("the InfraNodus MCP tool
  `optimize_knowledge_base`"), so they work with whichever InfraNodus
  server is connected.
- A user with no InfraNodus server connected gets one clear message from
  those commands, with the two ways to add it:
  the InfraNodus connector in claude.ai settings, or
  `claude mcp add --transport http infranodus https://mcp.infranodus.com`.
  Automatic memory works without it.

### Changes

- [ ] `.claude-plugin/plugin.json`: delete `mcpServers`; delete `mcp_url`
      and `api_base` from `userConfig`. The dialog then asks for the API key,
      plus the optional `save` and `exclude_paths`
- [ ] All skills: remove `--base "${user_config.api_base}"` from the `!` line
- [ ] `hooks/memory.py`: the API address is the built-in default. For local
      development only, `INFRANODUS_API_BASE` in the shell overrides it (an
      address, not a credential)
- [ ] `hooks/memory.py`: send the key only to `infranodus.com`, its
      subdomains, or this machine (`localhost`, `127.0.0.1`, `::1`). Any
      other address is refused with a clear message and no request is
      made. Same rule as `key_allowed_for` in the skills repo's
      `infranodus/scripts/upload_scopes.py`. Today the script sends the key
      to whatever address is configured. Needed for safety, and it is what
      lets a directory reviewer clear the credential hold
      ([fix 5](fix-5-directory-version.md))
- [ ] Every command that uses the tools: the "tools aren't available"
      message above, replacing "needs authenticating in /mcp … the plugin's
      MCP server"
- [ ] `README.md`: install is the key plus, for the tool commands, an
      InfraNodus MCP server (connector or `claude mcp add`); the settings
      section; the plugin description if it mentions the server
- [ ] Move the Codex server file out of the plugin root: `.mcp.json` becomes
      `codex/mcp.json` (next to `codex/key.py` from fix 1), and `mcpServers` in `.codex-plugin/plugin.json`
      points to it. Claude Code also loads a root `.mcp.json` ("Claude Code
      loads `.mcp.json` at the plugin root first, then each declared shape in
      order. A server name declared later replaces an earlier one", plugin
      manifest reference). Today the entry in `plugin.json` has the same name
      and replaces it. Once that entry is deleted, Claude Code would load the
      Codex address `https://mcp.infranodus.com/openai`, which is not the
      connector's address, so both would load. Test in Codex that the server
      is still found at the new path
- [ ] Release note: an update removes the plugin's server entry; users who
      signed in to it keep their tools through the connector or their own
      entry, or add one as above. Values typed into the two address fields
      are ignored
- [ ] Tests; bump the version (0.8.0)

## Tests to run before release

- [ ] With the claude.ai connector connected: after install the connector is
      still listed and active in `/mcp`, nothing is hidden, no sign-in is
      asked, `recall` and `optimize` use its tools
- [ ] With no InfraNodus server: recall at the first prompt and the session
      upload work; the commands show the message
- [ ] With the InfraNodus skills plugin installed (it declares the server):
      one server, as before this plugin
- [ ] An address on another host: nothing is sent, the message names the
      address; `localhost` still works
- [ ] `claude mcp list` shows no `plugin:infranodus-memory:…` entry, with
      and without the connector (the moved Codex file is not picked up)
- [ ] In Codex: the server from `codex/mcp.json` is still offered
      at install

## Not chosen

- Sending the key to the plugin's own server in a header, for everyone:
  removes the second sign-in but keeps two servers. Kept in reserve in
  [fix 5](fix-5-directory-version.md).
- A tool that hands the key to the plugin: any connected agent could call it
  and leak the key.

## Done when

A user with the claude.ai InfraNodus connector installs the plugin, enters
the key once, and sees one InfraNodus server, the one they had. The
commands use it.
