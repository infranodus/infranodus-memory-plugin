# Skills repo and plugins marketplace: no bundled server

**Status:** todo, written 2026-11-06.
**Repos:** `infranodus/skills` (here `../Skills/InfraNodus-Skills`) and `infranodus/plugins` (here `../infranodus-plugins`). The memory plugin's part is in [fix 1](fix-1-key-for-commands.md), [fix 2](fix-2-save-specific-content.md), [fix 4](fix-4-no-own-mcp-server.md) and [fix 5](fix-5-directory-version.md).

## The problem

Six plugins declare the InfraNodus MCP server. Claude Code matches a
plugin's server against the user's own by address, so the plugin's copy
either hides the claude.ai connector or asks for a second sign-in. The
plugins should use the server the user already has.

Checked in the repo on 2026-11-06:

- Server declared in: the root manifest (`infranodus-all`), `infranodus`,
  `skill-llm-wiki`, `skill-project-learnings`, `skill-seo-analysis`,
  `skill-shifting-perspective`. Not in `skill-cognitive-variability`,
  `skill-ontology-creator`, `skill-writing-assistant`.
- "run `/mcp`, select InfraNodus and sign in" in the `SKILL.md` of
  `infranodus`, `skill-seo-analysis`, `skill-shifting-perspective`,
  `skill-writing-assistant`.

## Changes

The plugins stay where they are. No new plugin folder and no sync script.

- [ ] Remove `mcpServers` from the six manifests; nothing else changes there
- [ ] The four skill files: replace the sign-in line with "connect the
      InfraNodus connector (claude.ai Settings → Connectors) or
      `claude mcp add --transport http infranodus https://mcp.infranodus.com`,
      then sign in"
- [ ] `infranodus/SKILL.md`: bare tool names instead of
      `mcp__infranodus__<tool>` ("call the InfraNodus
      `generate_content_gaps` tool, from whatever InfraNodus MCP server or
      connector is connected"). With no InfraNodus tools and no key: one
      line asking to connect the connector. Never ask for an API key
- [ ] Check that the frontmatter loads in Claude Code with the `openclaw`
      metadata block and causes no key prompt; report the result
- [ ] `README.md` of the skills repo: Claude Code quick start becomes
      "connect the InfraNodus connector first, then install"; the "bundled"
      column of the single-skill table becomes "requires InfraNodus
      connector"; remove the sentence about bundled skills bringing the
      server
- [ ] `README.md` of the plugins repo: remove the paragraph "Both plugins
      register the InfraNodus MCP server"; `infranodus` is "the /infranodus
      skill; uses your InfraNodus connector"
- [ ] `marketplace.json` of the plugins repo: `infranodus` requires the
      InfraNodus connector; `infranodus-memory` works with the connector,
      and an optional API key turns on automatic memory that uploads session
      learnings. The duplicate `infranodus` listing stays; it points at the
      same folder
- [ ] Bump every changed plugin and `infranodus-all` (`RELEASING.md`: "If you
      change `infranodus/`, also bump `infranodus-all`"); otherwise existing
      users keep the bundled server. Rebuild the OpenAI package
      (`openai/infranodus/`), which keeps its own server file

## The key fallback

The upload scripts read `INFRANODUS_API_KEY` and send it to InfraNodus. The
directory's feedback on 1.8.4 ("Uses a credential from user's machine")
named `infranodus/SKILL.md`, `scripts/upload_scopes.py`,
`scripts/tests/test_incremental.py` and `plugin.json`. Version 1.8.0 passed
with the same scripts; the only change in `infranodus/` since then is the
"Analyze and optimize memories" section of `SKILL.md`.

The key also appears in: `skill-llm-wiki/scripts/upload_wiki_ontology.py`
(environment and local config files), `skill-writing-assistant/SKILL.md`
(setup text and a command example), the main `README.md` and `install.sh`
(both inside the `infranodus-all` bundle, which is the whole repo).

- [ ] **Step 1, a test.** A branch of 1.8.4 without the "Analyze and
      optimize memories" section. **Validate** it in the portal
- [ ] **If it passes:** the fallback stays as it is, undocumented outside
      the skill. Reword the memory section and resubmit
- [ ] **If it fails:** the key parts stay in the repo for other clients, and
      Anthropic receives a branch without them, built by a script:
  - the part of each upload script that reads the key goes into a file of
    its own (`infranodus`, `skill-llm-wiki`)
  - the key instructions move out of the skill files into one reference
    file per skill; the skill file only says to connect the connector
  - the `openclaw` block that names the key, the key examples in the README
    and `install.sh` are left out of that branch

## Tests

- [ ] `/plugin marketplace add <local plugins repo>`, install `infranodus`
      and `infranodus-memory`: no prompt for `infranodus`, no MCP
      suppression message in `/plugin`
- [ ] The user's existing InfraNodus server or connector stays active
- [ ] `/infranodus` runs a graph tool through the existing server
- [ ] Server disabled and no key: the "connect the InfraNodus connector"
      line. With `INFRANODUS_API_KEY` in the shell (skills repo version):
      `upload_scopes.py --check-auth` succeeds

## Rules for the work

A branch in each repo, small commits, one pull request per repo with the
verification results, no merge. No change to the InfraNodus server or API.
