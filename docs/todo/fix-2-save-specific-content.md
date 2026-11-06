# Fix 2: the commands work through the InfraNodus MCP tools, with no key

**Status:** todo. Rewritten 2026-11-06.
**Depends on:** released together with [fix 1](fix-1-key-for-commands.md), which takes the key away from the commands.
**Repos:** this one, and one new tool in `mcp-server-infranodus` (for `forget-last`).
**Order:** fix 1 and fix 2 together, then [fix 4](fix-4-no-own-mcp-server.md); [fix 5](fix-5-directory-version.md) is the submission to Anthropic's directory. There is no fix 3.

## The problems

- The commands can't get the key, and may not read one from the machine
  (fix 1). Today `save`, `forget-last`, `recall` and `optimize` run the
  script with the key.
- "Put the refactoring UI rules into the InfraNodus memory" (70 rules) was
  routed to `save`, which only uploads the session transcript and takes no
  content. Its description claims the request: "or something to memory or to
  InfraNodus; prefer it over add_project_learnings and memory_add_relations".

## The fix

Every command that talks to InfraNodus does it through the MCP tools of the
InfraNodus server the user has connected. The script stays for the hooks and
for what needs no key.

| Command | Today | After |
|---|---|---|
| `save` | Script uploads the transcript with the key | Claude writes what the session learned and saves it with `add_project_learnings` |
| `remember` (new) | | Claude saves the content the user names with the memory tools |
| `recall` | Script lists the graphs with the key, then MCP tools | MCP tools only (`list_graphs` for the list) |
| `optimize` | Same | MCP tools only |
| `forget-last` | Script calls `/memory/forget` with the key | New MCP tool that calls the same endpoint |
| `status` | Script; says "API key: missing" | Script, local facts only: on or off, the project name, the last recall and upload and whether they worked |
| `on`, `off` | Script, no key | Unchanged |

Automatic saving at the end of a session is unchanged: the hook uploads the
transcript and the app extracts the learnings.

### `save`

- [ ] No `!` line. The skill tells Claude to write the session's durable
      learnings (locations, traps, conventions, decisions with reasons,
      workflows) and save them with `add_project_learnings`
- [ ] Description: only "save this session / what we learned so far, without
      waiting for the session to end". Add: "Not for specific content the
      user names (rules, a list, a fact, a document): use
      /infranodus-memory:remember"
- [ ] One line in the body: if the user did name specific content, run
      `remember` for it as well
- [ ] To test: a manual save followed by the automatic upload at the end of
      the same session does not store the same learning twice

### `remember`: new skill

`/infranodus-memory:remember <what>`; Claude may also invoke it by itself.

- [ ] `skills/remember/SKILL.md`, description: "Save specific content the
      user names to InfraNodus memory: rules, a list, facts, a decision, a
      document. Use when the user says remember this, save this / these to
      memory or to InfraNodus, add this to memory. For saving the session
      itself use /infranodus-memory:save."
- [ ] Step 1, where it goes:
  - how to work in this project → `add_project_learnings`
  - an outside subject (a book's rules, a framework, a client) →
    `memory_add_relations` with `scope: "topic"`, so it lands in
    `memory-<topic>` (the 70 rules → `memory-refactoring-ui`)
  - the user names a graph → `memory_add_relations` with `graphName`
  - about the user → `scope: "personal"`, only when the user asked for
    personal memory
- [ ] Step 2, the statements: one per item; nothing merged or shortened;
      IDs, numbers and checks kept; at least two `[[entities]]` each; a
      category per group
- [ ] The app's limits, stated in the skill (`infranodus-app`,
      `lib/memory/core.js`, `routes/memory.js`): every statement under 400
      characters; no secrets, host names or credentials; one bad statement
      rejects the whole batch. A rule longer than 400 characters is split in
      two statements that share the rule's ID. Send a large set in batches
      of about 25
- [ ] Step 3: report what was saved, the graph name and link, and anything
      refused

### `forget-last`

- [ ] `mcp-server-infranodus`: a tool `forget_project_learnings`
      `{ project, sessionId?, confirm? }` that calls the app's existing
      `POST /api/v1/memory/forget`. Same shape as `add_project_learnings`: a
      dry run first, then `confirm: true`. The endpoint already deletes the
      session's statements from every memory graph and un-marks what the
      session superseded; `delete_statements` alone would not do the second
      part
- [ ] The skill calls that tool for the project. It undoes automatic
      uploads. Learnings saved by hand with `save` or `remember` carry no
      session label; the skill says so and points to `delete_statements`

### Shared by all commands

- [ ] The project name: a `memory.py project` action prints the name the
      hooks use (no key)
- [ ] Which server: the InfraNodus MCP server the user has connected. With
      several, the one for infranodus.com, not a local one
- [ ] No InfraNodus tools available: one clear message with the two ways to
      add the server (see [fix 4](fix-4-no-own-mcp-server.md))
- [ ] To test: whether `allowed-tools` can pre-approve the InfraNodus tools
- [ ] `README.md`: the commands table; `.codex-plugin/plugin.json` if it
      lists the commands

### Decisions to confirm

1. **Approval.** The tools show a dry run and ask before `confirm: true`.
   Proposal: the user's request is the approval; confirm at once when the
   dry run keeps every statement, ask only when it drops or changes one.
2. **Enabling.** `add_project_learnings` and scoped memory refuse until the
   project or topic was enabled "on the user's request only". Proposal:
   installing the memory plugin and asking to save counts as that request.
3. **Name.** `remember` (proposal), or `add`.

## Tests

- [ ] No skill contains `--key`, `user_config.api_key`, or a `!` line that
      reaches the network
- [ ] Live in Claude Code, key set only in the install dialog:
  - "save this session" → learnings in `learn-<project>`
  - "put these rules into the InfraNodus memory" (70 items) → `remember`,
    70 statements in `memory-<topic>`, IDs intact
  - `/infranodus-memory:forget-last` after an automatic upload → that
    session's learnings are gone, superseded ones are back
  - `/infranodus-memory:status` → on, project name, last recall ok
- [ ] In claude.ai chat and Cowork (plugin uploaded as a zip): `remember`
      and `recall` work through the connector

## Done when

The request that failed on 2026-11-05 ends with the 70 rules in a memory
graph, and every command works with no key anywhere but the install dialog.
