# tube-bridge

<!-- mcp-name: io.github.TheWhiteWater/tube-bridge -->

**Self-hosted YouTube MCP server for AI agents.**

Search YouTube, inspect videos and channels, fetch transcripts and comments, extract timestamped frames, and build local semantic-search corpora.

[![CI](https://github.com/TheWhiteWater/tube-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/TheWhiteWater/tube-bridge/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tube-bridge.svg)](https://pypi.org/project/tube-bridge/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Quick start

### PyPI

```bash
pip install tube-bridge

tube-bridge          # stdio transport
tube-bridge --http   # HTTP transport on port 8080
```

### Docker

```bash
docker run --rm -p 8080:8080 ghcr.io/thewhitewater/tube-bridge:latest
```

The HTTP MCP endpoint is `http://localhost:8080/mcp`.

### Official MCP Registry

Registry name: `io.github.TheWhiteWater/tube-bridge`

Registry-aware clients can install the PyPI distribution with `uvx` and launch the stdio server without a hosted intermediary.

## MCP client configuration

### Local stdio

```json
{
  "mcpServers": {
    "tube-bridge": {
      "command": "tube-bridge"
    }
  }
}
```

If the executable is not on your client's `PATH`, use the full path returned by `which tube-bridge`.

### Streamable HTTP

```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "http",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

### Protected HTTP

Set a server-side Bearer key:

```bash
export TUBE_BRIDGE_AUTH_KEY="choose-a-long-random-value"
tube-bridge --http
```

Then configure the client header:

```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "http",
      "url": "https://your-host.example/mcp",
      "headers": {
        "Authorization": "Bearer <your-key>"
      }
    }
  }
}
```

`/health` remains public. `/mcp`, `/sse`, and `/messages` require the Bearer key when `TUBE_BRIDGE_AUTH_KEY` is set.

## Tools

| Tool | YouTube API key | Description |
|---|:---:|---|
| `youtube_search` | Optional | Search videos; Data API v3 with yt-dlp fallback |
| `youtube_get_video_info` | Optional | Video metadata, description, tags, views, and channel |
| `youtube_get_trending` | Optional | Trending videos |
| `youtube_get_channel_videos` | No | Recent channel uploads |
| `youtube_get_playlist` | No | Playlist videos |
| `youtube_get_transcript` | No | Transcript with optional timestamps |
| `youtube_get_frame` | No | One ephemeral JPEG near a timestamp |
| `youtube_get_available_languages` | No | Available manual and generated subtitle tracks |
| `youtube_get_comments` | Required | Top-level comments |
| `youtube_search_channels` | Required | Search channels with subscriber filters |
| `youtube_get_channel_info` | Required | Channel statistics and metadata |
| `corpus_create` | No | Create a local semantic-search corpus |
| `corpus_add` | No | Fetch, chunk, and embed a transcript |
| `corpus_search` | No | Search a corpus semantically |
| `corpus_list` | No | List local corpora |
| `corpus_delete` | No | Delete a corpus and its vectors |
| `tube_bridge_help` | No | Runtime tool and setup documentation |

Fourteen tools can run without a YouTube Data API key. Comments, channel search, and channel details require one.

## Optional YouTube Data API key

Create a YouTube Data API v3 key in Google Cloud Console, then set:

```bash
export YOUTUBE_API_KEY="your-key"
```

With a key, search, video information, and trending use Data API v3 first. Supported operations fall back to yt-dlp when the key is absent or quota is exhausted.

## Local semantic corpus

Corpus data and embeddings stay on the machine running tube-bridge.

```text
corpus_create("ai-agents", "AI Agents Research")
corpus_add("ai-agents", "https://www.youtube.com/watch?v=VIDEO_ID")
corpus_search("ai-agents", "memory systems")
corpus_list()
corpus_delete("ai-agents")
```

- storage: SQLite with sqlite-vec;
- embeddings: BGE-small-en-v1.5 through fastembed;
- chunking: 80-second windows with 20-second overlap;
- results: similarity score, source time span, video title, and timestamp URL;
- default data directory: `~/.tube_bridge`.

Set `TUBE_BRIDGE_CACHE` to use another directory:

```bash
export TUBE_BRIDGE_CACHE="/path/to/tube-bridge-data"
```

The embedding model may be downloaded on first use.

## Frame extraction

`youtube_get_frame` needs `ffmpeg` on `PATH`. The Docker image includes it; source and PyPI users install it with their OS package manager.

Each call downloads only a short temporary section, returns one bounded JPEG, and removes the temporary media before returning.

## Proxy support

If YouTube blocks requests from your network, configure an HTTP(S) proxy:

```bash
export TUBE_BRIDGE_PROXY="http://proxy.example:8080"
```

The value is used by yt-dlp and transcript requests. Keep proxy credentials in environment variables, never in MCP configuration committed to source control.

## Transports

- **stdio** — recommended for local MCP clients;
- **`/mcp`** — Streamable HTTP;
- **`/sse`** and **`/messages`** — legacy SSE compatibility;
- **`/health`** — process health and tool count.

## Agent Plugin preview

GitHub Releases also include `tube-bridge-agent-plugin-<version>.zip`. It bundles:

- the local stdio MCP configuration;
- the `tube-bridge-research` skill;
- research templates and source-evaluation guidance.

The plugin format does not install system or Python dependencies. Install Python 3.12+, ffmpeg, and tube-bridge dependencies in the environment used by your plugin host.

## Development

```bash
git clone https://github.com/TheWhiteWater/tube-bridge.git
cd tube-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-release.txt
pip install --no-deps -e .
pip install pytest pytest-asyncio pytest-mock build twine
python -m pytest tests -q
```

Optional live smoke test:

```bash
python test_tools.py
```

The deterministic test suite does not call YouTube. The live smoke test does.

## Known limitations

- YouTube can restrict anonymous yt-dlp and transcript requests, especially from cloud-hosting IP ranges.
- A Data API key improves search and metadata reliability but does not replace transcript access.
- Initial local embedding-model setup may require network access and additional disk space.
- This project is self-hosted software; it does not provide accounts, hosted storage, or a managed endpoint.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports should follow [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
