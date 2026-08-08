# 01 — System Context

## What tube-bridge is

An MCP (Model Context Protocol) server that lets AI agents interact with YouTube:
- Search videos (dual-source: Data API v3 primary, yt-dlp fallback)
- Get transcripts (plain text or timestamped, manual > ASR priority)
- Discover trending content
- Browse channels and playlists
- Extract video metadata (cached, dual-source)
- Read comments (via optional Data API v3)
- Build semantic search corpora over transcripts (local embeddings via fastembed + sqlite-vec; transcript fetching over network)

## Where it fits

```
AI Agent (Claude / Codex / Hermes / Cursor)
  │
  │  MCP protocol (JSON-RPC) over:
  │    • stdio (local child process, installed `tube-bridge` or compatibility root server.py)
  │    • Streamable HTTP /mcp (remote, recommended, tube_bridge/transport.py)
  │    • SSE /sse (legacy, deprecated, tube_bridge/transport.py)
  │
  ▼
tube-bridge (modular Python package)
  │
  ├── server.py                    — Source-checkout compatibility launcher
  ├── tube_bridge/cli.py           — Canonical synchronous installed entrypoint: stdio or HTTP
  ├── tube_bridge/server.py        — Single 16-tool catalog, MCP registration, HELP derivation + dispatch
  ├── tube_bridge/tools.py         — All tool implementations (async, cached, dual-source)
  ├── tube_bridge/transport.py     — HTTP/SSE ASGI routes only (no stdio) + optional Bearer auth + /health
  ├── tube_bridge/cache.py         — Persistent SQLite cache (cache.db)
  ├── tube_bridge/corpus.py        — Semantic search (corpus.db, sqlite-vec + fastembed)
  └── tube_bridge/youtube/
      ├── client.py       — yt-dlp subprocess (retry + exponential backoff + proxy)
      ├── api.py          — YouTube Data API v3 (stdlib urllib, no Google SDK)
      ├── transcript.py   — youtube-transcript-api (manual > ASR, proxy)
      └── models.py       — VideoInfo dataclass
  │
  ├── youtube-transcript-api  →  YouTube TimedText API (no auth)
  ├── yt-dlp (subprocess)     →  YouTube InnerTube API (no auth)
  └── YouTube Data API v3     →  Google API (optional, key required)
       │
       ▼
    YouTube servers
```

## Transport & Client Architecture

tube-bridge supports three transports, all built from the same MCP server instance:

1. **stdio** — Selected by the packaged `tube-bridge` command (`tube_bridge.cli:main`), which runs the async MCP stdio loop through `asyncio.run()`. Root `server.py` delegates to the same CLI for source-checkout compatibility.

2. **Streamable HTTP (`/mcp`)** — Built by `tube_bridge/transport.py` via `StreamableHTTPSessionManager` (stateless). Recommended for remote deployments. Launched with `tube-bridge --http`.

3. **SSE (`/sse`, legacy)** — Built by `tube_bridge/transport.py` via `SseServerTransport`. Deprecated in favor of Streamable HTTP.

`tube_bridge/transport.py` builds the HTTP/SSE ASGI routes (`/mcp`, `/sse`, `/messages`, `/health`); CLI runtime selection owns stdio.

Additional endpoints:
- **`/health`** — Always open. Returns tool count (16) and auth status.
- **Optional Bearer auth** — `TUBE_BRIDGE_AUTH_KEY` protects every remote route except `/health`, including `/mcp`, `/sse`, and `/messages`. `/health` remains open. Source authority: `_get_auth_key()`/`_check_auth()` in `tube_bridge/transport.py`.

## Outbound Sources & Trust Boundaries

tube-bridge makes outbound calls to three distinct sources. All API keys, tokens, and proxy URLs are obtained from environment variables at runtime; none are bundled, embedded, or committed.

