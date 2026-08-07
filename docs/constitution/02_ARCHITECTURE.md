# 02 — Architecture

## Overview

yt-mcp is a **single-file stdio MCP server** (~600 lines) that wraps two battle-tested libraries:

```
Agent (Claude / Codex / Hermes)
   │ MCP stdio (JSON-RPC)
   ▼
yt-mcp server.py
   ├── youtube-transcript-api  →  Transcripts (TimedText API)
   └── yt-dlp (subprocess)     →  Search, Metadata, Channels, Playlists, Trending
```

## Transport

**stdio only.** No HTTP server, no WebSocket, no long-running daemon. The MCP client (Hermes, Claude Desktop, etc.) spawns `python3 server.py` as a child process and communicates via stdin/stdout JSON-RPC.

Rationale:
- Zero network surface — no ports, no auth, no CORS
- Process lifecycle tied to client — no orphaned servers
- Deployment: a single `command` + `args` in MCP client config

## Dependency Strategy

| Dependency | Role | Required? | Notes |
|-----------|------|-----------|-------|
| `mcp` (>=1.0) | MCP protocol server | Yes | Stdio transport, tool registration |
| `yt-dlp` | Search, metadata, discovery | Yes | Called as subprocess with timeout |
| `youtube-transcript-api` | Transcript extraction | Yes | TimedText API, no auth needed |
| `google-api-python-client` | YouTube Data API v3 | **No** (optional) | Only for comments; graceful fallback if missing |

## Module Map

```
server.py
├── [L0] Constants & Types
│   └── VideoInfo dataclass
│
├── [L1] yt-dlp helpers
│   ├── _run_ytdlp()          — single JSON result
│   ├── _run_ytdlp_multi()    — multiple JSON results (playlists, search)
│   ├── _extract_video_id()   — URL → ID regex
│   └── _parse_video_info()   — raw JSON → VideoInfo
│
├── [L2] Transcript helpers
│   ├── _get_yt_api()              — lazy singleton
│   ├── _get_transcript()          — segments + language + is_generated
│   ├── _get_transcript_with_meta()— dict wrapper
│   └── _get_available_languages() — language list
│
├── [L3] Tool implementations (async)
│   ├── _search()            — yt-dlp ytsearchN:
│   ├── _video_info()        — yt-dlp --dump-json
│   ├── _trending()          — YouTube trending page
│   ├── _channel_videos()    — channel/@handle -> uploads
│   ├── _playlist()          — playlist URL -> videos
│   ├── _transcript()        — plain text or [MM:SS] lines
│   └── _available_languages()
│
├── [L4] MCP Server wiring
│   ├── list_tools()         — 7 tools with JSON schemas
│   ├── call_tool()          — dispatch
│   ├── _handle_tool()       — match → implementation
│   └── main()               — stdio_server.run()
```

## Design Decisions

1. **Subprocess, not Python bindings** — yt-dlp is called via `subprocess.run()` with timeout. Python bindings exist but are unstable. Subprocess gives clean process isolation and predictable timeouts.

2. **Flat playlist for search/channels** — `--flat-playlist` flag means yt-dlp returns metadata without fetching full video pages. This is fast (50 results in <5s) but lacks descriptions/tags. Full metadata is available via `youtube_get_video_info` on individual videos.

3. **Lazy transcript API** — `YouTubeTranscriptApi` is instantiated once and reused. It maintains an internal HTTP session, reducing connection overhead.

4. **Manual > ASR** — Transcript priority: manual subtitles first, auto-generated second. Manual subs have better punctuation and accuracy.

5. **Single-file by design** — 600 lines is the sweet spot: small enough to audit, large enough to be useful. Discovery layer (comments, Data API v3) will be added as sibling functions in the same file or as `discovery.py` import.
