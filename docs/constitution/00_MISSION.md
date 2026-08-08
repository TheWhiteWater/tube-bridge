# 00 — Mission & Vision

## Vision

**Every AI agent should be able to interact with YouTube as naturally as a human — search, discover, and extract knowledge — without API keys, registration, or vendor lock-in.**

tube-bridge is the open bridge between AI agents and YouTube. It converts YouTube from a walled video platform into a queryable knowledge base accessible through the Model Context Protocol (MCP).

## Mission

Build the **most complete, zero-friction YouTube MCP server** — covering search, discovery, metadata, transcripts, playlists, channels, comments, and semantic corpus search — with zero registration requirements and zero API keys for core functionality.

## Principles

1. **Zero-friction first** — Works out of the box. 13 of 16 tools require no API key, no OAuth, no registration. Dependencies can be installed with pip; PyPI package publication is not yet verified.
2. **Complete coverage** — Not just transcripts. Search, channels, playlists, trending, comments, metadata, and semantic corpus search. A broad read-only YouTube surface for agents; uploads, account management and bulk scraping remain non-goals.
3. **Agent-native design** — Every tool returns structured JSON optimized for LLM consumption. Descriptions, schemas, and error messages are written for AI agents, not humans.
4. **Graceful degradation** — yt-dlp as fallback (no keys needed for search/video_info/trending), YouTube Data API v3 as optional upgrade. Quota-exceeded falls through to the no-key path without breaking.
5. **Modular open core** — A `tube_bridge/` Python package with clean module boundaries: server wiring, packaged CLI, tool implementations, transport layer, persistent cache, and corpus engine. `tube_bridge.cli:main` is the canonical installed launcher; root `server.py` is a compatibility wrapper.
6. **Station-native** — First-class BrainOps lifecycle: TME, ADR, gates, vision-aligned development.

## Product Boundaries

**Core (MIT licensed):**
- All 16 MCP tools, all transports (stdio, Streamable HTTP, SSE), all cache/corpus logic.
- Zero-registration workflows: 13 tools usable without any API key.
- Users bring their own `YOUTUBE_API_KEY` for the 3 API-dependent tools (comments, channel search, channel info).

**Hosted demo endpoint (Railway, disposable):**
- Try-before-install only: `tube-bridge-production.up.railway.app`.
- Isolated Google Cloud project with server-side upstream configuration, separate from Operator personal/development configuration.
- Exactly 5 YouTube Data API v3 operations per client/IP.
- Corpora auto-delete after 10 minutes. No persistent volume, backups, accounts, or durable transcript/corpus hosting.
- Not advertised as a public service.

**Grabbit (separate MCP):**
- Completely separate MCP. No connector, dependency, shared service, code integration, or implementation roadmap exists between tube-bridge and Grabbit.
- An example agent usage sequence may show the agent using tube-bridge to find videos and then separately using Grabbit to save links — that is the full extent of any documented relationship.

## Tool Baseline

16 MCP tools registered in `tube_bridge/server.py` `list_tools()` (source: lines 67–248):

- **10 YouTube interaction tools:** `youtube_search`, `youtube_search_channels`, `youtube_get_channel_info`, `youtube_get_video_info`, `youtube_get_trending`, `youtube_get_channel_videos`, `youtube_get_playlist`, `youtube_get_transcript`, `youtube_get_available_languages`, `youtube_get_comments`.
- **5 corpus tools:** `corpus_create`, `corpus_add`, `corpus_search`, `corpus_list`, `corpus_delete`.
- **1 help tool:** `tube_bridge_help`.

Total: 10 + 5 + 1 = 16.

- **13 tools callable without any API key:** `youtube_search` (yt-dlp fallback), `youtube_get_video_info`, `youtube_get_trending`, `youtube_get_channel_videos`, `youtube_get_playlist`, `youtube_get_transcript`, `youtube_get_available_languages`, `corpus_create`, `corpus_add`, `corpus_search`, `corpus_list`, `corpus_delete`, `tube_bridge_help`.
- **3 tools require YouTube Data API v3 key:** `youtube_get_comments`, `youtube_search_channels`, `youtube_get_channel_info`.

Search, video_info, and trending upgrade to higher-quality Data API v3 results when the key is present; they fall back to yt-dlp when quota is exhausted or the key is absent.

## Success Criteria

- An AI agent can search YouTube, get a transcript, and analyze a video in under 3 tool calls.
- 16 tools available via stdio, Streamable HTTP, and SSE MCP transports.
- 13 tools work with zero API keys; 3 unlock with an optional Data API v3 key.
- Semantic corpus search over transcripts using local embeddings (fastembed + sqlite-vec), with embedding inference done locally after model assets are available; initial model acquisition/cache may require network. `corpus_add` fetches transcripts over the network.
- Open-core library published on GitHub under MIT license; hosted demo endpoint deployed for development/testing (Railway).
- Publication readiness gating: full-publication readiness is not yet accepted; tracked in `docs/planning/PUBLICATION_READINESS.md`.

## Anti-Goals (what success is NOT)

- NOT a YouTube downloader.
- NOT a video player or UI.
- NOT a replacement for YouTube Data API — a complementary, agent-first alternative.
- NOT a scraping service at scale — designed for agent use, not bulk harvesting.
- NOT a public production service — the hosted demo exists for development and limited testing until readiness gates are passed.
