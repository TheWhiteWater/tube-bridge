# 04 — Glossary

| Term | Definition |
|------|-----------|
| **MCP** | Model Context Protocol — JSON-RPC protocol for AI agent ↔ tool communication |
| **Stdio transport** | MCP transport over stdin/stdout; server runs as child process |
| **yt-dlp** | YouTube downloader fork; used here for search/metadata extraction via subprocess |
| **youtube-transcript-api** | Python library wrapping YouTube's TimedText API for subtitle extraction |
| **InnerTube API** | YouTube's internal API used by the web client; what yt-dlp calls under the hood |
| **TimedText API** | YouTube endpoint (`/api/timedtext`) for subtitle/CC retrieval; no auth needed |
| **Data API v3** | YouTube's official REST API; requires API key and has quota system (10k units/day) |
| **ASR** | Automatic Speech Recognition — auto-generated captions. Lower quality than manual subs. |
| **Flat playlist** | yt-dlp mode (`--flat-playlist`) returning metadata without full page fetch |
| **TME** | Task Model Engine — BrainOps hypothesis tracker and operating map |
| **ADR** | Architecture Decision Record — documented technical decision with context and rationale |
| **Genesis** | BrainOps lifecycle template for project birth: discover → attach → plan → persist → gate → publish |
