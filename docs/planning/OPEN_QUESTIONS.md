# Open Questions

Unresolved questions and blocking decisions. Resolved historical questions recorded for audit.

## Resolved Architecture Questions

### Q1: Dual-source architecture (yt-dlp + Data API v3)
**Status:** Resolved — ADR-001 (2026-08-08).
**Resolution:** Dual-source architecture confirmed as the direction. Data API v3 is primary for search, video_info, and trending when `YOUTUBE_API_KEY` is present; yt-dlp is the fallback for quota-exhausted or key-absent paths. Source: `tube_bridge/tools.py` implements dual-source dispatch in `search()`, `video_info()`, `trending()`.
**Evidence:** `search()`, `video_info()` and `trending()` in `tube_bridge/tools.py`; ADR-001.

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
**Resolution:** tube-bridge supports local stdio and Railway-hosted HTTP (`tube-bridge-production.up.railway.app`) with Streamable HTTP `/mcp` and Bearer auth. Stdio opens no inbound socket and explicit demo mode fails closed on stdio. Railway demo hardening is active: overwritten `X-Real-IP`, 5 attempted Data API operations/IP/process, memory-only counters, and 10-minute corpus deadlines. No third deployment target is required.
**Evidence:** `server.py`; `tube_bridge/transport.py`; `tube_bridge/demo_policy.py`; `tube_bridge/demo_ttl.py`; Railway live probes; ADR-001.

### Q6: Channel search
**Status:** Resolved — shipped in source.
**Resolution:** `youtube_search_channels` is registered in `list_tools()`. It requires `YOUTUBE_API_KEY` and uses Data API v3 exclusively. Supports subscriber count filters (`min_subscribers`, `max_subscribers`) and `order` parameter. No yt-dlp fallback exists for channel search.
**Evidence:** `tube_bridge/server.py` `list_tools()` registers `youtube_search_channels`; `tube_bridge/tools.py` `search_channels()` delegates to `api.search_channels()`.

### Q7: Claude connector authorization and tester distinction
**Status:** Architecture/source/deployment resolved; real Claude UI acceptance pending WI-00047.
**Owner:** Operator/Architect.
**Resolution:** Keep the existing static Bearer path for Pi/header-capable clients and add an optional deployment-only OAuth Authorization Code + PKCE adapter for Claude Custom Connector. Dynamic client registration does not grant access; a high-entropy deployment invite selects a pseudonymous `operator` or `tester` role. No accounts, durable identities, quota bypass, or identity vendor is introduced. Canonical OAuth URLs come only from `TUBE_BRIDGE_PUBLIC_BASE_URL`; malformed/partial OAuth configuration fails startup. Registration/form bounds, token lifetime, exact redirect/resource/issuer binding, and aggregate-counting semantics follow ADR-002.
**Gate:** OAuth endpoints may be described as active and protocol-verified, but do not claim Claude Custom Connector acceptance until the real UI authorizes and completes a tool call. The stale Claude Code `/sse` entry without a header is a separate local-client cleanup item.
**Evidence:** ADR-002; authoritative 64-test frozen contract `e1d13f36`; source `acc7cf3`; independent source audit PASS; CI `31289547358`; Railway deployment `3667c56f-4487-435b-b8b4-b45ec2d5619c`; live OAuth/PKCE/role/static-Bearer receipt `verification-WI-00047-railway-oauth-live.json`.

---

## Blocking Questions (Resolved)

All four original blocking questions are resolved per ADR-001. WI-00028 accepted core publication and WI-00029 accepted demo implementation/live controls. ADR-002's optional OAuth source and Railway protocol flow are now implemented and verified; WI-00047 remains open only for real Claude UI acceptance and final sign-off. This does not revoke existing core or demo acceptance.

### B1: Consumer identity and usage budgets
**Status:** Resolved and Implemented.
**Owner:** Operator.
**Resolution:** Isolated server-side demo configuration. Exactly 5 attempted Data API v3 network operations per Railway-overwritten `X-Real-IP` during the current process lifetime. No accounts/sessions; salted-HMAC bucket is memory-only, has no time reset, resets on process restart, and is never durably stored.
**Exit evidence:** Frozen Data API-boundary/identity tests; live six-value spoof probe yielded one bucket, five allows and sixth rejection; live restart reset aggregates to zero.

### B2: Hosted corpus exposure, persistence, and retention
**Status:** Resolved and Implemented.
**Owner:** Operator.
**Resolution:** Every demo corpus has a persisted 600-second deadline and is transactionally deleted by a nearest-deadline/reconciliation worker. No Railway volume, backups, accounts, or durable hosting. Self-hosted storage under `~/.tube_bridge` remains persistent.
**Exit evidence:** Frozen deadline/restart/rollback/race/worker tests; Railway manifest has no volume; non-invasive filesystem probe observed complete relational/vector deletion at the deadline sampling boundary.

### B3: Copyright, privacy, deletion, and compliance policy
**Status:** Resolved and Implemented.
**Owner:** Operator.
**Resolution:** No persistent hosted corpus, durable hosting promise, user accounts, SaaS or managed service. Raw client IP is not persisted or emitted by application access logs; corpora delete at 10 minutes. The transient model does not waive applicable privacy, copyright, or YouTube policy obligations.
**Exit evidence:** Published README data-handling/deletion notice, privacy tests, known-probe-IP application-log check, no-volume manifest and TTL deletion evidence.

### B4: Release evidence target
**Status:** Core Publication Resolved.
**Owner:** Operator/Architect.
**Resolution:** ADR-001 decision #7 is complete for both independent surfaces: GitHub Release, PyPI and public GHCR for self-hosted core; controlled Railway deployment for the disposable demo.
**Exit evidence:** Core 125-test freeze, package/registry receipts, accepted 209-test demo baseline, current cumulative 273-test hosted CI, demo lifecycle/audits, and live Railway identity/quota/restart/TTL receipts pass.

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
