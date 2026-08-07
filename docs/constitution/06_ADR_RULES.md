# 06 — ADR Rules

## When to write an ADR

An Architecture Decision Record is required when:

1. **Choosing between 2+ viable approaches** — e.g., yt-dlp vs Data API v3 for search
2. **Adding a new dependency** — any new pip package or external service
3. **Changing the transport/model** — e.g., stdio → HTTP, or flat playlist → full metadata
4. **Removing a tool or breaking its output schema**
5. **Changing a core principle** from 00_MISSION.md

## ADR Format

```markdown
# ADR-NNN: Title

**Status:** proposed | accepted | deprecated | superseded
**Date:** YYYY-MM-DD

## Context
What problem are we solving?

## Decision
What did we decide?

## Alternatives Considered
What else did we evaluate and why rejected?

## Consequences
What becomes easier/harder because of this?
```

ADR files live in `docs/adr/NNN-title.md`. Numbers are sequential.

## Decision Authority

| Role | Can propose | Can accept |
|------|:----------:|:----------:|
| Architect (W-1020) | ✅ | ✅ |
| Auditor | ✅ | ❌ (recommend only) |
| Executor | ✅ | ❌ (implement only) |

## Active ADRs

None yet — project in genesis phase. First expected ADR: "Discovery layer: yt-dlp vs Data API v3 for search and comments."
