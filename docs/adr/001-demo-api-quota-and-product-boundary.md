# ADR-001: Demo API Access, Quota Boundary, and Self-Hosted Product Boundary

**Status:** Accepted (architecture direction; not launch approval)
**Date:** 2026-08-08
**Authority:** Operator/Architect

## Context

tube-bridge is an MIT-licensed self-hosted MCP server that provides 16 tools for AI agents to interact with YouTube. It ships with a zero-registration workflow: 13 of 16 tools work without an API key, using yt-dlp and youtube-transcript-api. Three tools (comments, channel search, channel info) require a YouTube Data API v3 key, which users obtain from Google Cloud Console.

A Railway-hosted disposable demo endpoint exists at `tube-bridge-production.up.railway.app`. This ADR defines the architecture direction for demo API access, quota management, and the self-hosted product boundary.

### Key constraints

1. Source code obtains optional Data API access configuration from environment variables at runtime. No API key, token, or secret is bundled, embedded, committed, or shipped in the repository (source: `tube_bridge/tools.py` line 18 `api.get_api_key()`; `tube_bridge/transport.py` line 14 `os.environ.get("TUBE_BRIDGE_AUTH_KEY")`).
2. YouTube Data API v3 does not provide transcript text. Transcript reliability is a separate `youtube-transcript-api`/proxy concern.
3. Google documents default allocation as 100 search.list calls/day, 100 videos.insert calls/day, and 10,000 units/day combined for other endpoints, subject to change. Additional quota uses the YouTube API Services audit/quota-extension process. No purchasable quota tier was identified in official documentation.
4. At ADR acceptance time, full-publication readiness was not accepted. Subsequent WI-00028 evidence now accepts the self-hosted core publication; demo acceptance remains separate.

## Decision

### 1. Isolated server-side demo access

The demo's Data API access uses a dedicated Google Cloud project with isolated server-side upstream configuration, completely separate from Operator personal/development configuration. Authentication material (API key) is held only server-side as a Railway environment variable and never exposed to demo consumers or the repository.

**Rationale:** Isolates demo quota from individual developer keys. Prevents cross-contamination between demo usage and Operator development work. Aligns with Google's API terms.

### 2. Fixed 5-operation limit per client/IP

The demo enforces exactly 5 official YouTube Data API v3 operations per observed client IP during the lifetime of the current demo process. Identity is IP-only: there are no user accounts or sessions. The counter is held only in process memory, has no time-based reset, and resets when the disposable demo process restarts. The IP counter is not written to corpus storage or another durable store. Exhaustion affects only the disposable demo — self-hosted users bring their own keys and are unaffected.

**Rationale:** This is the simplest literal implementation of the fixed per-client/IP allowance. It prevents one client from exhausting shared demo quota without accounts, persistent identity, complex budgets, or an anomaly-detection platform. Process restarts may restore the allowance because the demo provides no continuity guarantee.

### 3. 10-minute corpus TTL on demo

Demo corpora are temporary only. Every corpus created on the demo is automatically deleted 10 minutes after creation. No persistent volume, backups, accounts, or durable transcript/corpus hosting is provided on the demo.

**Rationale:** Eliminates Railway volume mounts, backup promises, and durable hosted-data operations. The demo still requires a concise data-handling and deletion notice, and the transient model does not waive applicable privacy, copyright, or YouTube policy obligations. Self-hosted instances have full persistent corpus storage under `~/.tube_bridge`.

### 4. Official YouTube quota path

Additional Data API allocation follows the YouTube API Services audit/quota-extension process documented at:
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.google.com/youtube/terms/developer-policies

No purchasable quota tier was identified in these official documents. If Google introduces one, the decision can be revisited.

### 5. Separate transcript pipeline

Transcripts are obtained via `youtube-transcript-api` (with IPRoyal residential proxy for datacenter IP bot-detection workaround), not through the Data API. The Data API does not provide transcript text. This pipeline is architecturally independent from the API key/quotas decisions above.

### 6. Self-hosted boundary

tube-bridge is an MIT self-hosted individual MCP, never a SaaS or managed transcript-hosting product. The Railway demo is solely a disposable try-before-install convenience. There is no commercial extension, product gateway, billing, entitlement, or managed higher-quota tier.

