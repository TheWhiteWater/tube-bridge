# 00 — Mission & Vision

## Vision

**Every AI agent should be able to interact with YouTube as naturally as a human — search, discover, and extract knowledge — without API keys, registration, or vendor lock-in.**

yt-mcp is the open bridge between AI agents and YouTube. It converts YouTube from a walled video platform into a queryable knowledge base accessible through the Model Context Protocol (MCP).

## Mission

Build the **most complete, zero-friction YouTube MCP server** — covering search, discovery, metadata, transcripts, playlists, channels, and comments — with zero registration requirements and zero API keys for core functionality.

## Principles

1. **Zero-friction first** — Works out of the box. No API keys, no OAuth, no registration. Just `pip install` and `python3 server.py`.
2. **Complete coverage** — Not just transcripts. Search, channels, playlists, trending, comments, metadata. The full YouTube surface for agents.
3. **Agent-native design** — Every tool returns structured JSON optimized for LLM consumption. Descriptions, schemas, and error messages are written for AI agents, not humans.
4. **Graceful degradation** — yt-dlp as primary (no keys), Data API v3 as optional upgrade for comments/rate-limits. Never break when optional deps are missing.
5. **Python stack purity** — Single-file server, stdlib-heavy, minimal dependencies. No npm, no Docker required. One process, one language.
6. **Station-native** — First-class BrainOps lifecycle: TME, ADR, gates, vision-aligned development.

## Success Criteria

- An AI agent can search YouTube, get a transcript, and analyze a video in under 3 tool calls
- 8+ tools available via stdio MCP transport
- Zero API keys needed for transcripts, search, metadata, channels, playlists
- Comment extraction via optional Data API v3 key with clean fallback
- Passes project-genesis gate with full constitution + TME map

## Anti-Goals (what success is NOT)

- NOT a YouTube downloader
- NOT a video player or UI
- NOT a replacement for YouTube Data API — a complementary, agent-first alternative
- NOT a scraping service at scale — designed for agent use, not bulk harvesting
