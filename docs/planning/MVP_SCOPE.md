# MVP Scope — tube-bridge

**Status:** Self-hosted core shipped and published; ADR-003 retirement is verified and WI-00060 is closed.

## Included

### MCP Tools

Exactly 17 read-only tools:

- 11 YouTube search/discovery/transcript/frame/metadata tools in the source tree;
- 5 local corpus tools;
- `tube_bridge_help`.

Fourteen are keyless-capable. Three require the user's `YOUTUBE_API_KEY`.

### Transports

- stdio;
- Streamable HTTP `/mcp`;
- legacy SSE `/sse` and `/messages`;
- public `/health`;
- optional static Bearer through `TUBE_BRIDGE_AUTH_KEY`.

### Data and Storage

- user-owned `cache.db` and `corpus.db`;
- local fastembed inference and sqlite-vec search;
- user-controlled persistence, retention and backups;
- nullable `expires_at` compatibility column with no active TTL behavior;
- transcript failures preserve real network/proxy causes.

### Distribution

- GitHub Release;
- PyPI;
- public GHCR container;
- MIT license.

## Excluded

- public hosted demo or try-before-install endpoint;
- OAuth, DCR, invite codes, tester roles or browser-Claude connector compatibility;
- demo quotas, IP identity buckets, trusted-proxy selection or forced corpus TTL;
- accounts, signup, billing, entitlements, managed storage, shared credentials or SLA;
- browser extension, video download/upload/mutation, bulk scraping;
- Grabbit connector or code integration.

## Evidence

| Capability | Status | Evidence |
|---|---|---|
| 17-tool catalog and dispatch | Published and verified in v1.1.0 | Frozen core, frame contracts and public MCP smokes |
| 14 keyless / 3 Data API tools | Published and verified in v1.1.0 | Source, package and pulled-image contracts |
| stdio/HTTP/SSE + static Bearer | Shipped | Transport and MCP integration tests |
| cache/corpus SQLite lifecycle | Shipped | Core SQLite tests plus ADR-003 compatibility contract |
| packaging and installed CLI | Published | Wheel/sdist/twine, isolated install and PyPI checks |
| container | Published | GHCR pull and MCP handshake |
| self-hosted-only retirement | Verified | Five-test frozen WI-00060 contract, independent source/docs audits, hosted CI and private Railway receipt |
| private endpoint exclusion | Verified | Two-test frozen WI-00064 contract, hosted CI, source audit and private live help receipt pass |

## Definition of Done

- [x] Exactly 17 tools and 14/3 key split in published v1.1.0; v1.0.3 remains immutable release history.
- [x] Self-hosted stdio/HTTP/SSE transports.
- [x] Optional static Bearer for header-capable clients.
- [x] User-managed cache and semantic corpora.
- [x] GitHub, PyPI and GHCR publication.
- [x] Original 125-test core freeze.
- [x] ADR-003 accepted and 5-test retirement contract frozen.
- [x] Final source/docs audits, hosted CI and private Railway verification for WI-00060.
- [x] WI-00064 private-endpoint help remediation audit, CI and private redeploy.
- [x] WI-00060 final conformance PASS and Station closure.

## Public Product Statement

Install it yourself and decide whether it is useful. The project does not provide hosted evaluation access.
