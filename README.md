# tube-bridge

**YouTube MCP server for AI agents — search, discovery, transcripts, comments, semantic corpus.**

16 tools. 13 without API key. 3 with optional YouTube Data API v3 key.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.28.1-green.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/tube-bridge.svg)](https://pypi.org/project/tube-bridge/)
[![Container](https://img.shields.io/badge/GHCR-tube--bridge-blue.svg)](https://github.com/TheWhiteWater/tube-bridge/pkgs/container/tube-bridge)

## Quick Start

```bash
# 1. Install the published package
pip install tube-bridge

# 2. Run (no API key needed for 13 of 16 tools)
tube-bridge                    # stdio mode (local MCP clients)
tube-bridge --http             # HTTP mode (remote, port 8080)

# 3. Or run the published container
docker run --rm -p 8080:8080 ghcr.io/thewhitewater/tube-bridge:latest

# MCP endpoints: stdio via `tube-bridge`, HTTP at http://localhost:8080/mcp
```

**16 tools: 13 callable without any setup. 3 unlock with a Data API v3 key. 5 corpus tools use local embeddings.**

## Tools (16)

| Tool | API Key | Description |
|------|:-------:|-------------|
| `youtube_search` | ❌→✅ | Search videos. Data API v3 primary when key set, yt-dlp fallback. Rich filters: date, channel, duration, order |
| `youtube_get_video_info` | ❌→✅ | Full metadata: title, views, channel, tags, description. Dual-source, cached |
| `youtube_get_trending` | ❌→✅ | Trending videos. API v3 primary, yt-dlp fallback |
| `youtube_get_channel_videos` | ❌ | Recent uploads from any channel (@handle or URL) |
| `youtube_get_playlist` | ❌ | All videos in a playlist |
| `youtube_get_transcript` | ❌ | Transcript/subtitles. Plain text or [MM:SS] timestamps. Manual > ASR |
| `youtube_get_available_languages` | ❌ | Subtitle languages with manual/auto-generated flags |
| `youtube_get_comments` | ✅ | Top-level comments with likes and reply counts |
| `youtube_search_channels` | ✅ | Channel search with subscriber counts and filters |
| `youtube_get_channel_info` | ✅ | Detailed channel stats: subscribers, views, country, keywords |
| `tube_bridge_help` | ❌ | Server documentation accessible via MCP |
| `corpus_create` | ❌ | Create a named corpus for semantic transcript search |
| `corpus_add` | ❌ | Add video transcript to a corpus. Auto-fetches (network), chunks, embeds locally |
| `corpus_search` | ❌ | Semantic search within a corpus. Returns chunks with scores, timestamps, video IDs |
| `corpus_list` | ❌ | List all corpora with chunk and video counts |
| `corpus_delete` | ❌ | Delete a corpus and all its chunks/vectors permanently |

**Key:** ❌ = no key needed; ✅ = key required; ❌→✅ = works without key, upgrades with key.

### Transport Endpoints

- **`/mcp`** — Streamable HTTP (recommended for remote deployments)
- **`/sse`** — SSE (legacy; deprecated)
- **`/health`** — Health check (always open)
- **stdio** — Direct child process for local MCP clients

### Optional Auth

Set `TUBE_BRIDGE_AUTH_KEY` to enable Bearer-token protection on all remote routes except `/health` (/mcp, /sse, /messages). The `/health` endpoint remains open. If not set, open access (for local dev).

MCP client config with auth:
```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "http",
      "url": "https://your-app.example.com/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-key"
      }
    }
  }
}
```

## YouTube Data API v3 (Optional)

For comments, channel search, channel info, and higher-quality search results, obtain your own YouTube Data API key from Google Cloud Console and set it as an environment variable:

```bash
export YOUTUBE_API_KEY="your-key-here"
```

3 tools unlock with a key. Search and video_info also upgrade to higher-quality Data API v3 results. With the key present, yt-dlp is used as a fallback when quota is exhausted.

## Bridge Corpus — Semantic Search

Semantic search over YouTube transcripts using local embeddings. Useful for research workflows — build a corpus of videos on a topic and search across them.

```
corpus_create("ai-agents", "AI Agents Research")     # Named corpus
corpus_add("ai-agents", "dQw4w9WgXcQ")               # Auto-chunks + embeds (transcript fetched over network)
corpus_search("ai-agents", "memory systems")          # Semantic search with scores
corpus_list()                                          # List all corpora
corpus_delete("ai-agents")                             # Delete permanently
```

- **Chunking:** by transcript segments, 80-second windows with 20-second overlap
- **Embeddings:** fastembed (BGE-small-en-v1.5, 384-dim); local inference after model assets are available; initial model acquisition may require network; no embedding API setup
- **Storage:** `corpus.db` — separate SQLite file from `cache.db`, same directory (`~/.tube_bridge`)

## Architecture

```
tube_bridge/
├── server.py          # MCP wiring: tool registration + dispatch
├── tools.py           # All tool implementations (async, cached, retry)
├── transport.py       # Streamable HTTP + SSE + stdio transport
├── cache.py           # Persistent SQLite cache (cache.db) for transcripts + video metadata
├── corpus.py          # Semantic search (corpus.db, sqlite-vec + fastembed)
└── youtube/
    ├── client.py      # yt-dlp subprocess client (retry + backoff + proxy)
    ├── api.py         # YouTube Data API v3 client (stdlib urllib, no third-party Google SDK)
    ├── transcript.py  # youtube-transcript-api wrapper (manual > ASR, proxy)
    └── models.py      # VideoInfo dataclass
```

- **Dual-source:** Data API v3 primary → yt-dlp fallback for search, video_info, trending
- **Cache:** SQLite `cache.db` (persistent, survives restarts) + `lru_cache` hot layer
- **Corpus:** SQLite `corpus.db` (separate database) with sqlite-vec vectors
- **Data API client:** Python stdlib `urllib` only; no `google-api-python-client` dependency
- **Retry:** 2 retries with exponential backoff for yt-dlp subprocess
- **Proxy:** `TUBE_BRIDGE_PROXY` env var routes both yt-dlp and transcript API through a proxy
- **Graceful:** quota exceeded → falls through to yt-dlp; stderr captured in `_warning` field

## Self-Hosting

tube-bridge is an MIT self-hosted individual MCP — never a SaaS or managed transcript-hosting product. The Railway deployment below is solely a disposable try-before-install demo.

### Railway (Disposable Demo)

```bash
git clone https://github.com/TheWhiteWater/tube-bridge
cd tube-bridge
railway init --name tube-bridge
railway up --service tube-bridge --detach

# Set in Railway dashboard → Variables:
#   YOUTUBE_API_KEY  (uses isolated demo GCP project, separate from Operator keys)
#   TUBE_BRIDGE_PROXY (recommended for transcripts from datacenter IPs)
#   TUBE_BRIDGE_AUTH_KEY (optional, protects all remote routes except /health)
```

**Demo hardening target (not yet accepted):** exactly 5 Data API v3 operations per observed client IP and deletion of every demo corpus within 10 minutes. WI-00029 still owns implementation and verification; do not rely on these controls on the current endpoint yet.

### Docker

```bash
docker build -t tube-bridge .
docker run -p 8080:8080 -e YOUTUBE_API_KEY=... tube-bridge
```

### Any Host

```bash
pip install mcp==1.28.1 yt-dlp youtube-transcript-api starlette uvicorn sqlite-vec fastembed
python3 server.py --http --port 8080 --host 0.0.0.0
```

## MCP Client Config

**stdio (local):**
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

**Streamable HTTP (recommended for remote):**
```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "http",
      "url": "https://your-app.example.com/mcp"
    }
  }
}
```

**SSE (legacy):**
```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "sse",
      "url": "https://your-app.example.com/sse"
    }
  }
}
```

## Product Boundary

### Current State
- **MIT self-hosted library** — 16 MCP tools, all transports, cache/corpus logic. Available on GitHub.
- **Disposable Railway demo** — `tube-bridge-production.up.railway.app` is a try-before-install demo only. Not a SaaS or managed product.
- **Disposable-demo controls are planned, not yet accepted.** WI-00029 must implement and verify isolated upstream configuration, exactly 5 Data API operations per observed client IP, deletion of each demo corpus within 10 minutes, and no durable hosted storage. Do not treat the current Railway endpoint as evidence that these controls are active.
- **Published self-hosted core.** GitHub Release, PyPI package, and public GHCR image are live. Frozen 125-test, clean install, installed CLI/MCP, Docker handshake, wheel+sdist, twine, and hosted CI checks pass.

### Full Publication Scope
The self-hosted core is fully published through GitHub Release, PyPI, and GHCR. Disposable Railway demo controls and retention guarantees remain a separate acceptance surface.

### What tube-bridge Is NOT
- Not a SaaS or managed transcript-hosting product.
- No commercial extension, product gateway, billing, entitlement, or managed higher-quota tier.
- [Grabbit MCP](https://grabbitapp.com) is a completely separate companion MCP ([live endpoint](https://mcp.grabbitapp.com/api/mcp)). There is no connector, dependency, shared service, bundled workflow, or code integration: an agent may use tube-bridge to find videos and independently use Grabbit to save links.
- Browser extension is outside this project's release gate and must not be architected here.

### Decision Sources
- `PROJECT_VISION.md` — product boundaries, tool baseline, open-core scope.
- `docs/planning/PUBLICATION_READINESS.md` — readiness checklist (P0/P1/P2 items, no-go gates).
- `docs/adr/001-demo-api-quota-and-product-boundary.md` — architecture direction for demo isolation, fixed 5-operation limit, 10-minute corpus TTL, self-hosted boundary, and full-publication scope.

## Testing

```bash
python3 test_tools.py
```

This remains an optional live smoke against YouTube. Formal acceptance uses `python3 -m pytest tests -q`; the frozen suite contains 125 deterministic tests. Hosted GitHub Actions CI passes on Python 3.12 and 3.13.

## Known Limitations

- **Datacenter IPs (Railway, AWS, etc.):** YouTube may block anonymous requests from cloud IP ranges. `youtube_search` and `youtube_get_video_info` are unaffected with a Data API v3 key. `youtube_get_transcript` may fail with bot detection — set `TUBE_BRIDGE_PROXY` to a residential proxy to work around this.
- **Demo retention hardening pending:** the accepted target is deletion within 10 minutes with no persistent volume or backups, but WI-00029 implementation/verification remains open. Self-hosted instances retain corpora under `~/.tube_bridge`.
- **yt-dlp anonymous search:** degraded by YouTube in recent months. Prefer Data API v3 when available.

## License

MIT — see LICENSE file.
