# MVP Scope — tube-bridge

> **Status:** Self-hosted core implementation/publication and the separately gated disposable-demo P0 controls are complete. This is a retrospective scope document grounded in shipped code and live evidence. No commercial extension, product gateway, or Grabbit connector.

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

- Optional static Bearer protection on the three remote MCP routes (`/mcp`, `/sse`, `/messages`) via `TUBE_BRIDGE_AUTH_KEY`; `/health` is always public. When OAuth is enabled, its discovery, registration, authorization and token endpoints are intentionally public protocol routes while MCP routes remain protected. If neither auth mechanism is set, self-hosted HTTP remains open for local development.

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

- **Railway disposable demo deployed:** `tube-bridge-production.up.railway.app`. Controlled try-before-install surface; not a SaaS, durable corpus host, or managed service.

## Evidence Status (Honest Assessment)

| Capability | Status | Evidence |
|-----------|--------|----------|
| 16 tools registered | **Shipped** | `tube_bridge/server.py` `list_tools()` registers exactly 16 `Tool()` objects (source-verified) |
| 13 keyless / 3 API-key | **Shipped** | Verified against `list_tools()` + tool implementations in `tube_bridge/tools.py` (source-verified) |
| Dual-source search/video/trending | **Shipped** | `tube_bridge/tools.py` `search()`, `video_info()`, `trending()` implement dual-source dispatch (source-verified) |
| All 3 transports + /messages + health | **Shipped** | `tube_bridge.cli` owns stdio-vs-HTTP selection; `tube_bridge.transport` wires HTTP/SSE, `/messages`, `/health`, auth and identity (source-verified) |
| Separate cache.db / corpus.db | **Shipped** | Distinct `tube_bridge.cache.DB_PATH` and `tube_bridge.corpus.DB_PATH` authorities (source-verified) |
| Local embedding inference | **Shipped** | `tube_bridge/corpus.py` uses fastembed; inference code present in source (source-verified; formal runtime acceptance open) |
| Railway demo exists | **Deployed** | Confirmed endpoint deployed |
| Automated test suite / CI | **Verified** | Core C2 retains its 125-test freeze; the accepted demo baseline reached 209 tests and the current cumulative suite with the 64-test OAuth addendum is 273 deterministic tests with hosted Python 3.12/3.13 CI PASS. `test_tools.py` remains optional live smoke |
| PyPI / install / entrypoint verification | **Published and verified** | Core C3: PyPI install, packaged `tube_bridge.cli:main`, installed MCP runtime, wheel+sdist/twine, and public GHCR runtime pass |
| Demo public access controls | **Accepted** | Dedicated server-side config; Railway-overwritten `X-Real-IP`; one bucket across spoof attempts; exactly 5 allows and structured sixth rejection; restart reset |
| Optional OAuth test identity | **Deployed; final UI gate pending** | Invite-gated DCR/Authorization Code/PKCE, Operator/Tester aggregates, static-Bearer coexistence and unchanged quota counters pass deterministic/source/CI/live-protocol gates; real Claude Custom Connector authorization/tool call remains |
| Observability and monitoring | **Accepted** | Aggregate `/health` counters, structured policy errors, no raw identity persistence, application access log disabled; known probe identities absent from Railway application logs |
| Policy / privacy / retention | **Accepted** | README data-handling notice; no persistent volume, accounts, backups, or durable hosting promise. Transient operation does not waive external policy obligations |
| Corpus exposure and persistence mode | **Accepted** | Persisted 600-second deadline, nearest-deadline/reconciliation worker, transactional relational/vector deletion, deterministic race coverage, and live non-invasive deletion observation. Self-hosted storage remains persistent |

## Excluded from MVP Scope

| Feature | Reason | Status |
|---------|--------|--------|
| Bulk scraping / scheduled harvests | Non-goal per 05_NON_GOALS.md | Excluded |
| Video download or mutation | Read-only tools only per 00_MISSION.md | Excluded |
| Unlimited public demo access | Contrary to ADR-001 and the accepted exactly-5 process-lifetime allowance | Excluded; bounded demo is active |
| Browser extension | Outside project scope and release gate per ADR-001 | Excluded |
| Grabbit connector or integration | Grabbit is a completely separate MCP per ADR-001; companion MCP example only, no tube-bridge implementation | Excluded |
| Commercial extension / product gateway | No commercial extension, gateway, billing, or managed hosting planned per ADR-001 | Excluded |
| SaaS / managed hosting | tube-bridge is an MIT self-hosted MCP, never a SaaS per ADR-001 | Excluded |

## Definition of Done

### Implementation Baseline (Shipped in Source)

The following core items are verified against source, frozen tests, installed artifacts, hosted CI, PyPI, and the public registry image. Disposable-demo controls are separately verified; live upstream availability remains an operational limitation.

- [x] 16 MCP tools registered in source (`list_tools()` returns exactly 16 `Tool()` objects)
- [x] 13 tools work without API key; 3 with optional `YOUTUBE_API_KEY` (source-verified)
- [x] Dual-source architecture: Data API v3 + yt-dlp implemented in source
- [x] All 3 transports (stdio, `/mcp` Streamable HTTP, `/sse` legacy) plus `/messages` handler and `/health` route (source-verified)
- [x] Separate `cache.db` and `corpus.db` implemented in source
- [x] Local embedding inference (fastembed) implemented in source; formal runtime acceptance open
- [x] Static Bearer auth on `/mcp`, `/sse`, and `/messages` with public `/health` remains compatible
- [x] Optional fail-closed OAuth/DCR/PKCE adapter, invite roles and aggregate-only auth metrics implemented and Railway protocol-verified
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

Disposable demo acceptance (Surface 2) has D1–D5 P0 evidence. D6 and X1–X2 remain triaged with event-based review triggers; X3 is N/A while no volume is attached. The demo can still be withheld independently while core remains available.

- [x] D1: Dedicated Google Cloud project and server-side upstream setup, isolated from Operator personal/development configuration (P0)
- [x] D2: Exactly 5 attempted official YouTube Data API v3 operations per Railway-observed client IP/process enforced and live-probed (P0)
- [x] D3: Aggregate counters/structured errors enforce the allowance and expose TTL configuration without raw identity (P0)
- [x] D4: Self-hosted boundary and disposable demo data-handling disclosure documented; no volume/accounts/backups/durable hosting (P0)
- [x] D5: Persisted 10-minute corpus deadline with transactional auto-deletion deterministically and live verified; self-hosted storage remains persistent (P0)
- [ ] D6/X1: YouTube audit/quota-extension path (P1 conditional); review before broad announcement and when demand approaches default allocation; becomes P0 if the ceiling is hit first
- [ ] X2: Proxy reliability (P1 conditional); review before broad announcement and on an Operator-observed availability-threshold breach
- [x] X3: Railway persistence/backups N/A for the accepted no-volume, non-durable demo
- [ ] D7: OAuth source/CI/Railway handshake complete; real Claude Custom Connector UI authorization and tool call plus final sign-off remain

### Publication Scope

Only two surfaces have acceptance gates: published self-hosted Core and Disposable Demo. Both P0 gates are complete and remain independent. There is no commercial extension, product gateway, Grabbit connector, or browser-extension surface.

**Core implementation/publication and disposable-demo P0 controls are accepted independently.**
