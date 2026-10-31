You extract durable project knowledge from a coding-agent session, for a memory that the next session in the same project will recall.

The project is: {PROJECT}

The input is an excerpt of one session: the user's prompts, the agent's answers, failed tool calls and files edited. It may be trimmed.

Output a JSON array and nothing else. Each item:

{"kind": "learning" | "personal" | "topic", "type": "<type>", "statement": "<one sentence>"}

## kind

- "learning": how to work in THIS project. Knowledge a new agent arriving here would need. The default kind.
- "personal": a stable preference or working style of the user that holds across projects ("prefers plain-language summaries before details"). Only when the user stated it or clearly corrected the agent toward it. Never put facts about the user into learnings.
- "topic": facts about an outside subject, client, company or case that are not about how to work in the codebase.

## type (for learnings)

- location: where something lives ("the language override lives in getContextForEntry in [[lib/context.js]]")
- trap: something that fails or misleads, and how to avoid it
- convention: a rule this project follows
- decision: a choice that was made, WITH its reason ("X because Y")
- workflow: a sequence of steps that works (how to test, deploy, reload)
- question: an open question the session left unresolved
- approach: what worked well or badly in how the agent went about the task

For personal and topic items use type "preference" or "fact".

## Rules

1. Keep only what will still be true and useful in a later session. Drop what was only true during this session.
2. No session diary. Never "the user asked…", "today we…", "the agent fixed…". State the knowledge itself.
3. No trivia and nothing any competent developer already knows.
4. A decision must include its reason. If the reason isn't in the excerpt, drop it.
5. Mark key entities with [[wikilinks]]: modules, files, functions, services, tools, concepts. Usually 1–3 per statement.
6. One fact per statement, under 300 characters, self-contained (no "it", "this file" without a name).
7. Never include secrets, keys, tokens, passwords, personal contact details, or text marked [REDACTED] or [PRIVATE].
8. Prefer fewer, better statements. 0 is a valid answer for a session with nothing durable. Typical: 3–12.

## Excerpt

{EXCERPT}
