# 01 — System Context

## What tube-bridge Is

An MIT self-hosted MCP server that lets AI agents search and inspect YouTube, retrieve transcripts and metadata, browse channels/playlists/comments, and build local semantic transcript corpora.

There is no public hosted demo. Every user installs and operates their own instance.

## Runtime Context

```text
AI Agent
  │ MCP JSON-RPC
  ├── stdio
  ├── Streamable HTTP /mcp
  └── legacy SSE /sse + /messages
       │
       ▼
tube-bridge
  ├── tube_bridge/cli.py          installed entrypoint and transport selection
  ├── tube_bridge/server.py       16-tool catalog, registration, help, dispatch
  ├── tube_bridge/tools.py        tool implementations
  ├── tube_bridge/transport.py    HTTP/SSE, optional Bearer, health
  ├── tube_bridge/cache.py        cache.db
  ├── tube_bridge/corpus.py       corpus.db, sqlite-vec, fastembed
  └── tube_bridge/youtube/
      ├── client.py               yt-dlp subprocess
      ├── api.py                  Data API v3 via stdlib urllib
      ├── transcript.py           youtube-transcript-api
      └── models.py               VideoInfo
       │
       ├── YouTube TimedText API
       ├── YouTube InnerTube through yt-dlp
       └── optional YouTube Data API v3
```

Retired modules `oauth.py`, `demo_policy.py`, and `demo_ttl.py` are not part of the active package.

## Transport Boundary

1. **stdio** — local child-process transport through the installed `tube-bridge` command.
2. **Streamable HTTP `/mcp`** — stateless recommended remote transport.
3. **SSE `/sse`** — legacy compatibility transport with `/messages` POST.
4. **`/health`** — public process health, server name, tool count, and static-auth status.

`TUBE_BRIDGE_AUTH_KEY` optionally protects `/mcp`, `/sse`, and `/messages`. Without it, self-hosted HTTP is open. There are no OAuth discovery/registration/authorization/token routes, invites, users, tester roles, or IP identities.

## Outbound Sources

| Source | Module | Auth | Purpose |
|---|---|---|---|
| YouTube TimedText | `youtube/transcript.py` | None | Captions/transcripts; optional proxy |
| YouTube InnerTube | `youtube/client.py` | None | yt-dlp search/metadata/channel/playlist fallback |
| YouTube Data API v3 | `youtube/api.py` | User-owned `YOUTUBE_API_KEY` | Comments, channel tools and upgraded results |

The core requires network access to YouTube but no external database, vector service, or embedding API. sqlite-vec and fastembed run locally after model assets are available.

## Trust Boundaries

- API keys, proxy URLs and Bearer keys come from the deploying user's environment.
- No credentials are bundled, committed, logged, or distributed by the project.
- yt-dlp runs as a timeout-bounded subprocess with captured output and retry behavior.
- Transcript network/proxy failures remain distinct from confirmed missing captions.
- The project does not provide shared upstream credentials or a hosted evaluation endpoint.

## Local Storage

- `cache.db` stores transcript/video metadata cache entries.
- `corpus.db` stores named corpora, chunks, added-video records, and per-corpus vectors.
- Both live under `TUBE_BRIDGE_CACHE` (default `~/.tube_bridge`).
- The self-hosting user controls retention and backups.
- `corpora.expires_at` remains nullable for compatibility with databases touched by earlier development builds; active code writes `NULL` and imposes no expiry worker.

## Integration Points

- MCP-compatible local or remote clients that support stdio, Streamable HTTP, or legacy SSE.
- Optional user-owned YouTube Data API project.
- Optional user-owned HTTP proxy.
- BrainOps Station for this repository's development lifecycle only.

The Operator's private Railway deployment is personal infrastructure protected by static Bearer auth. It is not a project integration point, public endpoint, demo, managed service, or compatibility promise.

## Product Boundary

- **Included:** all 16 tools, all active transports, optional static Bearer, cache/corpus logic, packaging and container distribution.
- **Excluded:** public demo, OAuth, tester program, accounts, hosted retention, shared quota/key access, billing, SLA, browser extension, and managed hosting.
- **Separate:** Grabbit is a different MCP with no connector, dependency, shared service, or implementation roadmap.
