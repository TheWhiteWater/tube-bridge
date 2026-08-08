# MVP Scope — tube-bridge

> **Status:** Self-hosted core implementation, runtime acceptance, and publication are complete. Disposable-demo quota/retention implementation remains open under WI-00029. This is a retrospective scope document grounded in shipped code. No commercial extension, product gateway, or Grabbit connector.

## What the Implementation Baseline Contains

The shipped source code (`tube_bridge/` package + root `server.py`) implements the following, verified by inspection of the codebase and documented in `PROJECT_VISION.md` and `README.md`:

### Tool Catalogue: 16 MCP Tools

Total tools registered in `tube_bridge/server.py` `list_tools()`: **10 YouTube interaction + 5 corpus + 1 help = 16**.

| # | Tool | API Key | Notes |
|---|------|:-------:|-------|
| 1 | `youtube_search` | No → Yes | Data API v3 primary when key present; yt-dlp fallback |
| 2 | `youtube_get_video_info` | No → Yes | Full metadata; dual-source with cache |
| 3 | `youtube_get_trending` | No → Yes | API v3 primary; yt-dlp fallback |
| 4 | `youtube_get_channel_videos` | No | Recent uploads from @handle or URL |
| 5 | `youtube_get_playlist` | No | All videos in a playlist |
| 6 | `youtube_get_transcript` | No | Plain text or [MM:SS] timestamps; manual > ASR |
| 7 | `youtube_get_available_languages` | No | Subtitle languages; manual/auto flags |
| 8 | `youtube_get_comments` | **Yes** | Top-level comments with likes |
| 9 | `youtube_search_channels` | **Yes** | Channel search with subscriber filters |
| 10 | `youtube_get_channel_info` | **Yes** | Detailed channel stats |
| 11 | `corpus_create` | No | Named corpus for semantic search |
| 12 | `corpus_add` | No | Auto-fetches transcript (network), chunks, local embeds |
| 13 | `corpus_search` | No | Semantic search with scores and timestamps |
| 14 | `corpus_list` | No | List all corpora with counts |
| 15 | `corpus_delete` | No | Delete corpus and all chunks/vectors |
| 16 | `tube_bridge_help` | No | In-MCP server documentation |

- **13 tools callable without any API key.** The 3 tools requiring `YOUTUBE_API_KEY` are: `youtube_get_comments`, `youtube_search_channels`, `youtube_get_channel_info`.
- Search, video_info, and trending upgrade to Data API v3 results when the key is set; they fall back to yt-dlp when the key is absent or quota is exhausted.

### Transports

- **stdio** — MCP child process transport (local clients)
- **`/mcp`** — Streamable HTTP (recommended for remote deployments)
- **`/sse`** — SSE (legacy; deprecated in favor of Streamable HTTP) plus remote `/messages` POST handler
- **`/health`** — Always-open health check

### Auth

- Optional Bearer-token protection on **every remote route except `/health`** via `TUBE_BRIDGE_AUTH_KEY` environment variable. This includes `/mcp`, `/sse`, and `/messages`. If the env var is not set, open access (local dev). `/health` is always open regardless of auth configuration.

### Data Sources

- **Dual-source architecture:** YouTube Data API v3 (primary, stdlib `urllib`) + yt-dlp subprocess client (fallback) for search, video_info, and trending.
- **Transcripts:** `youtube-transcript-api` with manual > ASR language priority.
- **Data API client:** Python stdlib `urllib` only; no `google-api-python-client` dependency.

### Storage

- **`cache.db`** — SQLite under `~/.tube_bridge/` (configurable via `TUBE_BRIDGE_CACHE`). Stores transcripts and video metadata with persistent caching.
- **`corpus.db`** — Separate SQLite database in the same directory. Stores named corpora, chunks, and sqlite-vec embedding vectors.

### Embeddings

- **fastembed** (BGE-small-en-v1.5, 384-dim) for local embedding inference. Inference runs locally after model assets are available; initial model acquisition may require network download.
- `corpus_add` fetches transcripts over the network (via `youtube-transcript-api`) when not already cached.

### Deployment

- **Railway demo endpoint deployed:** `tube-bridge-production.up.railway.app`. For development and limited testing; not advertised as a public service.

## Evidence Status (Honest Assessment)

| Capability | Status | Evidence |
|-----------|--------|----------|
| 16 tools registered | **Shipped** | `tube_bridge/server.py` `list_tools()` registers exactly 16 `Tool()` objects (source-verified) |
| 13 keyless / 3 API-key | **Shipped** | Verified against `list_tools()` + tool implementations in `tube_bridge/tools.py` (source-verified) |
| Dual-source search/video/trending | **Shipped** | `tube_bridge/tools.py` `search()`, `video_info()`, `trending()` implement dual-source dispatch (source-verified) |
| All 3 transports + /messages + health | **Shipped** | `tube_bridge/transport.py` wires stdio/HTTP/SSE; `/messages` POST handler at line 77–78; health endpoint at line 43–48 (source-verified) |
| Separate cache.db / corpus.db | **Shipped** | `tube_bridge/cache.py` line 13, `tube_bridge/corpus.py` line 15 (source-verified) |
| Local embedding inference | **Shipped** | `tube_bridge/corpus.py` uses fastembed; inference code present in source (source-verified; formal runtime acceptance open) |
| Railway demo exists | **Deployed** | Confirmed endpoint deployed |
| Automated test suite / CI | **Verified** | Core C2: 125 frozen deterministic tests and hosted Python 3.12/3.13 CI pass. `test_tools.py` remains optional live smoke |
| PyPI / install / entrypoint verification | **Published and verified** | Core C3: PyPI install, packaged `tube_bridge.cli:main`, installed MCP runtime, wheel+sdist/twine, and public GHCR runtime pass |
| Demo public access controls | **Decision resolved, not implemented** | Demo D1–D2 P0. Per ADR-001: dedicated GCP project, exactly 5 Data API ops per client/IP. Enforcement not deployed |
| Observability and monitoring | **Decision resolved, not implemented** | Demo D3 P0. Counters/errors for 5-op limit and 10-min TTL. Not deployed |
| Policy / privacy / retention | **Decision resolved, implementation open** | Demo D4 P0. Per ADR-001: no persistent volume, accounts, backups, or durable transcript/corpus hosting. A concise demo data-handling/deletion notice is required; the transient model does not waive applicable privacy, copyright, or YouTube policy obligations |
| Corpus exposure and persistence mode | **Decision resolved, not implemented** | Demo D5 P0. Per ADR-001: every corpus auto-deleted 10 minutes after creation. Self-hosted instances have full persistent corpus storage |

