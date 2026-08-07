# AGENTS.md — tube-bridge

**Project:** YouTube MCP Server for AI Agents — tube-bridge
**Stack:** Python 3.12+, MCP 1.x, yt-dlp, youtube-transcript-api
**Transport:** stdio (JSON-RPC)
**License:** MIT

## Quick Start

```bash
# Install deps
pip install mcp yt-dlp youtube-transcript-api

# Run as MCP server
python3 server.py

# Test tools
python3 test_tools.py
```

## What This Project Is

A single-file MCP server (~600 lines) providing 7 tools for AI agents to interact with YouTube:
- `youtube_search` — search videos by query
- `youtube_get_video_info` — full metadata
- `youtube_get_trending` — trending videos
- `youtube_get_channel_videos` — channel uploads
- `youtube_get_playlist` — playlist contents
- `youtube_get_transcript` — transcript (plain or timestamped)
- `youtube_get_available_languages` — subtitle languages

Zero API keys. Zero registration.

## Architecture

```
server.py
├── yt-dlp subprocess    → Search, metadata, channels, playlists, trending
└── youtube-transcript-api → Transcripts, language list
```

See `docs/constitution/02_ARCHITECTURE.md` for full module map.

## Project State

- **Lifecycle:** `methodology.project_genesis` (discover → attach → plan → persist → gate → publish)
- **TME Run:** `yt-mcp-genesis-001`
- **WorkItem:** `WI-00026`
- **Directions:** DIR-001 (MVP done), DIR-002 (discovery layer), DIR-003 (production)
- **Vision:** `PROJECT_VISION.md`

## Working With This Code

### Adding a tool
1. Add function in `server.py` under `# Tool implementations`
2. Register in `list_tools()` with JSON schema
3. Add case in `_handle_tool()`
4. Add test in `test_tools.py`

### Testing
```bash
python3 test_tools.py  # Smoke test all tools against real YouTube data
```

### MCP Client Config

```yaml
mcp_servers:
  tube-bridge:
    command: python3
    args: [/home/ali/Workspace/BrainOps/Projects/tube-bridge/server.py]
    timeout: 120
```

## Conventions

- **Subprocess, not bindings** — yt-dlp is called via `subprocess.run()` with timeout
- **Flat playlist** for lists (fast), full `--dump-json` for single video info
- **Manual > ASR** — transcript priority: manual subtitles first, auto-generated second
- **Single file** — keep it under 1000 lines; split to modules only when it crosses that
- **JSON output** — all tools return structured JSON; no human-formatted text

## Key Docs

| Document | Path |
|----------|------|
| Project Vision | `PROJECT_VISION.md` |
| Mission & Principles | `docs/constitution/00_MISSION.md` |
| Architecture | `docs/constitution/02_ARCHITECTURE.md` |
| Data Model | `docs/constitution/03_DATA_MODEL.md` |
| Non-Goals | `docs/constitution/05_NON_GOALS.md` |
| ADR Rules | `docs/constitution/06_ADR_RULES.md` |
| Open Questions | `docs/planning/OPEN_QUESTIONS.md` |
| Index | `docs/INDEX.md` |
