# Project Vision — yt-mcp

**Last updated:** 2026-08-07
**Author:** W-1020 (Architect)
**Status:** active

## North Star

Every AI agent can interact with YouTube as naturally as a human — search, discover, extract knowledge — without API keys, registration, or vendor lock-in.

## Development Path

### Phase 1 — Core MVP (DONE)
7 tools: search, video info, trending, channels, playlists, transcript (plain/timed), languages. Zero keys. Single-file stdio server. Tested on real YouTube data.

### Phase 2 — Discovery Layer (NEXT)
- Comment extraction via Data API v3 (optional key)
- Dual-source architecture: yt-dlp primary, API v3 as upgrade path
- ADR-001: formalize discovery layer strategy

### Phase 3 — Production
- GitHub repo with AGENTS.md
- CI pipeline (smoke tests against known videos)
- PyPI package (`pip install yt-mcp`)
- MCP registry submission

### Phase 4 — Intelligence
- Semantic search across transcripts (ChromaDB)
- Frame/screenshot extraction
- Channel analytics

## Project Spirit

- **Agent-first, not human-first** — tools return structured JSON, not pretty text
- **Zero friction forever** — core functionality never requires API keys
- **Library, not service** — one Python file, one process, stdio transport
- **Open source from day one** — MIT license, community contributions welcome

## Alignment Check

When evaluating whether work is on-vector, ask:
1. Does it work without API keys? (If no — is it in the optional upgrade path?)
2. Is the output optimized for LLM consumption?
3. Does it keep the single-file simplicity?
4. Could an agent accomplish something useful in <3 tool calls?

## Roadmap

| Milestone | Status | Target |
|-----------|--------|--------|
| 7 core tools | ✅ DONE | 2026-08-07 |
| GitHub + AGENTS.md | 🔄 IN PROGRESS | 2026-08-07 |
| Project Genesis gate PASS | 🔄 IN PROGRESS | 2026-08-07 |
| ADR-001: Discovery layer | 📋 PLANNED | 2026-08-10 |
| Comments tool (Data API v3) | 📋 PLANNED | 2026-08-14 |
| PyPI package | 📋 PLANNED | 2026-08-21 |
