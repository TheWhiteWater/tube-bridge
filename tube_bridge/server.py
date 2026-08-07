"""tube-bridge — MCP server wiring: tool registration + dispatch."""

import json

from mcp.server import Server
from mcp.types import Tool, TextContent

from .tools import (
    search, search_channels,
    video_info, trending, channel_videos, playlist,
    transcript, available_languages,
    comments, channel_info,
    corpus_create, corpus_add, corpus_search, corpus_list, corpus_delete,
)
from .youtube.client import extract_video_id

HELP_TEXT = {
    "server": "tube-bridge",
    "version": "1.0.0",
    "tools": 11,
    "description": "YouTube MCP server — search, discovery, transcripts, comments.",
    "architecture": {
        "dual_source": "Data API v3 primary, yt-dlp fallback for search, video_info, trending",
        "transcripts": "youtube-transcript-api only (no Data API v3 alternative for subtitles)",
        "caching": "lru_cache on video_info (64) and transcripts (32)",
        "retry": "2 retries with exponential backoff for yt-dlp subprocess",
    },
    "tools": [
        {"name": "youtube_search", "key_required": False, "upgrades_with_key": True,
         "description": "Search videos. Rich filters when API key present: date, channel, duration, order."},
        {"name": "youtube_search_channels", "key_required": True, "upgrades_with_key": False,
         "description": "Search channels by name/topic with subscriber filters."},
        {"name": "youtube_get_channel_info", "key_required": True, "upgrades_with_key": False,
         "description": "Channel stats: subscribers, views, videos, country, keywords."},
        {"name": "youtube_get_video_info", "key_required": False, "upgrades_with_key": True,
         "description": "Video metadata: title, duration, views, channel, tags, description."},
        {"name": "youtube_get_trending", "key_required": False, "upgrades_with_key": True,
         "description": "Trending videos. Data API v3 primary, yt-dlp fallback."},
        {"name": "youtube_get_channel_videos", "key_required": False, "upgrades_with_key": False,
         "description": "Recent uploads from a channel (@handle or URL)."},
        {"name": "youtube_get_playlist", "key_required": False, "upgrades_with_key": False,
         "description": "All videos in a playlist."},
        {"name": "youtube_get_transcript", "key_required": False, "upgrades_with_key": False,
         "description": "Subtitles/transcript. Plain text or [MM:SS] timestamps. Manual > ASR."},
        {"name": "youtube_get_available_languages", "key_required": False, "upgrades_with_key": False,
         "description": "Available subtitle languages with manual/auto-generated flags."},
        {"name": "youtube_get_comments", "key_required": True, "upgrades_with_key": False,
         "description": "Top-level comments with likes and reply counts."},
        {"name": "tube_bridge_help", "key_required": False, "upgrades_with_key": False,
         "description": "This help text."},
    ],
    "known_limitations": [
        "Datacenter IPs (Railway, AWS): transcripts may fail with bot detection. No Data API v3 alternative.",
        "yt-dlp anonymous search degraded by YouTube. Prefer Data API v3 when key is set.",
        "Trending yt-dlp URL fragile — Data API v3 used as primary when key present.",
    ],
    "api_key_setup": "Set YOUTUBE_API_KEY env var. Get from https://console.cloud.google.com/apis/library/youtube.googleapis.com",
    "deploy_url": "https://tube-bridge-production.up.railway.app/mcp",
}


