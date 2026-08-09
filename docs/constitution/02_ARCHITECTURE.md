# 02 — Architecture

## Overview

tube-bridge is a **modular Python package** (`tube_bridge/`) with a packaged synchronous CLI and a root compatibility launcher. It wraps three data sources behind a unified MCP interface with 16 tools:

```
Agent (Claude / Codex / Hermes)
   │ MCP JSON-RPC over:
   │   • stdio (tube_bridge.cli → mcp.server.stdio)
   │   • Streamable HTTP /mcp (tube_bridge/transport.py)
   │   • SSE /sse (legacy, tube_bridge/transport.py)
   ▼
server.py                       — Source-checkout compatibility wrapper
tube_bridge/cli.py              — Canonical synchronous installed CLI: stdio or HTTP
tube_bridge/server.py           — 16-tool catalog, MCP wiring, HELP derivation, and separately verified dispatch
tube_bridge/tools.py            — 15 operational tool implementations (async, cached, dual-source); tube_bridge_help is handled directly in server.py
tube_bridge/transport.py        — HTTP/SSE ASGI app builder + optional static Bearer + /health
tube_bridge/cache.py            — cache.db: persistent SQLite for transcripts + video metadata
tube_bridge/corpus.py           — corpus.db: sqlite-vec vectors + fastembed embeddings
tube_bridge/youtube/
   ├── client.py       — yt-dlp subprocess (retry, backoff, proxy)
   ├── api.py          — Data API v3 client (stdlib urllib, no Google SDK)
   ├── transcript.py   — youtube-transcript-api (manual > ASR, proxy)
   └── models.py       — VideoInfo dataclass
```

## Transport Layer

**Packaged CLI** (`tube_bridge/cli.py`):
- Exposes synchronous `main()` for the `tube-bridge` console script and calls the async runtime via `asyncio.run()`.
- Parses `--http`, `--port`, `--host`; selects MCP stdio or uvicorn HTTP.
- Root `server.py` imports and delegates to this same entrypoint for source-checkout compatibility.

**Transport builder** (`tube_bridge/transport.py`):
- Builds a raw ASGI app routing `/mcp`, `/sse`, `/messages`, `/health`.
- `/mcp`: `StreamableHTTPSessionManager` (stateless) — recommended for remote deployments.
- `/sse`: `SseServerTransport` with `/messages` POST handler — legacy, deprecated.
- `/health`: Always-open JSON endpoint returning tool count and static-auth status.
- Optional `TUBE_BRIDGE_AUTH_KEY` protects `/mcp`, `/sse`, and `/messages`; no auth configuration retains open self-host behavior.
- Lifespan: `http_manager.run()` started/stopped with ASGI lifespan events; session manager lifecycle is tied to the server process.
- **Note:** `transport.py` builds HTTP/SSE ASGI routes only; packaged CLI runtime selection handles stdio.

## Tool Registration & Dispatch

**Tool registration** (`tube_bridge/server.py`):
- `TOOL_CATALOG` is the single authority for exactly 16 registered names, descriptions and JSON input schemas; `list_tools()` returns its MCP `Tool` objects.
- 10 YouTube interaction tools + 5 corpus tools + 1 help tool.
- Each tool schema declares required parameters, optional parameters with defaults, and type constraints. Not every schema contains enum constraints; schemas use standard JSON Schema `type` declarations (`string`, `integer`, `boolean`, `object`).

**Tool dispatch** (`tube_bridge/server.py` `call_tool()` + `_handle_tool()`):
- `call_tool()` wraps the result in `TextContent` with JSON serialization.
- Errors have explicit branches for `ValueError`, `RuntimeError`, and generic `Exception`, returned as structured tool payloads.
- `_handle_tool()` is a separate `match`/`case` dispatcher routing tool names to async implementation functions in `tube_bridge/tools.py`.

`HELP_TEXT` is derived from `TOOL_CATALOG`. Dispatch remains separate; frozen catalog/help/schema/dispatch tests enforce exactly the same 16-name set.

## Tool Implementation Patterns

Fifteen operational tool implementations are delegated to `tube_bridge/tools.py`; `tube_bridge_help` is handled directly in `tube_bridge/server.py` by returning `HELP_TEXT`:

### Dual-Source Pattern (search, video_info, trending)

