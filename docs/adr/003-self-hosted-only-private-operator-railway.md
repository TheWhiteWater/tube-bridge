# ADR-003: Self-Hosted-Only Product and Private Operator Railway

**Status:** Accepted
**Date:** 2026-08-09
**Authority:** Operator/Architect
**WorkItem:** WI-00060
**Supersedes:** ADR-001 for the hosted-demo surface; ADR-002 in full

## Context

The public disposable Railway demo introduced IP quotas, short corpus retention, trusted-proxy identity, OAuth compatibility, invite roles, and a browser authorization flow. These controls were implemented and verified, but they increased product and operational complexity without improving the core value: a user can install the MIT MCP and decide whether it is useful in their own environment.

The Operator does not want to run a public demo or tester program. The existing Railway service remains useful as private personal infrastructure for Pi and header-capable clients.

## Decision

1. **The only public product is the MIT self-hosted MCP.** Users install from PyPI, GitHub, or GHCR and operate their own server, credentials, storage, quotas, and retention.
2. **There is no public hosted demo.** The project does not advertise or accept a public Railway try-before-install surface, external tester invites, managed access, or browser-Claude connector compatibility.
3. **The existing Railway service becomes private Operator infrastructure.** It retains `TUBE_BRIDGE_AUTH_KEY`, Operator-owned upstream configuration, and optional proxy configuration. The public hostname is not a product endpoint and is not distributed as a demo URL.
4. **Demo mode is disabled.** The private instance does not apply the five-operation demo allowance, trusted-proxy identity buckets, or forced ten-minute corpus TTL.
5. **OAuth and tester identity are retired.** OAuth discovery/DCR/authorize/token routes, signing/invite configuration, Operator/Tester aggregates, and associated source/tests are removed. Browser Claude Custom Connector is not a supported private-client target because it cannot attach the existing static Bearer header.
6. **Header-capable personal clients remain supported.** Pi and Claude Code CLI may use the private Railway service with the existing static Bearer key. Self-hosted HTTP remains optionally protected by `TUBE_BRIDGE_AUTH_KEY`.
7. **History is preserved.** Accepted demo/OAuth commits, audits, and deployment receipts remain in Git and Station history; they are no longer active product requirements or manifests.

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Continue public demo and repair OAuth/browser flows | Rejected: preserves the complexity the Operator explicitly chose to retire. |
| Keep a public unauthenticated `/mcp` | Rejected: exposes Operator-owned upstream resources and does not create a self-hosted-only product. |
| Keep demo/OAuth code dormant but undocumented | Rejected: dead product-specific code and active manifests would preserve maintenance and audit burden. |
| Shut down Railway entirely | Rejected: the authenticated instance remains useful as private Operator infrastructure for Pi/CLI. |
| Rewrite history back to `v1.0.2` | Rejected: Git/Station evidence must remain append-only and auditable. |

## Consequences

### Positive

- One product boundary: install and self-host the MCP.
- No public-demo operations, tester provisioning, OAuth server, account-like flow, IP identity, or hosted retention promise.
- The Operator keeps a convenient private Railway MCP without exposing its Bearer credential.
- Core release behavior and existing distribution channels remain unchanged.

### Negative

- Browser Claude Custom Connector cannot use the private Railway MCP.
- Users must install/operate their own instance before evaluating tools.
- Previously built demo/OAuth functionality is intentionally retired.

## Acceptance

- Railway has no OAuth/demo/trusted-proxy variables; static Bearer remains.
- Unauthenticated private `/mcp` is `401`; authenticated initialize succeeds.
- OAuth discovery is absent and `/health` reports no active demo mode.
- Demo/OAuth production modules, tests, active manifests, and public claims are removed without rewriting Git ancestry.
- Core deterministic, package, Docker, hosted CI, secret and documentation audits pass.
