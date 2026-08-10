# tube-bridge

**YouTube MCP server for AI agents — search, discovery, transcripts, comments, semantic corpus.**

17 tools. 14 without API key. 3 with optional YouTube Data API v3 key.

`v1.1.0` adds bounded timestamp-to-JPEG extraction, deterministic default-language subtitle selection, and a portable Agent Plugin preview for evidence-oriented research.

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-1.28.1-green.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/tube-bridge.svg)](https://pypi.org/project/tube-bridge/)
[![Container](https://img.shields.io/badge/GHCR-tube--bridge-blue.svg)](https://github.com/TheWhiteWater/tube-bridge/pkgs/container/tube-bridge)

## Quick Start

```bash
# 1. Install the package
pip install tube-bridge

# 2. Run (no API key needed for 14 of 17 tools)
tube-bridge                    # stdio mode (local MCP clients)
tube-bridge --http             # HTTP mode (remote, port 8080)

# 3. Or run the published container
docker run --rm -p 8080:8080 ghcr.io/thewhitewater/tube-bridge:latest

# MCP endpoints: stdio via `tube-bridge`, HTTP at http://localhost:8080/mcp
```

**17 tools: 14 callable without any setup. 3 unlock with a Data API v3 key. 5 corpus tools use local embeddings.**

## Agent Plugin Preview

The v1.1.0 GitHub release is configured to include `tube-bridge-agent-plugin-1.1.0.zip`, a portable Agent Plugins v1 bundle with:

- one discoverable `tube-bridge-research` skill;
- the 17-tool local stdio MCP configuration;
- evidence, adversary-review, and source-lineage methodology;
- worked examples and reusable research templates;
- the frozen Corpus v2 storage contract, clearly separated from the current v1 corpus runtime.

Agent Plugins v1 does not standardize dependency installation. Install Python 3.12+, ffmpeg, and the package dependencies into the `python3` environment used by your plugin host before launching the MCP. The plugin bundle contains no credentials; API keys, proxy settings, cache location, and retention remain operator-controlled.

The plugin is a preview because dependency bootstrap and client-specific loading remain host responsibilities. The skill content and MCP contract are covered by the deterministic test suite.

## Tools (17)

| Tool | API Key | Description |
|------|:-------:|-------------|
| `youtube_search` | ❌→✅ | Search videos. Data API v3 primary when key set, yt-dlp fallback. Rich filters: date, channel, duration, order |
| `youtube_get_video_info` | ❌→✅ | Full metadata: title, views, channel, tags, description. Dual-source, cached |
| `youtube_get_trending` | ❌→✅ | Trending videos. API v3 primary, yt-dlp fallback |
| `youtube_get_channel_videos` | ❌ | Recent uploads from any channel (@handle or URL) |
| `youtube_get_playlist` | ❌ | All videos in a playlist |
| `youtube_get_transcript` | ❌ | Transcript/subtitles. Original/default language; manual > ASR within that language |
| `youtube_get_frame` | ❌ | One ephemeral JPEG near an integer-millisecond timestamp; best-effort frame boundary, MCP ImageContent, no persistence |
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

`youtube_get_frame` requires an `ffmpeg` executable on `PATH`; the published container installs it. Source/PyPI operators install ffmpeg with their OS package manager.

### Transport Endpoints

- **`/mcp`** — Streamable HTTP (recommended for remote deployments)
- **`/sse`** — SSE (legacy; deprecated)
- **`/health`** — Health check (always open)
- **stdio** — Direct child process for local MCP clients

### Optional Auth

Set `TUBE_BRIDGE_AUTH_KEY` to protect `/mcp`, `/sse`, and `/messages`. Header-capable clients send `Authorization: Bearer <key>`. `/health` remains public. Without the variable, self-hosted HTTP is open.

Client config:
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
├── cli.py             # Runtime selection: stdio or HTTP
├── transport.py       # Streamable HTTP + SSE routes, optional Bearer auth, health
├── cache.py           # Persistent SQLite cache (cache.db) for transcripts + video metadata
├── corpus.py          # Semantic search (corpus.db, sqlite-vec + fastembed)
└── youtube/
    ├── client.py      # yt-dlp subprocess client (retry + backoff + proxy)
    ├── api.py         # YouTube Data API v3 client (stdlib urllib, no third-party Google SDK)
    ├── transcript.py  # youtube-transcript-api wrapper (default-language selection, proxy)
    ├── frame.py       # bounded timestamp→JPEG extraction (yt-dlp + ffmpeg)
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

tube-bridge is an MIT self-hosted individual MCP — not a hosted demo, SaaS, or managed transcript service. Each user installs and operates their own instance, credentials, storage, quotas, and retention.

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
- **MIT self-hosted library** — 17 MCP tools, all transports, cache/corpus logic.
- **v1.1.0 release line** — the authorized candidate targets GitHub Release, PyPI, and public GHCR. Publication state and downloaded-artifact evidence are recorded in `docs/planning/PUBLICATION_READINESS.md` rather than inferred from source version strings.
- **No hosted demo** — the project does not provide public hosted access, tester invites, accounts, managed storage, or an SLA. Install it yourself to evaluate it.

### Full Publication Scope
The self-hosted runtime's public distribution surfaces are GitHub Release, PyPI, and GHCR. The Agent Plugin preview is packaged as a GitHub Release asset and source-tree bundle; it is not an additional hosted service.

### What tube-bridge Is NOT
- Not a SaaS or managed transcript-hosting product.
- No commercial extension, product gateway, billing, entitlement, or managed higher-quota tier.
- [Grabbit MCP](https://grabbitapp.com) is a completely separate companion MCP ([live endpoint](https://mcp.grabbitapp.com/api/mcp)). There is no connector, dependency, shared service, bundled workflow, or code integration: an agent may use tube-bridge to find videos and independently use Grabbit to save links.
- Browser extension is outside this project's release gate and must not be architected here.

### Decision Sources
- `PROJECT_VISION.md` — product boundaries, tool baseline, open-core scope.
- `docs/planning/PUBLICATION_READINESS.md` — readiness checklist (P0/P1/P2 items, no-go gates).
- `docs/adr/003-self-hosted-only-private-operator-railway.md` — active self-hosted-only product decision.
- ADR-001's hosted-demo clauses and ADR-002 are historical and superseded.

## Testing

```bash
python3 test_tools.py
```

This remains an optional live smoke against YouTube. Formal acceptance uses `python3 -m pytest tests -q`; the source-tree suite contains 188 deterministic tests, preserving the original release/privacy gates and adding frame, plugin, subtitle-selection, and Corpus v2 contracts. Hosted GitHub Actions CI runs on Python 3.12 and 3.13.

## Known Limitations

- **Datacenter IPs (Railway, AWS, etc.):** YouTube may block anonymous requests from cloud IP ranges. `youtube_search` and `youtube_get_video_info` are unaffected with a Data API v3 key. `youtube_get_transcript` may fail with bot detection — set `TUBE_BRIDGE_PROXY` to a residential proxy to work around this.
- **yt-dlp anonymous search:** degraded by YouTube in recent months. Prefer Data API v3 when available.

## License

MIT — see LICENSE file.
