# 05 — Non-Goals

These are explicit things we will NOT build into yt-mcp. They help prevent scope creep.

## Video downloading
yt-dlp can download videos, but yt-mcp is a metadata/transcript server. No `youtube_download` tool.

## Video upload / channel management
This is a read-only tool. No upload, no comment posting, no playlist editing.

## Authentication / user accounts
Zero auth. The server has no concept of "logged in user." All tools use anonymous access.

## Rate limiting / quota management
yt-mcp does not implement its own rate limiting. It relies on:
- yt-dlp's built-in retry/backoff
- Optional Data API v3 quota (managed by the API key owner)

## UI / Dashboard
No web UI. This is an MCP server for AI agents. CLI tooling may come later as a separate project.

## Bulk scraping
Designed for agent use (dozens of calls per session). Not optimized for thousands of parallel requests.

## Multi-language NLP
Transcripts are returned as-is. No translation, no sentiment analysis, no keyword extraction. The agent's LLM does that.