## Excluded from MVP Scope

| Feature | Reason | Status |
|---------|--------|--------|
| Bulk scraping / scheduled harvests | Non-goal per 05_NON_GOALS.md | Excluded |
| Video download or mutation | Read-only tools only per 00_MISSION.md | Excluded |
| Unlimited public demo access | Per ADR-001: exactly 5 Data API ops per client/IP; enforcement not yet implemented (D2 P0) | Blocked (Demo D2 P0) |
| Browser extension | Outside project scope and release gate per ADR-001 | Excluded |
| Grabbit connector or integration | Grabbit is a completely separate MCP per ADR-001; companion MCP example only, no tube-bridge implementation | Excluded |
| Commercial extension / product gateway | No commercial extension, gateway, billing, or managed hosting planned per ADR-001 | Excluded |
| SaaS / managed hosting | tube-bridge is an MIT self-hosted MCP, never a SaaS per ADR-001 | Excluded |

## Definition of Done

### Implementation Baseline (Shipped in Source)

The following core items are verified against source, frozen tests, installed artifacts, hosted CI, PyPI, and the public registry image. Live upstream availability and disposable-demo controls remain separately bounded.

- [x] 16 MCP tools registered in source (`list_tools()` returns exactly 16 `Tool()` objects)
- [x] 13 tools work without API key; 3 with optional `YOUTUBE_API_KEY` (source-verified)
- [x] Dual-source architecture: Data API v3 + yt-dlp implemented in source
- [x] All 3 transports (stdio, `/mcp` Streamable HTTP, `/sse` legacy) plus `/messages` handler and `/health` route (source-verified)
- [x] Separate `cache.db` and `corpus.db` implemented in source
- [x] Local embedding inference (fastembed) implemented in source; formal runtime acceptance open
- [x] Optional Bearer auth on every remote route except `/health` (source-verified in `tube_bridge/transport.py` line 66)
- [x] Railway demo endpoint deployed
- [x] MIT license; open-core source on GitHub

### Core Library Acceptance Gate (Independent of Demo)

Core publication acceptance (Surface 1) has complete C1–C5 evidence plus GitHub Release, PyPI and public GHCR receipts. Core remains independent of the disposable demo.

- [x] C1: one authoritative 16-tool catalog, derived HELP metadata and corrected package docs (P0)
- [x] C2: 125 frozen deterministic tests and hosted Python 3.12/3.13 CI PASS (P0)
- [x] C3: PyPI install, synchronous console entrypoint, installed MCP runtime, wheel+sdist/twine, public GHCR pull and MCP handshake PASS (P0)
- [x] C4: corrected-model independent documentation audit PASS; source/test conformance is tracked by Station methodology receipts (P0)
- [x] C5: package metadata, bounded/public dependencies, exact SHA-256 lock, Docker consumption, MIT license and secret exclusion verified (P0)

### Disposable Demo Acceptance Gate (Independent of Core)

Disposable demo acceptance (Surface 2) requires D1–D5 P0 evidence. D6 and X1–X3 are triaged/conditional. The demo can be withheld while core remains available. All demo decisions are resolved per ADR-001 (accepted 2026-08-08); implementation remains open.

- [ ] D1: Dedicated Google Cloud project and server-side upstream setup, isolated from Operator personal/development configuration (P0)
- [ ] D2: Exactly 5 official YouTube Data API v3 operations per client/IP enforced (P0)
- [ ] D3: Counters/errors observability sufficient to enforce the 5-operation limit and 10-minute corpus TTL (P0)
- [ ] D4: Self-hosted boundary and disposable demo disclosure documented — no persistent volume, accounts, backups, or durable transcript/corpus hosting (P0, decision resolved per ADR-001)
- [ ] D5: 10-minute corpus auto-deletion implemented — every corpus created on the demo is deleted 10 minutes after creation; self-hosted instances have full persistent storage (P0, decision resolved per ADR-001)
- [ ] D6: YouTube API Services audit/quota-extension path (P1 conditional; becomes P0 if demo usage hits default quota ceiling before extension complete)
- [ ] X1–X3: Quota extension, proxy reliability, Railway persistence — triaged conditional (P1); not blocking without threshold breach

### Publication Scope

Only two surfaces have acceptance gates: published self-hosted Core and Disposable Demo. Core publication/runtime acceptance is complete; demo quota/retention implementation remains open. There is no commercial extension, product gateway, Grabbit connector, or browser-extension surface.

**Core implementation and publication are accepted. Disposable-demo acceptance is not.**
