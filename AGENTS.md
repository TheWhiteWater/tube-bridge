# AGENTS.md — tube-bridge

**Project:** YouTube MCP server for AI agents — 16 tools
**Stack:** Python 3.12+, MCP 1.28.1, yt-dlp, youtube-transcript-api, sqlite-vec, fastembed
**Transport:** stdio + Streamable HTTP (/mcp) + SSE (/sse, legacy)
**License:** MIT

## Quick Start

```bash
pip install mcp==1.28.1 yt-dlp youtube-transcript-api starlette uvicorn sqlite-vec fastembed
python3 server.py              # stdio
python3 server.py --http       # HTTP on :8080
python3 test_tools.py          # live smoke test (not an automated suite)
```

## Architecture

```
tube_bridge/
├── server.py          # MCP wiring: 16-tool registration (list_tools) + dispatch (call_tool)
├── tools.py           # All tool implementations (async, cached, dual-source)
├── transport.py       # Streamable HTTP (/mcp) + SSE (/sse, legacy) + stdio + optional Bearer auth
├── cache.py           # Persistent SQLite cache (cache.db) — transcript + video metadata tables
├── corpus.py          # Semantic search (corpus.db) — sqlite-vec vectors + fastembed (local)
└── youtube/
    ├── client.py      # yt-dlp subprocess (retry + exponential backoff + proxy)
    ├── api.py         # YouTube Data API v3 client — stdlib urllib only, no Google SDK
    ├── transcript.py  # youtube-transcript-api (manual > ASR, proxy)
    └── models.py      # VideoInfo dataclass
```

## Tools (16)

Registered in `tube_bridge/server.py` `list_tools()` (lines 67–248). Confirmed from source.

| # | Tool | API Key | Notes |
|---|------|:---:|-------|
| 1 | `youtube_search` | No→Yes | Dual-source: API v3 primary, yt-dlp fallback |
| 2 | `youtube_search_channels` | Yes | Channel search, subscriber filters |
| 3 | `youtube_get_channel_info` | Yes | Channel stats: subs, views, country, keywords |
| 4 | `youtube_get_video_info` | No→Yes | Cached (lru_cache 64), dual-source |
| 5 | `youtube_get_trending` | No→Yes | API v3 primary, yt-dlp fallback |
| 6 | `youtube_get_channel_videos` | No | Recent uploads from @handle or URL |
| 7 | `youtube_get_playlist` | No | All videos in a playlist |
| 8 | `youtube_get_transcript` | No | Plain text or [MM:SS] timestamps, Manual > ASR |
| 9 | `youtube_get_available_languages` | No | Subtitle languages, manual vs auto-generated |
| 10 | `youtube_get_comments` | Yes | Top-level comments via Data API v3 |
| 11 | `corpus_create` | No | Named corpus, fixed embedding model |
| 12 | `corpus_add` | No | Fetches transcript (network), chunks locally, embeds locally |
| 13 | `corpus_search` | No | Semantic search: scores, timestamps, video IDs |
| 14 | `corpus_list` | No | List corpora with chunk + video counts |
| 15 | `corpus_delete` | No | Delete corpus and all chunks/vectors |
| 16 | `tube_bridge_help` | No | In-MCP docs: tools, architecture, limitations |

13 callable without API key; 3 require one.

## Storage

- **`cache.db`** — persistent SQLite database for transcript segments and video metadata. Path: `$TUBE_BRIDGE_CACHE/cache.db` (default: `~/.tube_bridge/cache.db`). Tables: `transcripts`, `video_info`.
- **`corpus.db`** — separate SQLite database for semantic search corpora. Same directory as `cache.db`. Tables: `corpora`, `corpus_chunks`, `corpus_added_videos`, plus per-corpus sqlite-vec virtual tables.

Both databases live under the same configurable directory but are distinct files and schemas.

## Data API Client

- YouTube Data API v3 calls use Python stdlib `urllib.request` directly (`tube_bridge/youtube/api.py`).
- No `google-api-python-client` or any third-party Google SDK is a dependency.
- `YOUTUBE_API_KEY` is read from the environment at runtime; no key is bundled or committed.

## Transports & Auth

- **stdio** — child-process transport for local MCP clients.
- **Streamable HTTP** (`/mcp`) — recommended for remote deployments.
- **SSE** (`/sse`) — legacy, deprecated in favor of Streamable HTTP.
- **`/health`** — always open, returns tool count and auth status.
- **Optional Bearer auth** — `TUBE_BRIDGE_AUTH_KEY` env var protects all remote routes except `/health` (/mcp, /sse, /messages). Sourced at `tube_bridge/transport.py` line 66.

