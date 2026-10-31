You extract durable project knowledge from a coding-agent session, for a memory that the next session will recall.

The session ran in the project: {PROJECT}

The input is a trimmed excerpt of one session: shell commands that succeeded, the files edited, the user's prompts, the agent's final answers and failed tool calls.

Return statements through the required JSON schema. Each statement has:

- project: the folder name of the repo the statement is about. Usually "{PROJECT}". Sessions often touch neighbouring repos (paths like ../other-repo/… or ~/Software/other-repo/…): a fact about code in another repo gets that repo's folder name. Never guess a name that doesn't appear in the excerpt.
- kind and type, below.
- statement: one sentence.

## kind and type

- "learning": how to work in a project. Knowledge a new agent arriving there would need. The default kind. Types:
  - location: where something lives ("the language override lives in getContextForEntry in [[lib/context.js]]")
  - trap: something that fails or misleads, and how to avoid it
  - convention: a rule the project follows
  - decision: a choice that was made, WITH its reason ("X because Y")
  - workflow: a sequence of steps or a command that works (how to build, test, deploy, reload)
  - question: an open question the session left unresolved
  - approach: what worked well or badly in how the agent went about the task
- "personal": about the user, not about any project. Types:
  - preference: a stable preference or working style the user stated or clearly corrected the agent toward ("prefers plain-language summaries before details")
  - environment: a fact about the user's machine, shell, agent setup or permissions that would hold in every project ("the shell is zsh, which doesn't word-split unquoted variables", "auto mode blocks merging pull requests"). Never put these into learnings.
- "topic": facts about an outside subject, client, company or case that are not about how to work in a codebase. Type "fact".

## Rules

1. Keep only what will still be true next month. Drop snapshots: version numbers that will change, release or deploy status, branch names, what is committed, uncommitted, merged or pending, "currently", "now", "at the moment", counts that will change.
2. No session diary. Never "the user asked…", "today we…", "the agent fixed…". State the knowledge itself.
3. No trivia and nothing any competent developer already knows.
4. A decision must include its reason. If the reason isn't in the excerpt, drop it.
5. Every statement marks its key entities with [[wikilinks]]: modules, files, functions, services, commands, concepts. At least one, usually 1–3.
6. One fact per statement, under 300 characters, self-contained (no "it", "this file" without a name).
7. About the project's own code and how to work in it, not about tools the agent happened to use once in the session (a dashboard, an analysis plugin), unless the project depends on them.
8. Never include secrets, keys, tokens, passwords, personal contact details, or text marked [REDACTED] or [PRIVATE].
9. Prefer fewer, better statements. An empty list is a valid answer for a session with nothing durable. Typical: 3–12.

## Excerpt

{EXCERPT}
