# AGENTS.md — tube-bridge

**Project:** YouTube MCP server for AI agents — 16 tools
**Stack:** Python 3.12+, MCP 1.28.1, yt-dlp, youtube-transcript-api, sqlite-vec, fastembed
**Transport:** stdio + Streamable HTTP (/mcp) + SSE (/sse)
**License:** MIT

## Quick Start

```bash
pip install mcp==1.28.1 yt-dlp youtube-transcript-api starlette uvicorn sqlite-vec fastembed
python3 server.py              # stdio
python3 server.py --http       # HTTP on :8080
python3 test_tools.py          # smoke test
```

## Architecture

```
tube_bridge/
├── server.py          # MCP wiring: tool registration + dispatch
├── tools.py           # All tool implementations (async, cached)
├── transport.py       # Streamable HTTP (/mcp) + SSE (/sse) + stdio
├── cache.py           # Persistent SQLite cache for transcripts + metadata
├── corpus.py          # Semantic search: sqlite-vec + fastembed
└── youtube/
    ├── client.py      # yt-dlp subprocess (retry + backoff + proxy)
    ├── api.py         # YouTube Data API v3 (optional)
    ├── transcript.py  # youtube-transcript-api (manual > ASR, proxy)
    └── models.py      # VideoInfo dataclass
```

## Conventions

- **Dual-source:** API v3 primary, yt-dlp fallback for search, video_info, trending
- **Cached:** SQLite (persistent) + lru_cache hot layer
- **Retry:** 2 retries with exponential backoff for yt-dlp subprocess
- **Proxy:** TUBE_BRIDGE_PROXY env var → both yt-dlp and transcript API
- **Embeddings:** fastembed (BGE-small-en-v1.5), offline, zero keys
- **Single package:** one `tube_bridge/` directory, zero external services

## Key Docs

| Document | Path |
|----------|------|
| README (public) | README.md |
| Project Vision | PROJECT_VISION.md |
| Architecture | docs/constitution/02_ARCHITECTURE.md |
| Data Model | docs/constitution/03_DATA_MODEL.md |
| Non-Goals | docs/constitution/05_NON_GOALS.md |
| ADR Rules | docs/constitution/06_ADR_RULES.md |
| Open Questions | docs/planning/OPEN_QUESTIONS.md |