| Source | Module | Auth | Purpose |
|--------|--------|------|---------|
| `youtube-transcript-api` | `tube_bridge/youtube/transcript.py` | None | Transcript extraction (TimedText API). Proxy supported via `TUBE_BRIDGE_PROXY`. |
| `yt-dlp` (subprocess) | `tube_bridge/youtube/client.py` | None | Search, metadata, channels, playlists, trending (InnerTube API). 2 retries with exponential backoff (`1.5 ** attempt`). Proxy supported via `TUBE_BRIDGE_PROXY`. |
| YouTube Data API v3 | `tube_bridge/youtube/api.py` | `YOUTUBE_API_KEY` env var | Comments, channel search, channel info, upgraded search/video_info/trending. Uses Python stdlib `urllib` directly — no `google-api-python-client` dependency. |

### External Service Qualification

- The core requires **no external database, vector store, or embedding API service** — sqlite-vec and fastembed inference run locally after model assets are available; initial model acquisition may require network.
- However, the core **does rely on external YouTube upstreams**: the YouTube TimedText API (via youtube-transcript-api), YouTube InnerTube API (via yt-dlp subprocess), and optionally YouTube Data API v3. Network connectivity to YouTube servers is required for all tools except `corpus_list`, `corpus_delete`, `corpus_search` (when corpus already populated), and `tube_bridge_help`.

### Trust Boundaries

- **No bundled credentials** — All sensitive values (API keys, proxy URLs, auth tokens) are read from environment variables at runtime. No key is committed to the repository.
- **Graceful degradation** — When `YOUTUBE_API_KEY` is absent or quota is exhausted, tools fall back to yt-dlp for search, video_info, and trending. Tools that require the Data API (comments, channel search, channel info) return a clear error message.
- **Subprocess isolation** — yt-dlp runs as a subprocess with configurable timeouts. Rationale: explicit timeout control, captured stdout/stderr, 2-retry with exponential backoff, and process isolation. Failures are captured and surfaced as structured errors, not as crashes.
- **Transcript pipeline independence** — Transcripts are obtained via `youtube-transcript-api`, not through the Data API (which does not provide transcript text). A proxy (`TUBE_BRIDGE_PROXY`) can be configured to work around datacenter IP bot detection.

## Local Storage

- **`cache.db`** — Persistent SQLite database for transcript segments and video metadata. Default path: `~/.tube_bridge/cache.db` (configurable via `TUBE_BRIDGE_CACHE`). Tables: `transcripts` (video_id, lang, segments, language, is_generated), `video_info` (video_id, data).
- **`corpus.db`** — Separate SQLite database for semantic search corpora. Same directory as `cache.db`. Tables: `corpora`, `corpus_chunks`, `corpus_added_videos`, plus per-corpus sqlite-vec virtual tables. Embeddings generated via fastembed (BGE-small-en-v1.5); inference runs locally after model assets are available; initial model download may require network.

## Integration Points

1. **MCP Clients** — Any MCP-compatible client (Claude Desktop, Cursor, Codex, Hermes Agent). Supports stdio and HTTP transports.
2. **BrainOps Station** — Project lifecycle, TME operating map, ADR records.
3. **Optional: YouTube Data API v3** — For comment extraction, channel search, channel info, and higher-quality search/video_info/trending. Users bring their own key from Google Cloud Console.

## Product Boundaries

- **Core (MIT self-hosted)** — All 16 MCP tools, all transports, all cache/corpus logic. Zero registration for 13 tools. Users bring their own `YOUTUBE_API_KEY` for the 3 API-dependent tools.
- **Demo (Railway, disposable)** — Controlled try-before-install endpoint at `tube-bridge-production.up.railway.app`, not SaaS or managed hosting. WI-00029 accepted isolated server-side configuration, Railway-overwritten `X-Real-IP`, exactly 5 attempted Data API operations per observed IP/process, memory-only privacy-preserving counters, 10-minute transactional corpus deletion, and no volume/backups/accounts/durable hosting.
- **Grabbit (separate MCP)** — Completely separate MCP. No connector, dependency, shared service, code integration, or implementation roadmap exists between tube-bridge and Grabbit. An example agent usage sequence may show the agent using tube-bridge to find videos and then separately using Grabbit to save links — that is the full extent of any documented relationship.
- **Browser extension** — Outside this project's scope and release gate. Not architected, planned, or documented here.
