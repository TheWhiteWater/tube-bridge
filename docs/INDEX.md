# tube-bridge — Project Index

**YouTube MCP server for AI agents. 16 tools: search, discovery, transcripts, comments, semantic corpus. 13 zero-setup, 3 with optional Data API v3 key. MIT self-hosted MCP with disposable try-before-install demo.**

## Quick Nav

| Document | Purpose |
|----------|---------|
| [PROJECT_VISION.md](../PROJECT_VISION.md) | Product boundaries, tool baseline, self-hosted model |
| [README.md](../README.md) | Public-facing readme: quick start, tools, architecture, deployment |
| [00_MISSION.md](constitution/00_MISSION.md) | Why this project exists |
| [01_SYSTEM_CONTEXT.md](constitution/01_SYSTEM_CONTEXT.md) | Where it fits |
| [02_ARCHITECTURE.md](constitution/02_ARCHITECTURE.md) | How it's built |
| [03_DATA_MODEL.md](constitution/03_DATA_MODEL.md) | What data flows |
| [04_GLOSSARY.md](constitution/04_GLOSSARY.md) | Terminology |
| [05_NON_GOALS.md](constitution/05_NON_GOALS.md) | What we DON'T do |
| [06_ADR_RULES.md](constitution/06_ADR_RULES.md) | How architecture decisions get made |
| [MVP_SCOPE.md](planning/MVP_SCOPE.md) | Implementation baseline shipped in source |
| [WORK_BREAKDOWN.md](planning/WORK_BREAKDOWN.md) | Blocks A–F: decomposition and dependencies |
| [PUBLICATION_READINESS.md](planning/PUBLICATION_READINESS.md) | Two-surface readiness checklist with gates |
| [OPEN_QUESTIONS.md](planning/OPEN_QUESTIONS.md) | Resolved questions and blocking decisions |
| [ADR-001](adr/001-demo-api-quota-and-product-boundary.md) | Demo API access, quota boundary, self-hosted product boundary |

## Tool Inventory

10 YouTube interaction + 5 corpus + 1 help = **16 tools** registered in `tube_bridge/server.py` `list_tools()` (lines 67–248).

- **13 tools callable without API key** (zero-setup): `youtube_search` (yt-dlp fallback), `youtube_get_video_info`, `youtube_get_trending`, `youtube_get_channel_videos`, `youtube_get_playlist`, `youtube_get_transcript`, `youtube_get_available_languages`, `corpus_create`, `corpus_add`, `corpus_search`, `corpus_list`, `corpus_delete`, `tube_bridge_help`.
- **3 tools require YouTube Data API v3 key:** `youtube_get_comments`, `youtube_search_channels`, `youtube_get_channel_info`.

Search, video_info, and trending upgrade to higher-quality Data API v3 results when the key is present.

## State

- **Architecture direction:** ADR-001 accepted (2026-08-08) — demo API access, quota boundary, and self-hosted product boundary. Not launch approval.
- **Current WorkItems:** WI-00027 documentation synchronization is ready for gate; WI-00028 core publication hardening is complete; WI-00029 disposable-demo hardening remains draft.
- **Active TME direction:** DIR-004-publication-productization
- **Core publication:** Accepted and externally verified through GitHub Release, PyPI, public GHCR, hosted CI, clean install, and registry-image MCP checks.
- **Disposable demo:** Separate WI-00029 gate; quota and retention decisions are documented but implementation/verification remain open. No commercial extension, product gateway, Grabbit connector, or browser-extension roadmap exists.
- **Last updated:** 2026-08-08
