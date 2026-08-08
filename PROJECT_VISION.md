# Project Vision — tube-bridge

**Last updated:** 2026-08-08
**Status:** MIT open-core library; hosted demo endpoint deployed; controlled public demo access model proposed, not yet ready for broad promotion. Full-publication readiness not yet accepted.

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

- **Railway-hosted endpoint deployed:** `tube-bridge-production.up.railway.app`.
- **Dedicated Google Cloud project proposed (P0)** for demo Data API access; accepted as architecture but pending Operator provisioning evidence. Auth material would be held server-side only.
- **Controlled public demo access model proposed, not yet ready:** strict per-user/IP and global daily budgets with abuse controls and observability are planned but not yet fully implemented. Until these controls are in place, the demo endpoint exists for development and limited testing — it is not advertised as a public service.
- **No shared upstream access material** would be distributed to extension consumers.
- IPRoyal residential proxy (`TUBE_BRIDGE_PROXY` env var, pay-as-you-go) for transcript bot-detection workaround.

## Quota Facts (Verified 2026-08-08)

Default allocation documented as 100 search.list calls/day, 100 videos.insert calls/day, and 10,000 units/day combined for other endpoints, subject to change. Additional allocation follows the YouTube API Services audit/quota-extension process. No purchasable quota tier was identified in official Google documentation. Sources:
- https://developers.google.com/youtube/v3/determine_quota_cost
- https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- https://developers.google.com/youtube/terms/developer-policies

The Data API does not provide transcript text; transcripts rely on a separate `youtube-transcript-api`/proxy pipeline.

## Open-Core Boundary

**Open core (MIT licensed):**
- All 16 MCP tools, all transports, all cache/corpus logic.
- Zero-registration workflows: 13 tools usable without any API key.
- Users bring their own `YOUTUBE_API_KEY` for the 3 API-dependent tools.

**Proposed extension (separate commercial product layer):**
- Reuses the tube-bridge engine but is a distinct product.
- Requires a server-side product gateway for entitlements, usage enforcement, billing, trial management, and support.
- Physical deployment may reuse services (an architecture decision, not precluded).
- Features: trial/paid transcript and research capabilities; per-user quota, abuse controls, observability.

**Grabbit integration (optional connector):**
- Batch video-link collection workflow: save YouTube links into Grabbit collections.
- Transcript and research attachment to Grabbit items.
- Cross-promotion between tube-bridge extension and Grabbit.
- Not required for core tube-bridge operation; an independent opt-in path.

## Known Code/Docs Inconsistencies

These are documented readiness issues requiring source correction; they should not be interpreted as current facts:

- `tube_bridge/server.py` line 20: `HELP_TEXT` defines numeric `"tools": 11` but the duplicate `"tools"` key on line 28 (an 11-entry object listing 10 interaction tools + help) overwrites the numeric value at runtime. The help list omits the 5 corpus tools. `list_tools()` registers 16 tools (10 YouTube interaction + 5 corpus + 1 help). Source correction needed.
- `tube_bridge/__init__.py` docstring (lines 1–5) claims "10 tools." Source correction needed.
- `pyproject.toml` line 17: console entrypoint `tube-bridge = "server:main"` requires `pip install` verification before any PyPI publication claim.

## Publication Readiness

- **Full-publication readiness is not yet accepted.** A decision-ready checklist is maintained in `docs/planning/PUBLICATION_READINESS.md`.
- Architecture direction recorded in `docs/adr/001-demo-api-quota-and-product-boundary.md`.
- No production-ready promise, no coverage percentage, no SLA, no pricing, no launch venue, no legal conclusion is asserted.
