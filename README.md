# infranodus-memory-plugin

The `infranodus-memory` plugin: automatic memory for coding agents, stored as
InfraNodus knowledge graphs in your own account. On the first prompt of a
session it recalls what earlier sessions learned about the project; at the end
of a session it saves new learnings. Because memory is a graph, recall can also
say what the memory is missing.

**Status:** planning. Nothing implemented yet.

- Build plan, with links to the related plans in other repos: [`docs/plan.md`](docs/plan.md)
- Tasks for this repo: [`docs/todo/memory-system.md`](docs/todo/memory-system.md)
- Design: `mcp-server-infranodus/docs/drafts/infranodus-memory-system.md`

Starts as a Claude Code plugin (hooks + `/memory` skill), listed in the
InfraNodus skills marketplace. Hooks for other clients (Codex CLI, Cursor and
others) come later from the same code.