**Rationale:** Keeps the open-core library zero-friction. Users self-host with their own keys. The demo proves the tool works but makes no durability or availability promise.

### 7. Full-publication scope

Full open-source core distribution means GitHub Release, PyPI package, and public container image, with the demo documented as a separate surface. WI-00028 subsequently completed source/test/package verification and external publication; WI-00029 demo controls remain open.

### 8. Grabbit separation

Grabbit is a completely separate MCP. There is no connector, dependency, shared service, bundled workflow, code integration, or implementation roadmap between tube-bridge and Grabbit. An example agent usage sequence may show the agent uses tube-bridge to find videos and then separately uses Grabbit to save links — that is the full extent of any documented relationship.

**Rationale:** tube-bridge and Grabbit are independent products with separate lifecycles. No coupling is introduced.

### 9. Browser extension

A browser extension is outside this project's scope and release gate. It must not be architected, planned, or documented here.

## Alternatives Considered

| Alternative | Rejected Because |
|-------------|-----------------|
| Bundle an API key in the open-core repo | Security risk; violates MIT open-core principle; against Google API terms |
| Require all users to bring their own API key for all 16 tools | Destroys the zero-registration value proposition; 13 tools would regress |
| Per-user/IP daily budgets with abuse controls | Over-engineering for a disposable try-before-install demo; 5-op fixed limit is simpler and sufficient |
| Persistent demo corpus with volume mounts | Introduces retention policy, backup, deletion, GDPR, and copyright compliance infrastructure for a disposable demo |
| Commercial extension with product gateway | tube-bridge is an MIT self-hosted MCP, not a SaaS; no billing, entitlement, or managed tier is planned |
| Grabbit connector or shared service | Grabbit is a completely separate MCP; no coupling is introduced |

## Consequences

### Positive

- Open-core library remains zero-friction: 13 tools work without any setup.
- Demo users get a functional hosted endpoint without obtaining their own API key.
- Fixed 5-operation limit is transparent and simple — no complex budget/enforcement infrastructure needed.
- 10-minute corpus TTL eliminates data retention, privacy, and compliance overhead on the demo.
- Self-hosted users are unaffected by demo limits; they bring their own keys and have full persistent storage.
- Clean product boundary: no extension, no gateway, no billing, no Grabbit coupling.

### Negative

- Demo quota is finite and shared; 5-operation limit will be exhausted quickly by multiple users.
- No persistent corpus on demo — every corpus disappears after 10 minutes.
- YouTube audit/quota-extension process has no guaranteed timeline or outcome.
- Transcript pipeline depends on a third-party proxy service (IPRoyal) for datacenter deployments.

## Open Implementation Details

1. **10-minute TTL mechanism** — background cleanup loop, per-corpus timer, or lazy expiry checks may be chosen during implementation, provided every demo corpus becomes inaccessible and is deleted no later than 10 minutes after creation.
2. **Full-publication verification** — subsequently completed by WI-00028: frozen deterministic tests, hosted CI, PyPI install, public GHCR runtime, and GitHub Release receipts are present.

## Exit Criteria

This ADR is considered **accepted as architecture direction** when:
- Operator/Architect review confirms the direction is sound.
- No blocking concerns are raised that would invalidate the self-hosted boundary.

This ADR alone is **NOT** launch acceptance. Subsequent WI-00028 receipts satisfy the self-hosted core P0 gate; WI-00029 must independently satisfy the disposable-demo P0 gate.

## Sources

- `tube_bridge/server.py` — 16-tool registration (lines 67–248)
- `tube_bridge/youtube/api.py` — urllib-based Data API v3 client (lines 1–7 imports)
- `tube_bridge/tools.py` — tool implementations, dual-source fallback
- `tube_bridge/transport.py` — auth model, env var sourcing
- `tube_bridge/cache.py` — cache.db storage
- `tube_bridge/corpus.py` — corpus.db storage, local embeddings, network fetch for corpus_add
- `tube_bridge/youtube/transcript.py` — youtube-transcript-api wrapper
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.google.com/youtube/terms/developer-policies
