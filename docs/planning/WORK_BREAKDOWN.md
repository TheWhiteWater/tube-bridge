# Work Breakdown — tube-bridge

**Active authority:** ADR-003
**Current transition:** WI-00060

## Block A — Interaction Engine

**Status:** Complete

- 16-tool `TOOL_CATALOG` and matching dispatch/help.
- Dual-source Data API/yt-dlp behavior.
- Transcript extraction with real failure causes preserved.
- Read-only YouTube interaction boundary.

## Block B — Transports and Packaging

**Status:** Complete

- Installed synchronous CLI.
- stdio, Streamable HTTP and legacy SSE.
- Optional static Bearer.
- Wheel/sdist, exact lock, PyPI and GHCR distribution.

## Block C — Local Storage and Corpus

**Status:** Complete

- separate `cache.db` and `corpus.db`;
- local fastembed/sqlite-vec search;
- user-managed persistence and retention;
- nullable historical `expires_at` compatibility without active TTL;
- transactional corpus mutation and validated vector-table identifiers.

## Block D — Verification

**Status:** Complete for published core; WI-00060 final verification pending

- original 125-test core freeze;
- five-test self-hosted-only retirement contract;
- hosted Python 3.12/3.13 CI;
- build/twine, isolated install, Docker and MCP checks;
- independent source/document audits.

## Block E — Documentation and Release History

**Status:** In synchronization under WI-00060

- self-hosting-only public language;
- current release `v1.0.2`;
- functional `v1.0.0` metadata supersession history preserved;
- ADR-001 hosted-demo clauses and ADR-002 marked superseded;
- private infrastructure excluded from public product claims.

## Block F — Retire Hosted Demo and OAuth

**Status:** In verification

### Completed

- [x] Operator accepted ADR-003.
- [x] OAuth/demo/trusted-proxy variables removed from Railway.
- [x] Retirement contract frozen before source changes.
- [x] Demo/OAuth modules and tests removed from active tree.
- [x] Core transport/API/server behavior restored while preserving transcript fix.
- [x] Corpus schema compatibility retained while demo TTL behavior removed.

### Remaining

- [ ] Independent source audit.
- [ ] Bounded documentation audits.
- [ ] Hosted CI.
- [ ] Deploy simplified source to private Railway.
- [ ] Verify unauthenticated `401`, authenticated MCP initialize, no OAuth routes and no demo health surface.
- [ ] Cancel/supersede WI-00047 and WI-00057; close WI-00060.

## Dependency Graph

```text
A Interaction Engine ─┬─> B Transports/Packaging ─┬─> D Verification
                      └─> C Local Storage ─────────┘
                                      │
                                      └─> E Docs/History ─> F Retirement Gate
```

## Active Test Authority

- Core: `.brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json`
- ADR-003: `.brainops/methodology/frozen-tests/frozen-20260809051810-test_self_hosted_only_contract.py.json`

Demo/OAuth manifests remain in Git history but are removed from the active manifest directory.

## Product Rule

The project publishes software, not hosted access. Every user installs and evaluates their own MCP instance.
