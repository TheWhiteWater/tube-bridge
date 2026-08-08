# Open Questions

Unresolved questions and blocking decisions. Resolved historical questions recorded for audit.

## Resolved Architecture Questions

### Q1: Dual-source architecture (yt-dlp + Data API v3)
**Status:** Resolved — ADR-001 (2026-08-08).
**Resolution:** Dual-source architecture confirmed as the direction. Data API v3 is primary for search, video_info, and trending when `YOUTUBE_API_KEY` is present; yt-dlp is the fallback for quota-exhausted or key-absent paths. Source: `tube_bridge/tools.py` implements dual-source dispatch in `search()`, `video_info()`, `trending()`.
**Evidence:** `tube_bridge/tools.py` lines 16–62, 78–117, 125–163; ADR-001.

### Q2: Comments — Data API v3 only
**Status:** Resolved — ADR-001 (2026-08-08).
**Resolution:** Comments are obtained exclusively via YouTube Data API v3 (`youtube_get_comments`). This is a key-required tool. yt-dlp comment extraction is not used due to fragility and breakage on YouTube layout changes. If no API key is set, the tool returns a clear message: comments require `YOUTUBE_API_KEY`.
**Evidence:** `tube_bridge/tools.py` `comments()` delegates to `api.get_comments()`; ADR-001.

### Q3: One transcript tool
**Status:** Resolved — 2026-08-07.
**Resolution:** Single `youtube_get_transcript` tool with `with_timestamps` boolean parameter. Plain-text or `[MM:SS]`-prefixed output. Manual subtitles prioritized over auto-generated.
**Evidence:** `tube_bridge/server.py` `list_tools()` registers one transcript tool; `tube_bridge/tools.py` `transcript()`.

