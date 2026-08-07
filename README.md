# tube-bridge

**YouTube MCP server for AI agents — search, discovery, transcripts, comments.**

10 tools. Zero API keys for core features. Optional Data API v3 upgrade.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.28.1-green.svg)](https://modelcontextprotocol.io)
[![Railway](https://img.shields.io/badge/deploy-Railway-purple.svg)](https://railway.com)

## Quick Start

```bash
# 1. Install
pip install mcp==1.28.1 yt-dlp youtube-transcript-api starlette uvicorn sqlite-vec fastembed

# 2. Run (no API key needed for 12 of 16 tools)
python3 server.py              # stdio mode (local MCP clients)
python3 server.py --http       # HTTP/SSE mode (remote, port 8080)

# 3. Connect
# Claude Desktop / Cursor → add as MCP server:
#   stdio: python3 /path/to/tube-bridge/server.py
#   HTTP:  http://localhost:8080/mcp
```

**16 tools: 13 without API key, 3 with optional key. 5 corpus tools use local embeddings (zero network).**

## API Key (YouTube Data API v3)

**Get your own key** — the bundled key is for development only. If you deploy publicly, use your own to avoid burning shared quota:

```bash
# 1. Go to https://console.cloud.google.com/apis/library/youtube.googleapis.com
# 2. Create project → Enable YouTube Data API v3 → Credentials → API Key
# 3. Set the key:
export YOUTUBE_API_KEY="your-key-here"
```

With a key, 3 extra tools unlock: `youtube_get_comments`, `youtube_search_channels`, `youtube_get_channel_info`. Search and video_info also upgrade to higher-quality API v3 results.

## Proxy (Recommended for Railway/cloud deployments)

YouTube blocks datacenter IPs for transcript fetching. Fix: residential proxy.

```bash
# Get a proxy from IPRoyal ($7/GB pay-as-you-go, never expires)
# → https://iproyal.com — Residential Proxies → Pay As You Go
# You'll get a URL like: http://user:pass@geo.iproyal.com:12321

export TUBE_BRIDGE_PROXY="http://user:pass@geo.iproyal.com:12321"
```

Without a proxy, transcripts may fail on Railway/AWS/GCP with "Sign in to confirm you're not a bot". All other tools (search, etc.) are unaffected — they use Data API v3 which works fine from datacenter IPs.

## Full Deployment (Railway)

```bash
# 1. Clone
git clone https://github.com/TheWhiteWater/tube-bridge
cd tube-bridge

# 2. Deploy
railway init --name tube-bridge
railway up --service tube-bridge --detach

# 3. Set env vars in Railway dashboard → Variables:
#    YOUTUBE_API_KEY=your-key          (optional, for comments/channels)
#    TUBE_BRIDGE_PROXY=http://...      (recommended, for transcripts)
#    TUBE_BRIDGE_EMBEDDING_MODEL=...   (optional, default: BAAI/bge-small-en-v1.5)

# 4. Connect: https://your-app.up.railway.app/mcp
```

> ⚠️ **Important:** If you fork this repo, set your own `YOUTUBE_API_KEY` and `TUBE_BRIDGE_PROXY`. The bundled credentials have shared quotas — don't rely on them for production use.

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
**13 of 16 tools work with zero API keys.** 3 tools unlock with a YouTube Data API key. All 5 corpus tools use local embeddings (no key, no network).

## API Key (YouTube Data API v3)

For comments, channel search, channel info, and higher-quality search results, get your own YouTube Data API key:

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
