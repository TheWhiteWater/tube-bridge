# tube-bridge

<!-- mcp-name: io.github.TheWhiteWater/tube-bridge -->

**Self-hosted YouTube research for AI agents.**

Search videos and channels, read transcripts and comments, extract timestamped frames, and build private semantic-search corpora — through 17 MCP tools.

[![CI](https://github.com/TheWhiteWater/tube-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/TheWhiteWater/tube-bridge/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tube-bridge.svg)](https://pypi.org/project/tube-bridge/)
[![PyPI downloads](https://img.shields.io/pypi/dw/tube-bridge.svg)](https://pypistats.org/packages/tube-bridge)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Glama](https://glama.ai/mcp/servers/TheWhiteWater/tube-bridge/badges/score.svg)](https://glama.ai/mcp/servers/TheWhiteWater/tube-bridge)

- **14 of 17 tools need no YouTube API key.**
- **Local-first corpus:** transcripts, vectors, and indexes stay on your machine.
- **Useful research output:** titles, similarity scores, canonical video URLs, and timestamp links.
- **One tool for one frame:** return visual evidence near a transcript finding without keeping media files.
- **Self-hosted and MIT:** no account, hosted intermediary, managed storage, or vendor lock-in.

## Connect in a minute

The simplest setup uses [`uvx`](https://docs.astral.sh/uv/guides/tools/), which runs the published PyPI package in an isolated environment:

```bash
uvx tube-bridge
```

Normally your MCP client launches that command for you. Choose your client below.

> [!NOTE]
> tube-bridge requires Python 3.12 or newer. An API key is optional. `ffmpeg` is needed only for `youtube_get_frame`, and the first embedding operation may download the local model.

### Claude Desktop

Open **Settings → Developer → Edit Config** and add:

```json
{
  "mcpServers": {
    "tube-bridge": {
      "command": "uvx",
      "args": ["tube-bridge"]
    }
  }
}
```

Restart Claude Desktop after saving the configuration.

### Claude Code

```bash
claude mcp add --scope user tube-bridge -- uvx tube-bridge
```

### Cursor

Create `.cursor/mcp.json` in your project, or add the server to your user-level MCP configuration:

```json
{
  "mcpServers": {
    "tube-bridge": {
      "command": "uvx",
      "args": ["tube-bridge"]
    }
  }
}
```

### VS Code

Create `.vscode/mcp.json`:

```json
{
  "servers": {
    "tube-bridge": {
      "type": "stdio",
      "command": "uvx",
      "args": ["tube-bridge"]
    }
  }
}
```

### Codex CLI

```bash
codex mcp add tube-bridge -- uvx tube-bridge
```

## Pi package

Pi can load the package-relative adapter and the canonical `tube-bridge-research` skill from the same Git source:

```bash
python3 -m pip install tube-bridge==1.1.6
pi install git:github.com/TheWhiteWater/tube-bridge@v1.1.6
pi list
```

This registers one status tool plus all 17 MCP tools with the `tube_bridge_` prefix. The adapter reads the existing `plugin.json` and `mcp.json`, launches only the local stdio runtime, preserves bounded text and image content, and forwards only an allowlisted child-process environment.

The Pi package manager installs the Node adapter dependency but does not install Python or ffmpeg. Ensure the `python3` visible to Pi is Python 3.12+ with the tube-bridge dependencies installed; install `ffmpeg` separately to use `youtube_get_frame`. By default, Pi-managed state lives under the platform data directory; set `TUBE_BRIDGE_PI_DATA` to move that root. An explicit TUBE_BRIDGE_CACHE still takes precedence for the runtime databases. The optional live frame gate is `/tube-bridge-selftest frame`.

Remove the package with:

```bash
pi remove git:github.com/TheWhiteWater/tube-bridge@v1.1.6
```

If a desktop client cannot find `uvx`, replace `"uvx"` with the absolute path returned by `which uvx` on macOS/Linux or `where.exe uvx` on Windows.

## Try the complete research workflow

Ask your agent:

> Search YouTube for recent videos about local-first AI agents. Read the transcript of the strongest result, add it to a corpus named `local-agents`, find the section discussing memory, return the timestamped source link, and extract a frame from that moment.

The agent can complete that request with this tool sequence:

```text
youtube_search(query="local-first AI agents", order="date")
youtube_get_transcript(url="https://www.youtube.com/watch?v=VIDEO_ID", with_timestamps=true)
corpus_create(corpus_id="local-agents", label="Local-first AI Agents")
corpus_add(corpus_id="local-agents", url="https://www.youtube.com/watch?v=VIDEO_ID")
corpus_search(corpus_id="local-agents", query="memory architecture")
youtube_get_frame(url="https://www.youtube.com/watch?v=VIDEO_ID", timestamp_ms=FOUND_TIME_MS)
```

Add more videos with `corpus_add`, then use `corpus_search` to search across all of their transcripts at once.

## Tools

| Tool | YouTube API key | What it does |
|---|:---:|---|
| `youtube_search` | Optional | Search videos with date, channel, duration, and ordering filters |
| `youtube_get_video_info` | Optional | Get title, duration, views, channel, description, and tags |
| `youtube_get_trending` | Optional | Get currently trending videos |
| `youtube_get_channel_videos` | No | Get recent uploads from a channel URL or `@handle` |
| `youtube_get_playlist` | No | Get videos from a playlist |
| `youtube_get_transcript` | No | Get a transcript, optionally with `[MM:SS]` timestamps |
| `youtube_get_frame` | No | Return one ephemeral JPEG near an integer-millisecond timestamp |
| `youtube_get_available_languages` | No | List manual and auto-generated subtitle tracks |
| `youtube_get_comments` | Required | Get top-level comments with likes and reply counts |
| `youtube_search_channels` | Required | Search channels and filter by subscriber count |
| `youtube_get_channel_info` | Required | Get channel statistics, country, and keywords |
| `corpus_create` | No | Create a named local corpus |
| `corpus_add` | No | Fetch, chunk, and locally embed a video transcript |
| `corpus_search` | No | Semantically search a corpus with timestamped results |
| `corpus_list` | No | List corpora with video and chunk counts |
| `corpus_delete` | No | Permanently delete a corpus and its vectors |
| `tube_bridge_help` | No | Read runtime documentation and known limitations |

**No** means no YouTube Data API key is needed; network access to YouTube may still be required. Search, video information, and trending work without a key through yt-dlp and upgrade to Data API v3 when a key is configured.

## Optional YouTube Data API key

A YouTube Data API v3 key unlocks comments, channel search, and channel details. It also improves search, video information, and trending reliability.

Create a key in [Google Cloud Console](https://console.cloud.google.com/), enable **YouTube Data API v3**, and expose it to the process launching tube-bridge:

```bash
export YOUTUBE_API_KEY="your-key"
```

Keep keys out of committed MCP configuration files. Use your client's secret/environment support where available.

## Local semantic corpus

Corpus storage and embedding inference are local to the machine running tube-bridge.

- **Storage:** SQLite plus sqlite-vec in `~/.tube_bridge/corpus.db`
- **Embeddings:** BGE-small-en-v1.5 through fastembed
- **Chunking:** 80-second windows with 20-second overlap
- **Ranking:** overlap deduplication and source-aware per-video limits
- **Results:** similarity score, time span, video title, canonical URL, and timestamp URL

Set `TUBE_BRIDGE_CACHE` to move both corpus and cache databases:

```bash
export TUBE_BRIDGE_CACHE="/path/to/tube-bridge-data"
```

The embedding model may be downloaded on first use. After the assets are available, embedding inference does not require an external model API.

## Frame extraction

`youtube_get_frame` requires `ffmpeg` on `PATH`; the Docker image already includes it.

Each call downloads a short temporary section around `timestamp_ms`, returns one bounded JPEG as MCP `ImageContent`, and removes the temporary media before returning. It does not create a frame or clip library.

## Other ways to run

### Persistent PyPI installation

```bash
pip install tube-bridge

tube-bridge          # stdio
tube-bridge --http   # Streamable HTTP on port 8080
```

### Docker

```bash
docker run --rm -p 8080:8080 ghcr.io/thewhitewater/tube-bridge:latest
```

The health endpoint is `http://localhost:8080/health`; the Streamable HTTP endpoint is `http://localhost:8080/mcp`.

### Official MCP Registry

Registry name: [`io.github.TheWhiteWater/tube-bridge`](https://registry.modelcontextprotocol.io/)

Registry-aware clients can install the PyPI distribution with `uvx` and launch the stdio server without a hosted intermediary.

## Remote HTTP configuration

For an HTTP instance you operate:

```json
{
  "mcpServers": {
    "tube-bridge": {
      "type": "http",
      "url": "https://your-host.example/mcp"
    }
  }
}
```

Protect remote MCP routes by setting a server-side Bearer key:

```bash
export TUBE_BRIDGE_AUTH_KEY="choose-a-long-random-value"
tube-bridge --http
```

Then configure a header-capable client:

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

`/health` remains public. `/mcp`, `/sse`, and `/messages` require the Bearer key when `TUBE_BRIDGE_AUTH_KEY` is set. Legacy SSE is available at `/sse` for clients that still need it.

## Environment variables

| Variable | Required | Purpose |
|---|:---:|---|
| `YOUTUBE_API_KEY` | No | Enables the 3 API-only tools and upgrades supported discovery calls |
| `TUBE_BRIDGE_PROXY` | No | Routes yt-dlp and transcript requests through an HTTP(S) or SOCKS proxy |
| `TUBE_BRIDGE_CACHE` | No | Changes the directory containing `cache.db` and `corpus.db` |
| `TUBE_BRIDGE_AUTH_KEY` | No | Protects self-hosted HTTP MCP routes with a static Bearer token |

## How it works

```text
MCP client
   │
   ├── discovery and metadata ── Data API v3 (when configured)
   │                          └─ yt-dlp fallback
   ├── transcripts ───────────── youtube-transcript-api
   ├── timestamped frames ────── yt-dlp + ffmpeg → ephemeral JPEG
   └── semantic corpus ───────── SQLite + sqlite-vec + local fastembed
```

- stdio is recommended for local clients;
- Streamable HTTP is available at `/mcp` for self-hosted remote use;
- successful fallback responses keep their normal schemas;
- controlled failures use typed MCP errors with stable `code`, `source`, and `retryable` fields;
- cache and corpus databases are separate and remain operator-owned.

## Agent Plugin preview

[GitHub Releases](https://github.com/TheWhiteWater/tube-bridge/releases) include `tube-bridge-agent-plugin-<version>.zip`, containing:

- the local stdio MCP configuration;
- the `tube-bridge-research` skill;
- research templates and source-evaluation guidance.

Agent Plugins v1 does not standardize dependency installation. Install Python 3.12+, ffmpeg, and the package dependencies in the environment used by the plugin host. The bundle contains no credentials.

## Known limitations

- YouTube can restrict anonymous yt-dlp and transcript requests, especially from cloud-hosting IP ranges.
- A Data API key improves discovery and metadata reliability but does not replace transcript access.
- Initial local embedding-model setup may require network access and additional disk space.
- tube-bridge is self-hosted software; it does not provide accounts, public hosted access, managed storage, or an SLA.

If YouTube blocks requests from your network, set `TUBE_BRIDGE_PROXY`. Keep proxy credentials in environment variables rather than committed configuration.

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

`python test_tools.py` is an optional live YouTube smoke test. The deterministic test suite does not call YouTube.

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute. Security reports should follow [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
