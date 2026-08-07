# 01 — System Context

## What yt-mcp is

An MCP (Model Context Protocol) server that lets AI agents interact with YouTube:
- Search videos
- Get transcripts (plain text or timestamped)
- Discover trending content
- Browse channels and playlists
- Extract video metadata
- (Planned) Read comments

## Where it fits

```
AI Agent (Claude / Codex / Hermes / Cursor)
  │
  │  "Search YouTube for 'python async tutorial',
  │   get the transcript, summarize key points"
  │
  ▼
yt-mcp (stdio MCP server)          ← THIS PROJECT
  │
  ├── youtube-transcript-api  →  YouTube TimedText API (no auth)
  └── yt-dlp                  →  YouTube InnerTube API (no auth)
       │
       ▼
    YouTube servers
```

## Competitors & Alternatives

| Solution | Transcripts | Search | No API Key | Python |
|----------|:-----------:|:------:|:----------:|:------:|
| jkawamoto/mcp-youtube-transcript | ✅ | ❌ | ✅ | ✅ |
| kimtaeyoon83/mcp-server-yt | ✅ | ❌ | ✅ | ❌ (TS) |
| mcptube | ✅ | ❌ | ✅* | ✅ |
| YouTube Data API v3 | ❌ | ✅ | ❌ (key) | N/A |
| **yt-mcp** | ✅ | ✅ | ✅ | ✅ |

*AI features need API key

## Integration Points

1. **MCP Clients** — Any MCP-compatible client (Claude Desktop, Cursor, Codex, Hermes Agent)
2. **BrainOps Station** — Project lifecycle, TME operating map, ADR records
3. **Optional: YouTube Data API v3** — For comment extraction (rate-limited but stable contract)
