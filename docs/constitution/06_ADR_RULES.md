# 06 — ADR Rules

## When an ADR Is Required

An Architecture Decision Record is mandatory for:

1. **Core tool/output breaking changes** — removing a tool, changing its name, or altering its output schema in a way that breaks consumers.
2. **Adding a new dependency or external service** — any new pip package, third-party API, proxy service, or infrastructure dependency.
3. **Changing the transport or auth model** — e.g., adding/removing transports, changing auth mechanism, altering the `/health` surface.
4. **Changing storage architecture** — e.g., switching database engines, splitting/merging `cache.db` and `corpus.db`, changing embedding models.
5. **Demo quota, abuse controls, or access policy** — per-user/IP budgets, rate limiting, observability, any change to who can access the demo and under what constraints.
6. **Self-hosted core compatibility** — any change to what is MIT-licensed, how the 16 tools are distributed, or whether self-hosted users are affected by demo-side decisions.
7. **Disposable demo isolation and quota** — changes to the dedicated Google Cloud project boundary, the fixed 5 Data API operations per client/IP limit, or the 10-minute corpus TTL.
8. **Full-publication distribution strategy** — changes to the GitHub release, PyPI package, Docker image, or documented demo targets.

## ADR Format

```markdown
# ADR-NNN: Title

**Status:** proposed | accepted | deprecated | superseded
**Supersedes:** ADR-NNN (if applicable)
**Superseded by:** ADR-NNN (if applicable)
**Date:** YYYY-MM-DD

## Context
What problem are we solving? What constraints apply?

## Decision
What did we decide? Include enough detail that a future reader understands the architecture direction.

## Alternatives Considered
What else was evaluated, and why was it rejected?

## Consequences
What becomes easier or harder because of this choice?
```

ADR files live in `docs/adr/NNN-title.md`. Numbers are sequential.

## Decision Authority

Decisions are role-based, not tied to any specific agent identity:

| Role | Can Propose | Can Accept | Role in Decisions |
|------|:-----------:|:----------:|-------------------|
| **Operator / Architect** | Yes | **Yes** | Accepts or rejects ADRs; holds architecture authority |
| **Auditor** | Yes | No | Recommends; evaluates alignment with constitution, evidence, and gates |
| **Executor** | Yes | No | Implements accepted decisions; may propose when implementation surfaces new constraints |

## Active ADRs

| ADR | Status | Title | Supersedes |
|-----|--------|-------|------------|
| [ADR-001](../adr/001-demo-api-quota-and-product-boundary.md) | **Accepted** | Demo API Access, Quota Boundary, and Self-Hosted Product Boundary | — |
| [ADR-002](../adr/002-demo-oauth-test-identity.md) | **Accepted for frozen-TDD implementation** | Demo OAuth Compatibility and Pseudonymous Test Identity | — |

ADR-001 records the accepted architecture direction for demo access, quota boundaries, and the self-hosted product boundary. ADR-002 authorizes an optional OAuth compatibility addendum for the same Disposable Demo surface; it does not create a third product surface, account system, or quota identity. An accepted ADR is architecture direction, **not launch approval**. Per-surface/addendum acceptance requires all relevant P0 items in `docs/planning/PUBLICATION_READINESS.md` to be resolved, plus Operator/Architect sign-off. The existing Core Full Publication and Bearer-protected Disposable Demo remain accepted while WI-00047's OAuth addendum is pending. There is no commercial extension, product gateway, or Grabbit connector surface.

## ADR Lifecycle

```
proposed → accepted → [ deprecated | superseded ]
```

- **proposed** — Written and submitted for review. Has not yet been accepted.
- **accepted** — Reviewed and approved by Operator/Architect. Active architecture direction.
- **deprecated** — No longer applicable; the decision is no longer relevant to the current product state.
- **superseded** — Replaced by a newer ADR. Must include a `Superseded by:` link to the replacement.