## Conventions

- **Dual-source:** API v3 primary, yt-dlp fallback for search, video_info, trending
- **Cached:** SQLite persistent (cache.db) + lru_cache hot layer (64 for video_info, 32 for transcripts)
- **Retry:** 2 retries with exponential backoff for yt-dlp subprocess
- **Proxy:** `TUBE_BRIDGE_PROXY` env var → both yt-dlp and transcript API
- **Embeddings:** fastembed (BGE-small-en-v1.5, 384-dim); local inference after model assets are available; initial model acquisition may require network; no embedding API setup
- **Single package:** one `tube_bridge/` directory; no required external database/vector/embedding service; YouTube upstream network is required; proxy is optional

## Testing

```bash
python3 test_tools.py          # live smoke script only
```

`test_tools.py` remains an optional live smoke. The acceptance suite is the frozen `tests/` tree: 125 deterministic tests covering all 16 tools, package/install, SQLite lifecycle, real MCP transport, and Docker. `.github/workflows/ci.yml` is configured; hosted evidence requires an authorized push.

## Operational Guardrails

### Decision Sources
- `PROJECT_VISION.md` — product boundaries, tool baseline, open-core scope.
- `docs/planning/PUBLICATION_READINESS.md` — readiness checklist; full-publication readiness is not yet accepted.
- `docs/adr/001-demo-api-quota-and-product-boundary.md` — architecture direction for demo access, quota management, and product separation.

### No Direct Client-Side Upstream Access Material
- tube-bridge obtains optional API keys, tokens, and proxy URLs from environment variables at runtime.
- Do NOT bundle, embed, commit, or ship any API key, secret, or access material in the repository.
- Prior README claims implying bundled credentials are stale and have been corrected.

### Core vs Demo vs Grabbit Boundary
- **Core (MIT):** All 16 tools, all transports, cache/corpus logic — open source, zero registration for 13 tools.
- **Demo (Railway, disposable):** Try-before-install only. Exactly 5 Data API operations per client/IP, corpora auto-delete after 10 minutes. No persistence, accounts, SaaS, or managed hosting.
- **Grabbit (separate MCP):** Completely separate MCP. No connector, dependency, shared service, code integration, or implementation roadmap exists. An example agent usage sequence may show the agent using tube-bridge to find videos and then separately using Grabbit to save links — that is the full extent of any documented relationship.

### Source/Test Changes
- Source and test changes require corresponding tests and independent acceptance.
- `test_tools.py` is an optional live smoke; the frozen deterministic suite is the acceptance authority.
- Verify against runtime source (`tube_bridge/server.py` `list_tools()`) before citing tool counts.

### Publication Readiness
- **Full-publication readiness is not yet accepted.** Do not claim PyPI publication, completed CI, production acceptance, one-click deployment, legal compliance, or any production-ready promise.
- Documented readiness issues (P0/P1/P2) are tracked in `docs/planning/PUBLICATION_READINESS.md`.

## Core Release-Candidate State

1. `TOOL_CATALOG` is the single runtime source for 16 registered tools and derived HELP metadata.
2. Package documentation states 16 tools.
3. The installed synchronous entrypoint is `tube_bridge.cli:main`; isolated wheel install and MCP runtime are verified.
4. Frozen suite, Docker handshake, build/twine and independent audit pass. External publication remains Operator-gated.

## Key Docs

| Document | Path |
|----------|------|
| README (public) | README.md |
| Project Vision | PROJECT_VISION.md |
| Publication Readiness | docs/planning/PUBLICATION_READINESS.md |
| ADR-001 (Demo/Quota/Boundary) | docs/adr/001-demo-api-quota-and-product-boundary.md |
| Architecture | docs/constitution/02_ARCHITECTURE.md |
| Data Model | docs/constitution/03_DATA_MODEL.md |
| Non-Goals | docs/constitution/05_NON_GOALS.md |
| ADR Rules | docs/constitution/06_ADR_RULES.md |
| Open Questions | docs/planning/OPEN_QUESTIONS.md |

## Dependencies

```
mcp>=1.28.1
yt-dlp
youtube-transcript-api
starlette
uvicorn
sqlite-vec
fastembed
```
