# ADR-001: Demo API Access, Quota Boundary, and Product Separation

**Status:** Accepted (architecture direction; not launch approval)
**Date:** 2026-08-08
**Authority:** Operator/Architect

## Context

tube-bridge is an MIT-licensed open-core MCP server that provides 16 tools for AI agents to interact with YouTube. It ships with a zero-registration workflow: 13 of 16 tools work without an API key, using yt-dlp and youtube-transcript-api. Three tools (comments, channel search, channel info) require a YouTube Data API v3 key, which users obtain from Google Cloud Console.

A Railway-hosted demo endpoint exists at `tube-bridge-production.up.railway.app`. This ADR defines the architecture direction for demo API access, quota management, and the boundary between the open-core library, the optional hosted demo, proposed commercial extensions, and Grabbit integration.

### Key constraints

1. Source code obtains optional Data API access configuration from environment variables at runtime. No API key, token, or secret is bundled, embedded, committed, or shipped in the repository (source: `tube_bridge/tools.py` line 18 `api.get_api_key()`; `tube_bridge/transport.py` line 14 `os.environ.get("TUBE_BRIDGE_AUTH_KEY")`).
2. YouTube Data API v3 does not provide transcript text. Transcript reliability is a separate `youtube-transcript-api`/proxy concern.
3. Google documents default allocation as 100 search.list calls/day, 100 videos.insert calls/day, and 10,000 units/day combined for other endpoints, subject to change. Additional quota uses the YouTube API Services audit/quota-extension process. No purchasable quota tier was identified in official documentation.
4. Full-publication readiness is not yet accepted.

## Decision

### 1. Dedicated server-side demo access

The demo's Data API access will use a dedicated Google Cloud project, separate from any development or personal projects. Authentication material (API key) will be held only server-side as a Railway environment variable and never exposed to demo consumers, extension users, or the repository.

**Rationale:** Isolates demo quota from individual developer keys. Prevents shared-quota exhaustion. Aligns with Google's API terms.

### 2. Strict per-user/IP and global daily budgets

The demo will enforce both per-consumer and aggregate daily budgets on Data API calls. Abuse controls (rate limiting, anomaly detection, IP-based throttling) and observability (metrics, alerting) will be implemented before the demo is publicly promoted.

**Rationale:** Prevents a single consumer from exhausting shared demo quota. Provides operator visibility into usage patterns.

### 3. Official YouTube quota path

Additional Data API allocation follows the YouTube API Services audit/quota-extension process documented at:
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.google.com/youtube/terms/developer-policies

No purchasable quota tier was identified in these official documents. If Google introduces one, the decision can be revisited.

### 4. Separate transcript pipeline

Transcripts are obtained via `youtube-transcript-api` (with IPRoyal residential proxy for datacenter IP bot-detection workaround), not through the Data API. The Data API does not provide transcript text. This pipeline is architecturally independent from the API key/quotas decisions above.

### 5. Extension as separate product layer

The proposed commercial extension is a separate product layer but is explicitly based on and reuses the tube-bridge engine. It requires:
- A server-side product gateway for entitlements, usage enforcement, billing, trial management, and support.
- Physical deployment may reuse existing services (Railway or equivalent); this remains an architecture decision, not a prohibition.

**What the extension is NOT:** The extension is not a re-bundling of the open-core with shared upstream access material. No demo API key or proxy credential is distributed to extension consumers.

**Rationale:** Keeps the open-core library zero-friction. Allows the extension to monetize value-add (managed access, higher quotas, research features) without compromising the MIT promise.

### 6. Grabbit as optional connector

Grabbit integration is an optional connector and product workflow. It enables:
- Batch video-link collections: save YouTube links into Grabbit collections.
- Transcript and research attachment to Grabbit items.
- Cross-promotion between the tube-bridge extension and Grabbit.

Grabbit is not required for core tube-bridge operation. It is an independent opt-in path that may be implemented after the extension product gateway is established.

## Alternatives Considered

| Alternative | Rejected Because |
|-------------|-----------------|
| Bundle an API key in the open-core repo | Security risk; violates MIT open-core principle; against Google API terms |
| Require all users to bring their own API key for all 16 tools | Destroys the zero-registration value proposition; 13 tools would regress |
| Make the extension entirely separate infrastructure | The extension is built on the tube-bridge engine; physical deployment reuse is a valid architecture decision |
| Skip the product gateway and distribute shared credentials | Security and quota-abuse risk; no enforceable per-user budgets |
| Embed Grabbit as a hard dependency | Adds coupling; Grabbit is a separate product with its own lifecycle |

## Consequences

### Positive

- Open-core library remains zero-friction: 13 tools work without any setup.
- Demo users get a functional hosted endpoint without obtaining their own API key.
- Extension users get managed, higher-quota access without sharing upstream credentials.
- Clean product boundary enables independent extension pricing, trial, and support models.
- Grabbit integration adds a natural content-to-collection workflow without complicating the core.

### Negative

- Demo quota is finite and shared; budget exhaustion will degrade demo availability.
- Extension requires a product gateway — non-trivial infrastructure investment.
- YouTube audit/quota-extension process has no guaranteed timeline or outcome.
- Transcript pipeline depends on a third-party proxy service (IPRoyal) for datacenter deployments.

## Open Decisions

1. **Demo budget values** — exact per-user/IP and global daily limits need operator decision.
2. **Extension pricing and trial structure** — commercial decision for the operator.
3. **Product gateway technology** — whether to build custom or use an off-the-shelf API gateway.
4. **Grabbit integration timing** — whether to ship with extension v1 or as a follow-on.
5. **Persistent storage for corpus.db on Railway** — volume mount needed for production corpus retention.

## Exit Criteria

This ADR is considered **accepted as architecture direction** when:
- Operator/Architect review confirms the direction is sound.
- No blocking concerns are raised that would invalidate the open-core boundary.

This ADR is **NOT** launch acceptance. Full-publication readiness requires all P0 items in `docs/planning/PUBLICATION_READINESS.md` to be resolved.

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
