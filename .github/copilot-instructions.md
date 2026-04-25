# Engram Memory Protocol

This workspace uses Engram as persistent memory through MCP.

## When to save

Call `mem_save` immediately after any of these:

- Bug fix completed
- Architecture or design decision made
- Non-obvious discovery about the codebase
- Configuration or environment change
- Pattern or convention established
- User preference or constraint learned

Use this structure:

- `title`: short, searchable, verb + what
- `type`: `bugfix` | `decision` | `architecture` | `discovery` | `pattern` | `config` | `preference`
- `scope`: `project` by default
- `topic_key`: reuse for evolving topics when appropriate
- `content`:
  - `What`: what changed
  - `Why`: why it changed
  - `Where`: files or paths affected
  - `Learned`: gotchas or surprises, if any

## Topic rules

- Do not overwrite different topics with the same key
- Reuse the same `topic_key` for an evolving decision
- If unsure, call `mem_suggest_topic_key` first
- Use `mem_update` only when correcting a known observation

## When to search memory

When the user asks to recall past work, or references prior solutions:

1. Call `mem_context` first
2. If needed, call `mem_search`
3. If needed, call `mem_get_observation` for the full record

Also search proactively when the work may have been done before.

## Session close

Before ending a session, call `mem_session_summary` with this structure:

```md
## Goal
[What we worked on]

## Instructions
[User preferences or constraints, if any]

## Discoveries
- [Technical findings and gotchas]

## Accomplished
- [Completed work]

## Next Steps
- [What remains]

## Relevant Files
- path/to/file - [why it matters]
```

## Passive capture

When finishing a task, include a `## Key Learnings:` section with numbered items when there are durable learnings. This helps Engram capture useful knowledge even if an explicit save was missed.
