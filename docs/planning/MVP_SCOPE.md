# MVP Scope — tube-bridge

**Status:** Self-hosted core shipped and published; ADR-003 retirement evidence verified, with WI-00060 refreshed final conformance/closure pending.

## Included

### MCP Tools

Exactly 16 read-only tools:

- 10 YouTube search/discovery/transcript/metadata tools;
- 5 local corpus tools;
- `tube_bridge_help`.

Thirteen are keyless-capable. Three require the user's `YOUTUBE_API_KEY`.

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
| 16-tool catalog and dispatch | Shipped | Frozen core contracts |
| 13 keyless / 3 Data API tools | Shipped | Source and tool contracts |
| stdio/HTTP/SSE + static Bearer | Shipped | Transport and MCP integration tests |
| cache/corpus SQLite lifecycle | Shipped | Core SQLite tests plus ADR-003 compatibility contract |
| packaging and installed CLI | Published | Wheel/sdist/twine, isolated install and PyPI checks |
| container | Published | GHCR pull and MCP handshake |
| self-hosted-only retirement | Verified | Five-test frozen WI-00060 contract, independent source/docs audits, hosted CI and private Railway receipt |
| private endpoint exclusion | Verified | Two-test frozen WI-00064 contract, hosted CI, source audit and private live help receipt pass |

## Definition of Done

- [x] Exactly 16 tools and 13/3 key split.
- [x] Self-hosted stdio/HTTP/SSE transports.
- [x] Optional static Bearer for header-capable clients.
- [x] User-managed cache and semantic corpora.
- [x] GitHub, PyPI and GHCR publication.
- [x] Original 125-test core freeze.
- [x] ADR-003 accepted and 5-test retirement contract frozen.
- [x] Final source/docs audits, hosted CI and private Railway verification for WI-00060.
- [x] WI-00064 private-endpoint help remediation audit, CI and private redeploy.
- [ ] WI-00060 refreshed final conformance verdict and Station closure.

## Public Product Statement

Install it yourself and decide whether it is useful. The project does not provide hosted evaluation access.
