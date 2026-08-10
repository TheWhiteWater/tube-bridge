# 04 — Glossary

| Term | Definition |
|------|-----------|
| **MCP** | Model Context Protocol — JSON-RPC protocol for AI agent ↔ tool communication. tube-bridge implements stdio, HTTP (Streamable HTTP), and SSE transports. |
| **Streamable HTTP** | Stateless MCP transport at `/mcp` (built via `StreamableHTTPSessionManager`). Recommended for remote deployments. Replaces legacy SSE. |
| **SSE (legacy)** | Server-Sent Events MCP transport at `/sse` with `/messages` POST handler. Deprecated in favor of Streamable HTTP. Retained for backward compatibility. |
| **stdio transport** | MCP transport over stdin/stdout. MCP client normally spawns the installed `tube-bridge` command (`tube_bridge.cli:main`); root `server.py` is a source-checkout compatibility wrapper. |
| **dual-source** | tube-bridge architecture pattern: YouTube Data API v3 primary → yt-dlp fallback. Used for search, video_info, and trending. Quota exhaustion falls through gracefully. |
| **Data API v3** | YouTube's official REST API; requires `YOUTUBE_API_KEY` from Google Cloud Console. Provides search/video_info/trending results with richer metadata and unlocks comments, channel search, and channel info. Default allocation: 100 search.list calls/day, 100 videos.insert calls/day, and 10,000 units/day combined for other endpoints, subject to change. Additional allocation uses YouTube's audit/extension process. |
| **Data API setup** | Users obtain a `YOUTUBE_API_KEY` from Google Cloud Console and set it as an environment variable. 14 of 17 source-tree tools work without it; 3 require it. No API key is bundled or committed. |
| **yt-dlp** | YouTube downloader fork; used via subprocess for search/metadata/playlist/channel extraction. `--flat-playlist` mode for efficient listing. 2 retries with exponential backoff. |
| **youtube-transcript-api** | Python library wrapping YouTube's TimedText API for subtitle extraction. tube-bridge first selects the original/default language cohort, then prefers matching manual captions over ASR. |
| **InnerTube API** | YouTube's internal API used by the web client; what yt-dlp calls under the hood. Anonymous access, no auth required. |
| **TimedText API** | YouTube endpoint (`/api/timedtext`) for subtitle/CC retrieval. No auth needed. Used by `youtube-transcript-api`. |
| **ASR** | Automatic Speech Recognition — auto-generated captions. With no explicit language, the first ASR track identifies the default language family; matching manual captions are preferred without crossing into unrelated foreign tracks. |
| **proxy** | User-owned `TUBE_BRIDGE_PROXY` environment variable. Routes both yt-dlp subprocess and youtube-transcript-api through a proxy to work around datacenter IP bot detection. |
| **ImageContent** | MCP image response content. `youtube_get_frame` returns metadata followed by one base64 JPEG `ImageContent`; raw JPEG is capped at 1,500,000 bytes, base64 data at 2,000,000 characters, and neither clip nor image is persisted. |
| **cache.db** | Persistent SQLite database for transcript segments and video metadata. Located at `$TUBE_BRIDGE_CACHE/cache.db` (default `~/.tube_bridge`). Tables: `transcripts`, `video_info`. WAL journal mode. |
| **corpus.db** | Separate SQLite database for semantic search corpora. Located at `$TUBE_BRIDGE_CACHE/corpus.db` (same directory as cache.db). Tables: `corpora`, `corpus_chunks`, `corpus_added_videos`, plus per-corpus `vec_{id}` virtual tables. WAL journal mode. |
| **sqlite-vec** | SQLite extension for vector similarity search. Creates per-corpus `vec_{corpus_id}` virtual tables with `MATCH` query support. Distributed as a Python package (`sqlite-vec>=0.1.0`). |
| **fastembed** | Python library for local text embedding inference. Uses BGE-small-en-v1.5 (384-dim) by default. Configurable via `TUBE_BRIDGE_EMBEDDING_MODEL`. Inference runs locally after model assets are available; initial model acquisition may require network. Zero API keys. |
| **embedding model** | The model used to convert text chunks and search queries into vectors. Default: `BAAI/bge-small-en-v1.5`. Each corpus records its embedding model at creation; model mismatch on add/search raises an error. Switching models requires deleting and recreating corpora. |
| **corpus** | A named collection of video transcripts with embeddings for semantic search. Created via `corpus_create`, populated via `corpus_add`, searched via `corpus_search`. |
| **chunk** | A window of transcript segments (80 seconds, 20-second overlap) converted to a single embedding vector. Stored in `corpus_chunks` table with timestamps and text. The per-corpus vector table stores the embedding. |
| **corpus_add workflow** | 1. Fetch transcript over network (youtube-transcript-api, cache-aware). 2. Chunk segments into overlapping windows. 3. Embed each chunk locally via fastembed. 4. Store chunks and vectors. Idempotent via `corpus_added_videos` tracking. |
| **corpus score** | Semantic similarity computed as `round(1.0 - distance, 4)` without clamping. A higher computed score corresponds to a lower returned distance from sqlite-vec. Consumers must not assume a bounded [0, 1] range — distance can theoretically exceed 1.0, producing negative scores. |
| **[Grabbit MCP](https://grabbitapp.com) companion workflow** | An agent independently invoking two separate MCPs (tube-bridge and Grabbit) with no code integration between them. For example, an agent uses tube-bridge to find videos and then separately uses Grabbit to save links. There is no connector, dependency, shared service, or implementation roadmap between the two projects. |
| **publication gate** | Core checks in `docs/planning/PUBLICATION_READINESS.md` for the self-hosted package, releases, container, CI, documentation and secret exclusion. No hosted-demo gate exists. |
| **Flat playlist** | yt-dlp mode (`--flat-playlist`) returning metadata without full page fetch. Used by channel_videos and playlist tools for efficiency. |
| **source checkout install** | tube-bridge builds as wheel+sdist and installs into an isolated environment; the packaged `tube-bridge` console entrypoint and MCP runtime are verified. PyPI installation is also externally verified. |
| **quota extension** | No additional allocation beyond the default has been documented as requested or granted. YouTube's official docs identify the audit/extension process; no purchasable quota tier was identified. |
| **TME** | Task Model Engine — BrainOps hypothesis tracker and operating map. |
| **ADR** | Architecture Decision Record — documented technical decision with context, rationale, and consequences. See `docs/adr/`. |
| **Genesis** | BrainOps lifecycle template for project birth: discover → attach → plan → persist → gate → publish. |
