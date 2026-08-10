"""tube-bridge — MCP server wiring: tool registration + dispatch."""

import base64
import json

from mcp.server import Server
from mcp.types import ImageContent, Tool, TextContent

from .tools import (
    search, search_channels,
    video_info, trending, channel_videos, playlist,
    transcript, available_languages, video_frame,
    comments, channel_info,
    corpus_create, corpus_add, corpus_search, corpus_list, corpus_delete,
)
from .youtube.client import extract_video_id
from .youtube.frame import ExtractedFrame

VERSION = "1.1.0"
MAX_FRAME_IMAGE_DATA_CHARS = 2_000_000


HELP_TEXT = {
    "server": "tube-bridge",
    "version": VERSION,
    "description": "YouTube MCP server — search, discovery, transcripts, comments.",
    "architecture": {
        "dual_source": "Data API v3 primary, yt-dlp fallback for search, video_info, trending",
        "transcripts": "youtube-transcript-api only (no Data API v3 alternative for subtitles)",
        "caching": "lru_cache on video_info (64) and transcripts (32)",
        "retry": "2 retries with exponential backoff for yt-dlp subprocess",
    },
    "tools": [],
    "known_limitations": [
        "Datacenter IPs (Railway, AWS): transcripts may fail with bot detection. No Data API v3 alternative.",
        "yt-dlp anonymous search degraded by YouTube. Prefer Data API v3 when key is set.",
        "Trending yt-dlp URL fragile — Data API v3 used as primary when key present.",
        "youtube_get_frame requires yt-dlp network access and an ffmpeg executable on PATH.",
    ],
    "api_key_setup": "Set YOUTUBE_API_KEY env var. Get from https://console.cloud.google.com/apis/library/youtube.googleapis.com",
}


server = Server("tube-bridge", version=VERSION)


def _build_tools() -> list[Tool]:
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
            description="Transcript/subtitles of a YouTube video. Uses the original/default language; manual > ASR within that language.",
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
            name="youtube_get_frame",
            description="Extract one ephemeral JPEG near an integer-millisecond timestamp. Returns metadata plus MCP ImageContent; accuracy is best-effort at a decoded frame boundary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                    "timestamp_ms": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Frame timestamp in integer milliseconds",
                    },
                    "max_width": {
                        "type": "integer",
                        "minimum": 64,
                        "maximum": 1280,
                        "default": 640,
                        "description": "Maximum JPEG width in pixels (default 640)",
                    },
                },
                "required": ["url", "timestamp_ms"],
                "additionalProperties": False,
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
            description="Semantic search within a corpus. Deduplicates overlapping windows, limits source domination, and returns titles plus timestamp URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "corpus_id": {"type": "string", "description": "Corpus ID to search in"},
                    "query": {"type": "string", "description": "Natural language search query"},
                    "top_k": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "description": "Max results (default 10, max 50)",
                        "default": 10,
                    },
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


TOOL_CATALOG = tuple(_build_tools())
_DATA_API_REQUIRED = {
    "youtube_search_channels", "youtube_get_channel_info", "youtube_get_comments",
}
_UPGRADES_WITH_KEY = {
    "youtube_search", "youtube_get_video_info", "youtube_get_trending",
}
HELP_TEXT["tools"] = [
    {
        "name": tool.name,
        "key_required": tool.name in _DATA_API_REQUIRED,
        "upgrades_with_key": tool.name in _UPGRADES_WITH_KEY,
        "description": tool.description,
    }
    for tool in TOOL_CATALOG
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return list(TOOL_CATALOG)


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    try:
        result = await _handle_tool(name, arguments)
        if isinstance(result, ExtractedFrame):
            metadata = {
                "video_id": result.video_id,
                "requested_timestamp_ms": result.requested_timestamp_ms,
                "actual_timestamp_ms": None,
                "timestamp_accuracy": "best_effort_frame_boundary",
                "mime_type": result.mime_type,
                "bytes": len(result.data),
                "sha256": result.sha256,
                "retention": "ephemeral",
            }
            encoded_image = base64.b64encode(result.data).decode("ascii")
            if len(encoded_image) > MAX_FRAME_IMAGE_DATA_CHARS:
                raise RuntimeError("Frame exceeds serialized image response limit")
            return [
                TextContent(
                    type="text",
                    text=json.dumps(metadata, ensure_ascii=False, indent=2),
                ),
                ImageContent(
                    type="image",
                    data=encoded_image,
                    mimeType=result.mime_type,
                ),
            ]
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
    except RuntimeError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]
    except Exception:
        return [TextContent(
            type="text",
            text=json.dumps({"error": "Unexpected error"}, ensure_ascii=False),
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

        case "youtube_get_frame":
            return await video_frame(
                extract_video_id(args["url"]),
                args["timestamp_ms"],
                args.get("max_width", 640),
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
