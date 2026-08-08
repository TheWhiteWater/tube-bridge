# MVP Scope — tube-bridge

> **Status:** Implementation baseline shipped in source. Formal runtime acceptance and per-surface publication readiness are **not yet complete**. This is a retrospective scope document grounded in shipped code, not a forward-looking plan.

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
| Automated test suite / CI | **Not shipped** | Core C2 P0. `test_tools.py` is a 4-unique-tool live smoke script (search, video_info, trending, transcript); no full suite, no CI pipeline configured |
| PyPI / install / entrypoint verification | **Unverified** | Core C3 P0. `pyproject.toml` exists with console entrypoint `tube-bridge = "server:main"`; `pip install` from source and entrypoint not verified; package-registry route undecided |
| Demo public access controls | **Proposed, not implemented** | Demo D1–D2 P0. Per ADR-001; dedicated GCP project, per-consumer budgets, rate limiting, abuse controls not deployed |
| Observability and monitoring | **Proposed, not implemented** | Demo D3 P0. Structured logging, metrics export, alerting not deployed |
| Policy / legal / retention | **Decision required** | Demo D4 P0. Operator decisions pending on copyright, privacy, GDPR, retention, deletion |
| Corpus exposure and persistence mode | **Decision required** | Demo D5 P0. Ephemeral, persistent, or disabled mode not chosen; all modes require disclosure and deletion/retention treatment |
| Commercial extension / gateway | **Planned, not implemented** | Extension-only (E1–E4). Proposed product layer; separate launch gates independent of core; does not block core library or controlled demo |

## Excluded from MVP Scope

| Feature | Reason | Status |
|---------|--------|--------|
| Commercial extension / product gateway | Extension-only (E1–E4); separate product layer; core is MIT open-source library; own launch gates independent of core | Planned |
| Grabbit connector (batch video-link collection) | Connector-only (G1–G2); optional independent path; not in core; own launch gates independent of core | Proposed |
| Bulk scraping / scheduled harvests | Non-goal per 05_NON_GOALS.md | Excluded |
| Video download or mutation | Read-only tools only per 00_MISSION.md | Excluded |
| Unlimited public demo access | Budgets and abuse controls not yet implemented; D1–D2 P0 for controlled demo | Blocked (Demo D1–D2 P0) |
| Legal review / copyright compliance | Operator decision pending; D4 P0 for controlled demo per PUBLICATION_READINESS.md | Blocked (Demo D4 P0) |
| Data retention / deletion policy | Operator decision pending; D4 P0 for controlled demo per PUBLICATION_READINESS.md | Blocked (Demo D4 P0) |

## Definition of Done

### Implementation Baseline (Shipped in Source)

The following items are verified against source code (`tube_bridge/` package). Items marked [x] reflect implementation present in source; formal runtime acceptance (live tool invocation, embedding inference, fallback execution) is **not yet complete** and tracked separately.

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

Core library acceptance (Surface 1) requires C1–C5 P0 evidence. C4 is Resolved by the successful official re-audit receipt at `.brainops/methodology/audits/2026-08-08T05-16-06-772Z-64150819-codex/station-codex-audit.json` (verdict: PASS). This resolves documentation coherence only and does not imply runtime/source/test/package/demo acceptance. C1, C2, C3, C5 remain unresolved. Core can be accepted independently of the controlled demo. Existing GitHub availability is not revoked.

- [ ] C1: HELP_TEXT / package-docstring count drift corrected to reflect 16 tools (P0)
- [ ] C2: Deterministic tests and CI — unit/contract tests with mocked upstreams; CI pipeline running on PRs (P0)
- [ ] C3: Installation, entrypoint, and registry verification — `pip install .` from source checkout; console entrypoint `tube-bridge` verified; package-registry route decided (P0)
- [x] C4: Independent docs audit — Resolved with PASS receipt from official Station Codex re-audit (`.brainops/methodology/audits/2026-08-08T05-16-06-772Z-64150819-codex/station-codex-audit.json`, verdict: PASS). Docs coherence verified; does not imply runtime/source/test/package acceptance. (P0)
- [ ] C5: Release configuration and license review — `pyproject.toml` reviewed for publication; MIT license accurate; no bundled secrets (P0)

### Controlled Demo Acceptance Gate (Independent of Core)

Controlled demo acceptance (Surface 2) requires D1–D5 P0 evidence. D6 and X1–X3 are triaged/conditional. The demo can be withheld while core remains available.

- [ ] D1: Dedicated GCP project and server-side upstream setup (P0)
- [ ] D2: Exact budgets, rate limits, abuse controls, and access controls (P0)
- [ ] D3: Monitoring and observability — structured logging, metrics export, alerting configured (P0)
- [ ] D4: Policy, privacy, copyright, retention, and deletion — written policy document (P0)
- [ ] D5: Corpus exposure, persistence, and retention choice — mode chosen and documented (P0)
- [ ] D6: YouTube API Services audit/quota-extension path (P1 conditional; becomes P0 if demo usage hits default quota ceiling before extension complete)
- [ ] X1–X3: Quota extension, proxy reliability, Railway persistence — triaged conditional (P1); not blocking without threshold breach

### Extension and Grabbit Gates (Future, Never Block Core/Demo)

Extension E1–E4 and Grabbit G1–G2 are separate future launch gates and never gate core or controlled demo acceptance. Existing GitHub availability is not revoked.

**Implementation baseline is shipped. Formal runtime acceptance and per-surface publication readiness are not accepted.**
