# 06 — ADR Rules

## When an ADR Is Required

An Architecture Decision Record is mandatory for:

1. Removing/renaming a tool or making a breaking output/schema change.
2. Adding a package dependency, third-party API, external database/vector/embedding service, or infrastructure requirement.
3. Adding/removing a transport or changing static-auth behavior or `/health`.
4. Changing cache/corpus database architecture, retention behavior, or embedding model contract.
5. Adding any hosted public endpoint, demo, identity, account, tester, quota-sharing, or managed-service surface.
6. Changing what is MIT-licensed or how the self-hosted package/container is distributed.
7. Changing GitHub Release, PyPI, GHCR, dependency-lock, or release-signing strategy.
8. Reviving behavior explicitly retired by ADR-003.

## ADR Format

```markdown
# ADR-NNN: Title

**Status:** proposed | accepted | deprecated | superseded
**Supersedes:** ADR-NNN (if applicable)
**Superseded by:** ADR-NNN (if applicable)
**Date:** YYYY-MM-DD

## Context
## Decision
## Alternatives Considered
## Consequences
```

ADR files live under `docs/adr/` and use sequential numbers.

## Decision Authority

| Role | Can Propose | Can Accept |
|---|:---:|:---:|
| Operator / Architect | Yes | **Yes** |
| Auditor | Yes | No |
| Executor | Yes | No |

An accepted ADR records architecture authority; implementation still requires the applicable frozen tests, verification, independent audit, deployment and documentation gates.

## ADR State

| ADR | Status | Meaning |
|---|---|---|
| [ADR-001](../adr/001-demo-api-quota-and-product-boundary.md) | **Partially superseded** | Self-hosted/open-core decisions remain historical context; hosted-demo decisions are superseded by ADR-003. |
| [ADR-002](../adr/002-demo-oauth-test-identity.md) | **Superseded** | OAuth/tester design is retired. |
| [ADR-003](../adr/003-self-hosted-only-private-operator-railway.md) | **Accepted / active** | Only the self-hosted MCP is public; Operator Railway is private static-Bearer infrastructure. |
| [ADR-004](../adr/004-v1.1.0-release-test-contract-supersession.md) | **Accepted / release-specific** | v1.1.0 supersedes historical test-hash authority while preserving all prior manifests as evidence. |

## Active Product Rule

Public documentation and roadmaps describe one self-hosted product only. They must not advertise a Railway demo, public endpoint, invite/tester flow, OAuth, shared upstream credentials, managed retention, or SLA.

Historical commits, audits and receipts remain append-only evidence. Supersession changes active authority; it does not rewrite history.
