# Project Vision — tube-bridge

**Last updated:** 2026-08-08
**Status:** MIT self-hosted individual MCP. Core v1 is published on GitHub, PyPI, and GHCR; disposable-demo hardening remains separately gated.

## North Star

Every AI agent can interact with YouTube as naturally as a human — search, discover, extract knowledge, and build research corpora — without API keys, registration, or vendor lock-in.

## What Is Shipped

### Tool baseline: 16 MCP tools

The MCP server registers exactly 16 tools (source: `tube_bridge/server.py` `list_tools()`, lines 67–248):

| # | Tool | API Key Required | Notes |
|---|------|:---:|-------|
| 1 | `youtube_search` | No → Yes | Data API v3 primary when key present; yt-dlp fallback |
| 2 | `youtube_search_channels` | Yes | Channel search with subscriber filters |
| 3 | `youtube_get_channel_info` | Yes | Detailed channel stats |
| 4 | `youtube_get_video_info` | No → Yes | Metadata, cached (lru_cache 64), dual-source |
| 5 | `youtube_get_trending` | No → Yes | API v3 primary, yt-dlp fallback |
| 6 | `youtube_get_channel_videos` | No | Recent uploads from @handle or URL |
| 7 | `youtube_get_playlist` | No | All videos in a playlist |
| 8 | `youtube_get_transcript` | No | Plain text or [MM:SS] timestamps; Manual > ASR |
| 9 | `youtube_get_available_languages` | No | Subtitle languages with auto-generated flags |
| 10 | `youtube_get_comments` | Yes | Top-level comments via Data API v3 |
| 11 | `corpus_create` | No | Named corpus for semantic transcript search |
| 12 | `corpus_add` | No | Auto-fetches transcript (network), chunks, local embeds |
| 13 | `corpus_search` | No | Semantic search with scores and timestamps |
| 14 | `corpus_list` | No | List all corpora with counts |
| 15 | `corpus_delete` | No | Delete corpus and all chunks/vectors |
| 16 | `tube_bridge_help` | No | In-MCP documentation |

**Key:** 13 tools work without an API key; 3 require one.

**Corpus tools note:** All 5 corpus tools need no Data API authentication and embedding generation is local. However, `corpus_add` may fetch a transcript over the network (via `youtube-transcript-api`) when the transcript is not already cached.

### Transports

- **stdio** — MCP client spawns `python3 server.py` as a child process; no inbound listening port/socket; outbound network calls still occur for tool operations (yt-dlp, youtube-transcript-api, Data API v3).
- **Streamable HTTP** (`/mcp`) — stateless; recommended for remote deployments.
- **SSE** (`/sse`) — legacy; deprecated in favor of Streamable HTTP.
- **Health** (`/health`) — always open; returns tool count and auth status.

### Auth (optional)

- `TUBE_BRIDGE_AUTH_KEY` env var enables Bearer-token protection on all remote routes except `/health` (/mcp, /sse, /messages).
- If not set, open access (for local dev).
- Source: `tube_bridge/transport.py` line 66.

### Data API Client

- YouTube Data API v3 calls use Python stdlib `urllib` direct REST (`tube_bridge/youtube/api.py`).
- No `google-api-python-client` dependency exists in the codebase.
- `YOUTUBE_API_KEY` is read from the environment at runtime (`tube_bridge/youtube/api.py` line 12).

### Cache and Corpus Storage

- **Cache:** `cache.db` under `TUBE_BRIDGE_CACHE` directory (default `~/.tube_bridge`). Stores transcripts and video metadata. Source: `tube_bridge/cache.py` line 12.
- **Corpus:** `corpus.db` under the same configured directory. Separate database file. Stores named corpora, chunks, and sqlite-vec vectors. Source: `tube_bridge/corpus.py` line 15.

### Security Model

- Code obtains optional values (API keys, tokens, proxy URLs) from environment variables at runtime.
- No API key, secret, or access material is bundled, embedded, committed, or shipped in the repository.
- The publication policy forbids bundling such material; prior README claims implying bundled access material are stale and have been corrected.

## Demo Endpoint

- **Railway-hosted disposable demo:** `tube-bridge-production.up.railway.app`. This is solely a try-before-install demo, never a SaaS or managed transcript-hosting product.
- **Accepted target, implementation open:** WI-00029 must provide isolated server-side upstream configuration, exactly 5 official Data API operations per observed client IP, deletion of each demo corpus within 10 minutes, and no persistent volume/backups/accounts/durable hosted corpus.
- **Current evidence boundary:** the deployed endpoint proves reachability only; it does not yet prove those quota and retention controls. Self-hosted users remain unaffected and bring their own keys/storage.
- **No shared upstream access material** may be distributed to consumers.
- IPRoyal residential proxy (`TUBE_BRIDGE_PROXY` env var, pay-as-you-go) is the planned transcript bot-detection workaround for the demo.

## Quota Facts (Verified 2026-08-08)

Default allocation documented as 100 search.list calls/day, 100 videos.insert calls/day, and 10,000 units/day combined for other endpoints, subject to change. Additional allocation follows the YouTube API Services audit/quota-extension process. No purchasable quota tier was identified in official Google documentation. Sources:
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.google.com/youtube/terms/developer-policies

The Data API does not provide transcript text; transcripts rely on a separate `youtube-transcript-api`/proxy pipeline.

## Self-Hosted Boundary

tube-bridge is an MIT self-hosted individual MCP. It is never a SaaS or managed transcript-hosting product.

**Open core (MIT licensed):**
- All 16 MCP tools, all transports, all cache/corpus logic.
- Zero-registration workflows: 13 tools usable without any API key.
- Users bring their own `YOUTUBE_API_KEY` for the 3 API-dependent tools.

The Railway demo is solely a disposable try-before-install convenience. There is no commercial extension, product gateway, billing, entitlement, managed higher-quota tier, or extension deployment.

## [Grabbit MCP](https://grabbitapp.com)

Grabbit is a completely separate companion MCP. There is no connector, dependency, shared service, bundled workflow, code integration, or implementation roadmap between tube-bridge and Grabbit. An example agent usage sequence may show that the agent uses tube-bridge to find videos and then separately uses Grabbit to save links — that is the full extent of any documented relationship.

## Browser Extension

A browser extension is outside this project's scope and release gate. It must not be architected, planned, or documented here.

## Core Release-Candidate Evidence

- One runtime `TOOL_CATALOG` defines all 16 tools and derives HELP metadata; stale 10/11-tool claims are removed.
- The packaged synchronous entrypoint is `tube_bridge.cli:main`.
- Ten frozen Python test files produce 125 passing tests without changing the frozen hash.
- Isolated wheel install, installed CLI/MCP handshake, wheel+sdist, `twine check`, SHA-256 dependency lock, and actual Docker authenticated MCP handshake pass.
- Verification: `.brainops/methodology/verification/verification-WI-00028-python-local.json`; Station lifecycle hash/gate/persistence receipts are complete. Final independent conformance is recorded separately and must not be inferred from intermediate audit receipts.

## Publication Readiness

- **Self-hosted core publication is accepted.** GitHub Release, PyPI package, public GHCR image, hosted CI, and post-publication install/container receipts are present.
- **Disposable demo acceptance remains separate.** The 5-operation allowance and 10-minute corpus deletion controls belong to WI-00029 and are not implied by core publication.
- Architecture direction recorded in `docs/adr/001-demo-api-quota-and-product-boundary.md`.
- No production-ready promise, no coverage percentage, no SLA, no pricing, no launch venue, no legal conclusion is asserted.