Tools that work with or without an API key follow the same pattern:
1. Check `api.get_api_key()` — if present and non-empty, call the Data API v3 path first.
2. On `QUOTA_EXCEEDED`, fall through to the yt-dlp path.
3. On other RuntimeErrors, propagate the error.
4. If no key is set, go directly to the yt-dlp path.

Source: `tube_bridge/tools.py` functions `search()`, `video_info()`, and `trending()`.

### Async-to-Thread Boundaries

CPU-bound and I/O-bound synchronous code is wrapped with `asyncio.to_thread()`:
- `video_info()` → `_video_info_cached()` (LRU-cached, checks persistent cache before live fetch)
- `transcript()` → `_get_transcript_with_meta()` (persistent-cache-first)
- `trending()` → `_trending_sync()`
- `channel_videos()` → `_channel_videos_sync()`
- `playlist()` → `_playlist_sync()`
- `comments()`, `channel_info()`, `search_channels()` → `api.*()` calls
- All 5 corpus functions → `corpus.*()` calls

### Caching Strategy

Two-layer cache for transcripts and video metadata:
1. **Persistent SQLite cache** (`tube_bridge/cache.py`):
   - `cache.db` under `TUBE_BRIDGE_CACHE` directory (default: `~/.tube_bridge`).
   - Tables: `transcripts` (video_id, lang, segments JSON, language, is_generated, cached_at), `video_info` (video_id, data JSON, cached_at).
   - WAL journal mode for concurrent read safety.
2. **In-memory LRU cache:**
   - `@functools.lru_cache(maxsize=64)` on `_video_info_cached()`.
   - `@functools.lru_cache(maxsize=32)` on `_get_transcript_cached()`.
   - Hot layer sits on top of persistent cache; both are checked before live fetches.

### Transcript Priority

`tube_bridge/youtube/transcript.py` implements manual > ASR priority:
1. List available transcripts via `youtube-transcript-api`.
2. Segregate into manual (`not t.is_generated`) and auto-generated (`t.is_generated`).
3. If a language code is specified, filter both lists.
4. Try manual transcripts first, then auto-generated, then a direct `fetch()` call as last resort.
5. Lazy singleton `_get_api()` reuses the API instance; proxy configuration is applied at first instantiation.

### Retry & Resilience

`tube_bridge/youtube/client.py`:
- `run_ytdlp()` and `run_ytdlp_multi()` both implement 2 retries with exponential backoff (`1.5 ** attempt` seconds).
- Timeout is configurable per call (default 30–60s depending on operation).
- `TUBE_BRIDGE_PROXY` env var is applied to all yt-dlp subprocess calls.
- Stderr is captured and returned alongside results. ytdlp helpers (`run_ytdlp`, `run_ytdlp_multi`) return stderr as a string.

### Stderr Handling

- ytdlp helper functions (`run_ytdlp`, `run_ytdlp_multi`) return stderr as a string (second element of the tuple).
- Individual tool functions expose `_warning` on the result dict mainly when list results are empty (e.g., `if stderr and not videos: result["_warning"] = stderr`). This pattern appears in `search`, `trending`, `channel_videos`, and `playlist`.
- `video_info` may set `_ytdlp_stderr` on the result dict when stderr is present.

## Data API Client

`tube_bridge/youtube/api.py`:
- Uses Python stdlib `urllib.request` for all Data API v3 calls — no `google-api-python-client` dependency.
- `get_api_key()` reads `YOUTUBE_API_KEY` from environment at runtime.
- `api_call()` is the central request function: builds URL, makes GET request, handles HTTP errors and quota-exceeded with structured `RuntimeError` messages.
- Provides: `search_videos()`, `search_channels()`, `channel_info()`, `get_comments()`, `get_trending()`, `get_video_info()`.

## Corpus Engine

`tube_bridge/corpus.py` provides semantic search over YouTube transcripts:

**Storage:**
- `corpus.db` — separate SQLite database from `cache.db`, same configurable directory.
- Tables: `corpora` (corpus_id, label, embedding_model, created_at, nullable expires_at), `corpus_chunks` (id, corpus_id, video_id, start_ts, end_ts, text, added_at), `corpus_added_videos` (corpus_id, video_id, added_at).
- Per-corpus sqlite-vec virtual tables: `vec_{corpus_id}` with float embedding columns.

**Embedding:**
- fastembed with BGE-small-en-v1.5 (384-dim). Inference runs locally after model assets are available; initial model download may require network. Zero API keys.
- Model is lazy-loaded on first use via `_get_embedding_model()`.
- Model name configurable via `TUBE_BRIDGE_EMBEDDING_MODEL` env var.
- Each corpus records its embedding model at creation time; model mismatch on add/search raises an error.

