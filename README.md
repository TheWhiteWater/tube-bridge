# tube-bridge

**YouTube MCP server for AI agents — search, discovery, transcripts, comments.**

10 tools. Zero API keys for core features. Optional Data API v3 upgrade.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.28.1-green.svg)](https://modelcontextprotocol.io)
[![Railway](https://img.shields.io/badge/deploy-Railway-purple.svg)](https://railway.com)

## Quick Start

```bash
pip install mcp==1.28.1 yt-dlp youtube-transcript-api starlette uvicorn
python3 server.py              # stdio mode (for local MCP clients)
python3 server.py --http       # HTTP/SSE mode (for remote MCP clients)
```

## Tools (16)

| Tool | API Key | Description |
|------|:-------:|-------------|
| `youtube_search` | ❌→✅ | Search videos. Data API v3 when key present, yt-dlp fallback. Rich filters: date, channel, duration |
| `youtube_get_video_info` | ❌→✅ | Full metadata: title, views, channel, tags, description |
| `youtube_get_trending` | ❌→✅ | Trending videos. API v3 primary, yt-dlp fallback |
| `youtube_get_channel_videos` | ❌ | Recent uploads from any channel (@handle or URL) |
| `youtube_get_playlist` | ❌ | All videos in a playlist |
| `youtube_get_transcript` | ❌ | Transcript/subtitles. Plain text or [MM:SS] timestamps. Manual > ASR |
| `youtube_get_available_languages` | ❌ | Subtitle languages with manual/auto-generated flags |
| `youtube_get_comments` | ✅ | Top-level comments with likes and reply counts |
| `youtube_search_channels` | ✅ | Channel search with subscriber counts and filters |
| `youtube_get_channel_info` | ✅ | Detailed channel stats (subs, views, country, keywords) |
| `tube_bridge_help` | ❌ | Server documentation accessible via MCP |
| `corpus_create` | ❌ | Create a named corpus for semantic transcript search |
| `corpus_add` | ❌ | Add video transcript to a corpus (auto-chunks + embeds) |
| `corpus_search` | ❌ | Semantic search within a corpus (scores + timestamps) |
| `corpus_list` | ❌ | List all corpora with counts |
| `corpus_delete` | ❌ | Delete a corpus permanently |

**7 YouTube tools work with zero configuration.** 3 upgrade with an API key. 5 corpus tools use local embeddings (no key needed).

## Architecture

```
tube_bridge/
├── server.py          # MCP wiring: tool registration + dispatch
├── tools.py           # Tool implementations (async, cached, retry)
├── transport.py       # HTTP/SSE/stdio transport
├── cache.py           # SQLite cache for transcripts + video metadata
├── corpus.py          # Semantic search (sqlite-vec + fastembed)
└── youtube/
    ├── client.py      # yt-dlp subprocess client (retry + backoff)
    ├── api.py         # YouTube Data API v3 client
    ├── transcript.py  # youtube-transcript-api wrapper (manual > ASR)
    └── models.py      # VideoInfo dataclass
```

- **Dual-source:** Data API v3 → yt-dlp fallback for search, trending, video_info
- **Cache:** SQLite (survives restarts) + lru_cache hot layer for transcripts (64) and metadata (32)
- **Semantic search:** sqlite-vec + fastembed, named corpora, zero API keys
- **Retry:** 2 retries with exponential backoff for yt-dlp subprocess
- **Proxy:** IPRoyal residential proxy via TUBE_BRIDGE_PROXY env var
- **Graceful:** quota exceeded → falls through to yt-dlp; stderr in `_warning` field

## Bridge Corpus

Semantic search over YouTube transcripts using local embeddings. Useful for research workflows — build a corpus of videos on a topic and search across them.

```python
corpus_create("ai-agents", "AI Agents Research")     # Named corpus
corpus_add("ai-agents", "dQw4w9WgXcQ")               # Auto-chunks + embeds
corpus_search("ai-agents", "memory systems")          # Semantic search with scores
corpus_list()                                          # List all corpora
corpus_delete("ai-agents")                             # Archive/clean
```

- **Chunking:** by transcript segments, 60-90s windows with overlap
- **Embeddings:** fastembed (BGE-small-en-v1.5, 384-dim, offline, zero API keys)
- **Storage:** sqlite-vec — same file as cache, no separate server
- **Isolation:** named corpora, embedding_model per corpus, corpus_id filter before ANN

## API Key (Optional)

Core features work without any key. For API-powered features, set the environment variable:

```bash
export YOUTUBE_API_KEY="your-key-here"
```

> ⚠️ **Important:** The bundled API key is for development/testing only. If you clone this repo, **get your own key** from [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) to avoid burning through our quota. The key has 10,000 units/day — enough for ~100 searches.

## MCP Client Config

**Claude Desktop / Cursor / any MCP client — stdio:**
```json
{
  "mcpServers": {
    "tube-bridge": {
      "command": "python3",
      "args": ["/path/to/tube-bridge/server.py"]
    }
  }
}
```

**Remote (SSE):**
```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "sse",
      "url": "https://tube-bridge-production.up.railway.app/sse"
    }
  }
}
```

**Remote (Streamable HTTP, recommended):**
```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "http",
      "url": "https://tube-bridge-production.up.railway.app/mcp"
    }
  }
}
```

## Deployment

```bash
# Railway
railway up --service tube-bridge --detach

# Docker
docker build -t tube-bridge .
docker run -p 8080:8080 -e YOUTUBE_API_KEY=... tube-bridge
```

## vs Competitors

| Feature | tube-bridge | ZubeidHendricks | jkawamoto |
|---------|:---:|:---:|:---:|
| **Tools** | **10** | 10 | 4 |
| **Works without API key** | **7** | 0 | 4 |
| Dual-source (API + fallback) | ✅ | ❌ | ❌ |
| Transcript with timestamps | ✅ | ❌ | ✅ |
| Manual > ASR priority | ✅ | ❌ | ❌ |
| Channel search + subs filter | ✅ | ✅ | ❌ |
| Trending | ✅ | ❌ | ❌ |
| Cache + retry + stderr | ✅ | ❌ | ❌ |
| Streamable HTTP + SSE | ✅ | ❌ | SSE |
| Python (single package) | ✅ | ❌ (npm) | ✅ |

## Known Limitations

- **Datacenter IPs (Railway, AWS, etc.):** YouTube may block anonymous requests from cloud IP ranges. When deployed on Railway:
  - `youtube_search` + `youtube_get_video_info` → unaffected (use Data API v3 with key)
  - `youtube_get_transcript` → may fail with bot detection. **Fix:** set `TUBE_BRIDGE_PROXY` to a residential proxy (IPRoyal, $7/GB pay-as-you-go).
- **Corpus DB is ephemeral on Railway** (no persistent volume). Use Railway volume mount for production corpus storage.
- **yt-dlp anonymous search:** degraded by YouTube in recent months. Always prefer Data API v3 when available.

MIT
