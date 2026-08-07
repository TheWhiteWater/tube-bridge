# Project Vision — tube-bridge

**Last updated:** 2026-08-08
**Status:** Public release

## North Star

Every AI agent can interact with YouTube as naturally as a human — search, discover, extract knowledge, and build research corpora — without API keys, registration, or vendor lock-in.

## Development Path

### Phase 1 — Core MVP ✅ DONE
11 tools: search, video info, trending, channels, playlists, transcript (plain/timed), languages, comments, channel search, channel info, help. Zero keys for 8, 3 with optional API key. Dual-source architecture (API v3 → yt-dlp). Modular codebase (8 files).

### Phase 2 — Discovery Layer ✅ DONE
Comment extraction via Data API v3. Channel search with subscriber enrichment. Persistent SQLite cache. IPRoyal residential proxy for datacenter IP bot-detection workaround. Streamable HTTP (/mcp) transport.

### Phase 3 — Bridge Corpus ✅ DONE
Semantic search over YouTube transcripts via sqlite-vec + fastembed. Named corpora, chunking by transcript segments, embedding model per corpus. 5 new tools: corpus_create/add/search/list/delete.

### Phase 4 — Production ✅ DONE
GitHub repo (public), AGENTS.md, Railway deployment, README with self-hosting guide, MIT license, CI smoke tests.

### Phase 5 — Next
- PyPI package (`pip install tube-bridge`)
- Railway persistent volume for corpus DB
- Auth layer for public /mcp endpoint
- Graph layer: entity extraction from corpus → FOR/AGAINST signals (NEXUS-aligned)

## Project Spirit

- **Agent-first, not human-first** — tools return structured JSON
- **Zero friction forever** — core functionality never requires API keys
- **Library, not service** — one Python package, no external servers
- **Open source from day one** — MIT license

## Alignment Check

When evaluating whether work is on-vector:
1. Does it work without API keys? (If no — is it clearly optional?)
2. Is the output optimized for LLM consumption?
3. Does it keep the zero-external-services simplicity?
4. Could an agent accomplish something useful in <3 tool calls?