**corpus_add workflow:**
1. `tube_bridge/tools.py` `corpus_add()` first fetches the transcript via `_get_transcript_with_meta()` (which checks cache, then calls youtube-transcript-api over the network).
2. Passes transcript segments to `tube_bridge/corpus.py` `corpus_add()`.
3. Chunks segments into overlapping windows via `_chunk_transcript()`. The default window is **80 seconds** with a **20-second overlap** (`window_sec=80, overlap_sec=20`).
4. Embeds each chunk with fastembed (locally after model assets are available).
5. Stores chunks in `corpus_chunks` table and vectors in per-corpus sqlite-vec virtual table.
6. Idempotent: `corpus_added_videos` table prevents duplicate indexing. `force_reembed=True` bypasses this.

**corpus_search workflow:**
1. Validates corpus exists and embedding model matches.
2. Embeds the query string with the same model (locally after model assets are available).
3. Runs sqlite-vec `MATCH` query joined with `corpus_chunks` for metadata filtering.
4. Returns chunks with video IDs, timestamps, text, and similarity scores (distance → 1.0 − distance).

**Offline/online boundary:** Embedding inference and vector search run locally after model assets are available; initial model acquisition may require network (no external embedding service required). However, `corpus_add` fetches the video transcript over the network (via youtube-transcript-api) before chunking and embedding. The corpus workflow is not fully offline.

**Safety:** `corpus_id` is validated against `^[A-Za-z0-9_-]{1,128}$` before any SQL interpolation. Per-corpus vector table names are derived from the validated corpus_id.

## Product Layers (Architecture)

### Core Self-Hosted MCP — This Repository
- All 16 tools, all transports, cache/corpus logic.
- No external database/vector/embedding service required. Requires network connectivity to YouTube upstreams.
- Users bring their own `YOUTUBE_API_KEY` for the 3 API-keyed tools.
- MIT-licensed; installable from source. No SaaS, accounts, billing, or managed hosting.

### Distribution
- GitHub, PyPI and GHCR distribute the same self-hosted package.
- Users own deployment, credentials, quotas, storage, retention and availability.
- No public hosted demo, shared quota, forced corpus expiry, OAuth service, account layer, or managed infrastructure is part of the architecture.

## Release-Candidate Readiness

1. One catalog defines all 16 registered tool schemas and HELP metadata; a separate dispatcher is contract-tested against the same 16-name set.
2. Package documentation and the synchronous installed `tube_bridge.cli:main` entrypoint are verified from an isolated wheel.
3. The core freeze remains 125 tests; the active tree adds five self-hosted-only retirement tests, two private-endpoint help tests, and five v1.0.3 release-artifact tests for 137 deterministic tests. `test_tools.py` remains optional live smoke.
4. Wheel+sdist/twine, exact dependency lock, Docker MCP handshake, SQLite lifecycle contracts and final hosted Python 3.12/3.13 CI for the ADR-003 transition pass.
5. GitHub Release, PyPI and public GHCR publication are complete; no hosted-demo gate exists.

ADR-003 is the active product authority. ADR-001's hosted-demo clauses and ADR-002 are superseded but remain preserved as historical documents and Git/Station evidence.

## Design Decisions

1. **Subprocess, not Python import** — yt-dlp is called via `subprocess.run()` with explicit timeout, captured stdout/stderr, 2-retry with exponential backoff, and process isolation. This provides clean timeout control and predictable failure modes.

2. **Flat playlist for search/channels** — `--flat-playlist` flag means yt-dlp returns metadata without fetching full video pages. Full metadata is available via `youtube_get_video_info` on individual videos.

3. **Lazy transcript API** — `YouTubeTranscriptApi` is instantiated once and reused via a module-level singleton.

4. **Manual > ASR** — Transcript priority: manual subtitles first, auto-generated second.

5. **Modular package** — Clean module boundaries: server wiring/catalog, packaged CLI, tool implementations, transport, cache, corpus, and YouTube subpackage. Root `server.py` is only a compatibility wrapper.

6. **Dual database files** — `cache.db` and `corpus.db` are separate SQLite databases with distinct schemas and lifecycles, sharing the same configurable directory.

7. **No Google SDK dependency** — Data API v3 calls use Python stdlib `urllib` exclusively. No `google-api-python-client` package is required or referenced.