server = Server("tube-bridge")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="youtube_search",
            description="Search YouTube videos. Uses Data API v3 when YOUTUBE_API_KEY is set, falls back to yt-dlp. Filters: date range, channel, duration, order.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (default 10, max 50)", "default": 10},
                    "order": {"type": "string", "description": "Sort: date, rating, relevance, viewCount, title (API only)"},
                    "published_after": {"type": "string", "description": "ISO 8601 date filter (API only)"},
                    "published_before": {"type": "string", "description": "ISO 8601 date filter (API only)"},
                    "channel_id": {"type": "string", "description": "Restrict to channel ID (API only)"},
                    "video_duration": {"type": "string", "description": "short, medium, long (API only)"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="youtube_search_channels",
            description="Search YouTube channels by name/topic. Returns subscriber counts, video counts, country. Requires YOUTUBE_API_KEY.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Channel name or topic"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                    "min_subscribers": {"type": "integer", "description": "Minimum subscriber filter"},
                    "max_subscribers": {"type": "integer", "description": "Maximum subscriber filter"},
                    "order": {"type": "string", "description": "relevance, date"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="youtube_get_channel_info",
            description="Detailed channel metadata: subscribers, views, videos, country, keywords. Requires YOUTUBE_API_KEY.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string", "description": "YouTube channel ID (starts with UC...)"},
                },
                "required": ["channel_id"],
            },
        ),
        Tool(
            name="youtube_get_video_info",
            description="Detailed metadata for a YouTube video: title, duration, views, channel, description, tags.",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "YouTube video URL or ID"}},
                "required": ["url"],
            },
        ),
        Tool(
            name="youtube_get_trending",
            description="Currently trending YouTube videos. Uses Data API v3 when key present, yt-dlp fallback.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Max results (default 10)", "default": 10}},
            },
        ),
        Tool(
            name="youtube_get_channel_videos",
            description="Recent uploads from a YouTube channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_url": {"type": "string", "description": "Channel URL or @handle"},
                    "limit": {"type": "integer", "description": "Max videos (default 10)", "default": 10},
                },
                "required": ["channel_url"],
            },
        ),
        Tool(
            name="youtube_get_playlist",
            description="All videos in a YouTube playlist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "playlist_url": {"type": "string", "description": "Playlist URL"},
                    "limit": {"type": "integer", "description": "Max videos (default 20)", "default": 20},
                },
                "required": ["playlist_url"],
            },
        ),
        Tool(
            name="youtube_get_transcript",
            description="Transcript/subtitles of a YouTube video. Plain text or timestamped. Manual > ASR priority.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                    "lang": {"type": "string", "description": "Language code (e.g. en, ru). Auto-detect if not specified."},
                    "with_timestamps": {"type": "boolean", "description": "Include [MM:SS] timestamps (default: false)", "default": False},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="youtube_get_available_languages",
            description="Available subtitle languages for a video. Shows manual vs auto-generated.",
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "YouTube video URL or ID"}},
                "required": ["url"],
            },
        ),
        Tool(
            name="youtube_get_comments",
            description="Comments for a YouTube video. Requires YOUTUBE_API_KEY.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                    "max_results": {"type": "integer", "description": "Max comments (default 20)", "default": 20},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="corpus_create",
            description="Create a named corpus for semantic search over transcripts. Each corpus uses a fixed embedding model.",
            inputSchema={
                "type": "object",
                "properties": {
                    "corpus_id": {"type": "string", "description": "Unique corpus ID (e.g. 'iran-hormuz-2026')"},
                    "label": {"type": "string", "description": "Human-readable label (optional)"},
                },
                "required": ["corpus_id"],
            },
        ),
        Tool(
            name="corpus_add",
            description="Add a video transcript to a corpus. Auto-fetches transcript, chunks, and embeds. Idempotent: skip if already added.",
            inputSchema={
                "type": "object",
                "properties": {
                    "corpus_id": {"type": "string", "description": "Corpus ID to add to"},
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                    "force_reembed": {"type": "boolean", "description": "Re-embed even if already indexed", "default": False},
                },
                "required": ["corpus_id", "url"],
            },
        ),
        Tool(
            name="corpus_search",
            description="Semantic search within a corpus. Returns relevant transcript chunks with scores, timestamps, and video IDs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "corpus_id": {"type": "string", "description": "Corpus ID to search in"},
                    "query": {"type": "string", "description": "Natural language search query"},
                    "top_k": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                },
                "required": ["corpus_id", "query"],
            },
        ),
        Tool(
            name="corpus_list",
            description="List all available corpora with chunk and video counts.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="corpus_delete",
            description="Delete a corpus and all its chunks/vectors permanently.",
            inputSchema={
                "type": "object",
                "properties": {
                    "corpus_id": {"type": "string", "description": "Corpus ID to delete"},
                },
                "required": ["corpus_id"],
            },
        ),
        Tool(
            name="tube_bridge_help",
            description="Get tube-bridge documentation: available tools, architecture, known limitations, API key setup.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _handle_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
    except RuntimeError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Unexpected error: {e}"}, ensure_ascii=False),
        )]


async def _handle_tool(name: str, args: dict):
    match name:
        case "youtube_search":
            return await search(args["query"], args.get("limit", 10), args)

        case "youtube_search_channels":
            return await search_channels(args["query"], args.get("limit", 10), args)

        case "youtube_get_channel_info":
            return await channel_info(args["channel_id"])

        case "youtube_get_video_info":
            return await video_info(extract_video_id(args["url"]))

        case "youtube_get_trending":
            return await trending(args.get("limit", 10))

        case "youtube_get_channel_videos":
            return await channel_videos(args["channel_url"], args.get("limit", 10))

        case "youtube_get_playlist":
            return await playlist(args["playlist_url"], args.get("limit", 20))

        case "youtube_get_transcript":
            return await transcript(
                extract_video_id(args["url"]),
                args.get("lang"),
                args.get("with_timestamps", False),
            )

        case "youtube_get_available_languages":
            return await available_languages(extract_video_id(args["url"]))

        case "youtube_get_comments":
            return await comments(extract_video_id(args["url"]), args.get("max_results", 20))

        case "tube_bridge_help":
            return HELP_TEXT

        case "corpus_create":
            return await corpus_create(args["corpus_id"], args.get("label"))
        case "corpus_add":
            return await corpus_add(args["corpus_id"], extract_video_id(args["url"]), args.get("force_reembed", False))
        case "corpus_search":
            return await corpus_search(args["corpus_id"], args["query"], args.get("top_k", 10))
        case "corpus_list":
            return await corpus_list()
        case "corpus_delete":
            return await corpus_delete(args["corpus_id"])

        case _:
            raise ValueError(f"Unknown tool: {name}")
