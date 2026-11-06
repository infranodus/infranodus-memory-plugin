# Fix 2: the commands use the InfraNodus connector first, the key second

**Status:** built on branch `connector-first`, 2026-11-06. Not merged, not released.
**Depends on:** same release as [fix 1](fix-1-key-for-commands.md) and [fix 4](fix-4-no-own-mcp-server.md).
**Repos:** this one only. No change to the InfraNodus server or API.

## The problems

- The commands run the script with a key they can't get (fix 1).
- They say "Needs the InfraNodus MCP server authenticated in /mcp", which
  assumes the plugin's own server.
- "Put the refactoring UI rules into the InfraNodus memory" (70 rules) went
  to `save`, which only uploads the session transcript.

## The fix

Each command has up to two ways to work:

1. **The connector.** Claude uses the InfraNodus MCP tools, by bare name
   (`get_node_neighborhood`, `retrieve_from_knowledge_base`,
   `optimize_knowledge_base`, `add_project_learnings`,
   `get_project_learnings`, `delete_statements`, `memory_add_relations`),
   never `mcp__…`, because connector and plugin prefixes differ.
2. **The key, through a hook.** A command cannot receive the key, so the
   script is not run by the command. A `UserPromptExpansion` hook does it:
   it "runs when a user-typed command expands into a prompt" and receives
   `command_name` and `command_args` (hooks reference). For
   `/infranodus-memory:<name>` it does the work through the REST API when a
   key is set, and adds the result to Claude's context. It has its own 40 s
   limit, so the 5 s limit of the prompt hook stays. Tested live: the
   command name arrives as `infranodus-memory:status`, and the matcher
   `infranodus-memory:.*` fires.

| Command | Connector available | No connector, key set | Neither |
|---|---|---|---|
| `recall <query>` | MCP tools (plus the hook's result when a key is set) | Hook: `/recall` | One line |
| `optimize` | MCP tools | One line: needs the connector | One line |
| `remember <what>` (new) | MCP tools | One line: needs the connector | One line |
| `save` | Key set: the hook uploads the session, as today. No key: Claude writes the learnings and saves them with `add_project_learnings` | Hook uploads | One line |
| `forget-last` | Hook, needs the key | Hook: `/memory/forget` | Says it needs the API key |
| `status` | Key set or not, tools available or not, which features are active | Same | Same |
| `on`, `off` | Hook, local, no key needed | Same | Same |

The one line: "Connect the InfraNodus connector (or add an API key in
/plugin for automatic memory)."

Why `save` and `forget-last` lean on the key: an upload is labelled with the
session, and `/memory/forget` deletes that session's statements from every
memory graph and un-marks what it superseded. `delete_statements` can't do
the second part, and without a key nothing was uploaded, so there is nothing
to forget. Learnings saved by hand through the tools are removed with
`delete_statements`.

### Changes

- [x] `hooks/memory.py`: `hook-command` handles `recall`, `save`, `forget-last`, `status`, `on`,
      `off`, `optimize`, `remember`; the result goes out as `additionalContext`, marked
      `[infranodus-memory]`. Reuses the existing auth, timeout and error
      handling. Never prints the key
- [x] All skills: no `!` line, no `--key`, no "Needs the InfraNodus MCP
      server authenticated in /mcp". The body: relay the hook's result if one
      is above; otherwise use the tools; otherwise the one line
- [x] `on`, `off`, `status`, `forget-last`: `disable-model-invocation: true`,
      so they always arrive as a typed line the hook sees. `save`, `recall`,
      `optimize`, `remember` can also be started by Claude, and then use the
      connector
- [x] `save` description: only "save this session / what we learned so far".
      Not for specific content: that is `remember`. One line in the body: if
      the user named specific content, run `remember` for it as well
- [x] `skills/remember/SKILL.md`: "Save specific content the user names to
      InfraNodus memory: rules, a list, facts, a decision, a document."
  - how to work in this project → `add_project_learnings`
  - an outside subject → `memory_add_relations`, `scope: "topic"` (the 70
    rules → `memory-refactoring-ui`)
  - a graph the user names → `memory_add_relations` with `graphName`
  - one statement per item, nothing merged, IDs kept, two `[[entities]]`
    each, under 400 characters, batches of about 25
- [x] `status`: the hook gives key, on or off, project, last recall and
      upload; Claude adds whether InfraNodus tools are in the session
- [x] With several InfraNodus servers connected, use the one for
      infranodus.com, not a local one

### Decisions, built as proposed

1. **Approval.** The tools show a dry run before `confirm: true`. Proposal:
   the user's request is the approval; ask only when the dry run drops or
   changes a statement.
2. **Enabling.** The learnings and memory tools refuse until enabled "on the
   user's request only". Proposal: asking to save counts as that request.
3. **Name.** `remember` (proposal), or `add`.

## Tests

- [x] Unit, mocked HTTP: the hook's `recall`, `save`, `forget-last`,
      `status` with a key; the same commands with no key send nothing
- [x] Live, no key: `/infranodus-memory:recall API key` answered through the
      connected InfraNodus tools; `/infranodus-memory:status` is correct
- [ ] Live, key set, MCP server disabled: `/infranodus-memory:recall test`
      and `save` work through the hook
- [ ] "put these rules into the InfraNodus memory" (70 items) → `remember`,
      70 statements, IDs intact
- [ ] A manual save followed by the automatic upload does not store the same
      learning twice

## Done when

Every command works with the connector alone, the 70 rules request
succeeds, and no command touches a key.