### Q4: Trending — geo-dependent with API upgrade path
**Status:** Resolved — ADR-001 (2026-08-08).
**Resolution:** Trending uses Data API v3 as primary when `YOUTUBE_API_KEY` is present; yt-dlp as fallback. Data API v3 trending returns US results by default. The yt-dlp fallback path is IP-region dependent (YouTube's trending page varies by IP region). An optional exposed `region` input parameter for Data API v3 trending remains backlog/nonblocking.
**Evidence:** `tube_bridge/tools.py` `trending()` implements dual-source; README documents the geo-dependency; `tube_bridge/youtube/api.py` `get_trending()`.

### Q5: Deployment — local stdio plus Railway HTTP
**Status:** Resolved — ADR-001 (2026-08-08).
**Resolution:** tube-bridge supports both local stdio (child-process MCP transport) and Railway-hosted HTTP (`tube-bridge-production.up.railway.app`) with Streamable HTTP `/mcp` and optional Bearer auth. Stdio mode opens no inbound socket; tools use outbound network (yt-dlp subprocess, Data API v3 HTTPS). Public hardening (5-operation limit enforcement, 10-minute corpus TTL) remains pending implementation for the demo endpoint. No third deployment target is required.
**Evidence:** `server.py` transport dispatch; `tube_bridge/transport.py`; Railway endpoint deployed; ADR-001.

### Q6: Channel search
**Status:** Resolved — shipped in source.
**Resolution:** `youtube_search_channels` is registered in `list_tools()`. It requires `YOUTUBE_API_KEY` and uses Data API v3 exclusively. Supports subscriber count filters (`min_subscribers`, `max_subscribers`) and `order` parameter. No yt-dlp fallback exists for channel search.
**Evidence:** `tube_bridge/server.py` `list_tools()` registers `youtube_search_channels`; `tube_bridge/tools.py` `search_channels()` delegates to `api.search_channels()`.

---

## Blocking Questions (Resolved)

All four blocking questions are resolved per ADR-001 (accepted 2026-08-08). Implementation remains open. No blocking decisions remain.

### B1: Consumer identity and usage budgets
**Status:** Decision Resolved / Implementation Open.
**Owner:** Operator.
**Resolution:** ADR-001 decision #1 and #2: Isolated Google Cloud project completely separate from Operator personal/development configuration. Exactly 5 official YouTube Data API v3 operations per observed client IP during the current demo-process lifetime. Identity is IP-only with no accounts or sessions. The counter is memory-only, has no time reset, resets when the disposable process restarts, and is never written to durable storage.
**Exit evidence:** Isolated GCP project provisioned (D1); memory-only IP counter and 5-operation limit enforced and tested (D2) — both implementation open.

### B2: Hosted corpus exposure, persistence, and retention
**Status:** Decision Resolved / Implementation Open.
**Owner:** Operator.
**Resolution:** ADR-001 decision #3 and #6: Every corpus created on the demo is automatically deleted 10 minutes after creation. No persistent volume, backups, accounts, or durable transcript/corpus hosting. Self-hosted instances have full persistent corpus storage under `~/.tube_bridge`. Tube-bridge is an MIT self-hosted MCP, never a SaaS or managed hosting product.
**Exit evidence:** 10-minute corpus TTL enforced and observable (D5). No persistent volume or accounts required.

### B3: Copyright, privacy, deletion, and compliance policy
**Status:** Decision Resolved / Implementation Open.
**Owner:** Operator.
**Resolution:** ADR-001 decision #3 and #6: No persistent hosted corpus, no durable transcripts, no user accounts, no SaaS/managed hosting. Corpora auto-delete 10 minutes after creation. Self-hosted boundary means users bring their own storage and keys. The demo needs a concise data-handling and deletion notice; the transient model does not waive applicable privacy, copyright, or YouTube policy obligations.
**Exit evidence:** Published demo data-handling and deletion notice (D4), plus evidence that no user data persists beyond the 10-minute corpus TTL.

### B4: Release evidence target
**Status:** Local Core Resolved / External Publication Open.
**Owner:** Operator/Architect.
**Resolution:** ADR-001 decision #7: full open-source distribution means GitHub release, PyPI package, Docker image, and documented demo. The core release candidate now passes C1–C5 local source/test/package/container acceptance. External publication and disposable-demo controls remain separate gates.
**Exit evidence:** Frozen 125-test suite, CI configuration, isolated installed-wheel CLI/MCP, wheel+sdist/twine, exact dependency lock, Docker MCP handshake, SQLite cleanup, and Station verification/lifecycle gate pass. Hosted CI/tag/GitHub Release/PyPI/Docker registry receipts remain open.

---

## Grabbit Relationship

### G1: Grabbit connector and integration
**Status:** Resolved — ADR-001 (2026-08-08).
**Resolution:** Grabbit is a completely separate MCP. There is no connector, dependency, shared service, bundled workflow, code integration, or implementation roadmap between tube-bridge and Grabbit. An agent may use tube-bridge to find videos and separately use Grabbit to save links — that is the full extent of any documented relationship. Grabbit is a separate companion MCP usage example only, never a tube-bridge implementation item.
**Evidence:** ADR-001 decision #8; PROJECT_VISION.md "Grabbit" section.

---

## Conditional / Nonblocking Questions

These do not block the core library or disposable demo release. Each may become blocking if a higher-priority dependency is not resolved.

### C1: YouTube Data API quota extension
**Status:** Acknowledged.
**Owner:** Operator.
**Context:** Default allocation is documented as 100 search.list calls/day, 100 videos.insert calls/day, and 10,000 units/day combined for other endpoints. Additional quota requires the YouTube API Services audit/quota-extension process. No purchasable tier was identified in reviewed official documentation. This is a conditional P1 for a bounded demo — only becomes blocking if demo demand exceeds default allocation before extension is complete.
**Condition:** Blocking only if demo usage hits default quota ceiling before audit/extension is complete.

### C2: Proxy reliability (IPRoyal residential proxy)
**Status:** Deployed, conditional P1.
**Owner:** Operator.
**Context:** `TUBE_BRIDGE_PROXY` (IPRoyal residential proxy, pay-as-you-go) is operational with disclosed limitations. Transcript pipeline depends on it for datacenter deployments (Railway). No performance SLA is asserted. This is P1 with disclosed limitations; it becomes P0 only if the accepted demo transcript/corpus promise fails an Operator-defined availability threshold.
**Condition:** Becomes P0 if the accepted demo transcript/corpus promise fails an Operator-defined availability threshold.

### C3: Optional trending region parameter
**Status:** Deferred, nonblocking.
**Owner:** Architect.
**Context:** `youtube_get_trending` with Data API v3 supports a `regionCode` parameter. Adding this to the MCP tool schema would allow agents to request region-specific trending. This is a feature enhancement, not a blocking issue.
**Nonblocking:** Core library and demo release are independent of this feature.
