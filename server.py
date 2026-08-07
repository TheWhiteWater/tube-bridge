"""
tube-bridge — YouTube MCP server for AI agents.

Provides:
  Search — youtube_search, youtube_get_trending
  Discovery — youtube_get_video_info, youtube_get_channel_videos, youtube_get_playlist
  Transcripts — youtube_get_transcript, youtube_get_available_languages
  Comments — youtube_get_comments (requires YOUTUBE_API_KEY env var)

yt-dlp for search/discovery. youtube-transcript-api for transcripts.
YouTube Data API v3 for comments (optional, zero keys needed for everything else).
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class VideoInfo:
    id: str
    title: str
    url: str
    duration: int | None = None  # seconds
    view_count: int | None = None
    channel: str | None = None
    channel_url: str | None = None
    upload_date: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ---------------------------------------------------------------------------
# yt-dlp helpers
# ---------------------------------------------------------------------------


def _run_ytdlp(args: list[str], timeout: int = 60) -> dict | None:
    """Run yt-dlp --dump-json and parse output."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--no-warnings", "--no-playlist", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return None
        # yt-dlp with --dump-json prints one JSON per line
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if not lines:
            return None
        data = json.loads(lines[0])
        return data
    except Exception:
        return None


def _run_ytdlp_multi(args: list[str], timeout: int = 60) -> list[dict]:
    """Run yt-dlp --dump-json and parse all output lines."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--no-warnings", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return []
        items = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items
    except Exception:
        return []


def _extract_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from URL or return as-is if already an ID."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot extract video ID from: {url_or_id}")


def _parse_video_info(data: dict) -> VideoInfo:
    """Parse yt-dlp JSON output into VideoInfo."""
    return VideoInfo(
        id=data.get("id", ""),
        title=data.get("title", ""),
        url=data.get("webpage_url", f"https://youtube.com/watch?v={data.get('id', '')}"),
        duration=data.get("duration"),
        view_count=data.get("view_count"),
        channel=data.get("channel") or data.get("uploader"),
        channel_url=data.get("channel_url") or data.get("uploader_url"),
        upload_date=data.get("upload_date"),
        description=(data.get("description", "") or "")[:500],
        thumbnail=data.get("thumbnail"),
        categories=data.get("categories"),
        tags=data.get("tags", [])[:20] if data.get("tags") else None,
    )


# ---------------------------------------------------------------------------
# YouTube Data API v3 helpers (optional — requires YOUTUBE_API_KEY)
# ---------------------------------------------------------------------------


def _api_key() -> str | None:
    """Get YouTube Data API key from environment."""
    return os.environ.get("YOUTUBE_API_KEY")


def _api_call(endpoint: str, params: dict) -> dict:
    """Make a YouTube Data API v3 request. Returns parsed JSON."""
    key = _api_key()
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not set. Comments require a YouTube Data API v3 key.")
    params["key"] = key
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _get_comments_api(video_id: str, max_results: int = 20) -> list[dict]:
    """Get top-level comments for a video via Data API v3."""
    data = _api_call("commentThreads", {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": min(max_results, 100),
        "order": "relevance",
        "textFormat": "plainText",
    })
    comments = []
    for item in data.get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        comments.append({
            "author": snippet.get("authorDisplayName", ""),
            "text": snippet.get("textDisplay", ""),
            "likes": snippet.get("likeCount", 0),
            "published_at": snippet.get("publishedAt", ""),
            "reply_count": item["snippet"].get("totalReplyCount", 0),
        })
    return comments


# ---------------------------------------------------------------------------
# YouTube Transcript helpers
# ---------------------------------------------------------------------------


_yt_api: Any = None  # Lazy singleton


def _get_yt_api():
    """Get or create YouTubeTranscriptApi instance."""
    global _yt_api
    if _yt_api is None:
        from youtube_transcript_api import YouTubeTranscriptApi
        _yt_api = YouTubeTranscriptApi()
    return _yt_api


def _get_transcript(video_id: str, lang: str | None = None) -> tuple[list[dict], str, bool]:
    """Get transcript segments. Returns (segments, language_code, is_generated).
    Prioritizes manual subtitles over auto-generated (ASR)."""
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

    api = _get_yt_api()

    def _try_fetch(transcript_obj) -> list[dict] | None:
        try:
            fetched = transcript_obj.fetch()
            return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
        except Exception:
            return None

    try:
        transcript_list = api.list(video_id)

        # Separate manual and generated, prioritize manual
        manual = [t for t in transcript_list if not t.is_generated]
        generated = [t for t in transcript_list if t.is_generated]

        # Filter by language if specified
        if lang:
            manual = [t for t in manual if t.language_code == lang]
            generated = [t for t in generated if t.language_code == lang]

        # Try manual first, then generated
        for t in manual + generated:
            segments = _try_fetch(t)
            if segments:
                return segments, t.language_code, t.is_generated

    except (TranscriptsDisabled, NoTranscriptFound):
        pass
    except Exception:
        pass

    # Last resort: direct fetch without listing
    try:
        languages = [lang] if lang else None
        transcript = api.fetch(video_id, languages=languages)
        segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in transcript]
        # Can't determine language info reliably here
        return segments, lang or "unknown", False
    except Exception:
        pass

    raise RuntimeError(f"No transcript found for video {video_id}")


def _get_available_languages(video_id: str) -> list[dict]:
    """List available transcript languages."""
    api = _get_yt_api()
    try:
        transcript_list = api.list(video_id)
        langs = []
        for t in transcript_list:
            langs.append({
                "language": t.language,
                "language_code": t.language_code,
                "is_generated": t.is_generated,
            })
        return langs
    except Exception:
        return []


def _get_transcript_with_meta(video_id: str, lang: str | None = None) -> dict:
    """Get transcript segments + language metadata as dict."""
    segments, language_code, is_generated = _get_transcript(video_id, lang)
    return {
        "segments": segments,
        "language": language_code,
        "is_generated": is_generated,
    }


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("tube-bridge")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="youtube_search",
            description="Search YouTube videos by query. Returns title, URL, duration, views, channel. No API key needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10, max 50)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="youtube_get_video_info",
            description="Get detailed metadata for a YouTube video: title, duration, views, channel, description, tags, categories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="youtube_get_trending",
            description="Get currently trending YouTube videos. Optionally filter by category (music, gaming, news, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 10, max 30)",
                        "default": 10,
                    },
                },
            },
        ),
        Tool(
            name="youtube_get_channel_videos",
            description="Get recent uploads from a YouTube channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_url": {
                        "type": "string",
                        "description": "YouTube channel URL or @handle",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max videos (default 10, max 50)",
                        "default": 10,
                    },
                },
                "required": ["channel_url"],
            },
        ),
        Tool(
            name="youtube_get_playlist",
            description="Get all videos in a YouTube playlist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "playlist_url": {
                        "type": "string",
                        "description": "YouTube playlist URL",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max videos (default 20, max 100)",
                        "default": 20,
                    },
                },
                "required": ["playlist_url"],
            },
        ),
        Tool(
            name="youtube_get_transcript",
            description="Get the transcript/subtitles of a YouTube video. Returns plain text by default, or timestamped lines [MM:SS] when with_timestamps=true. Prioritizes manual subtitles over auto-generated (ASR).",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                    "lang": {
                        "type": "string",
                        "description": "Language code (e.g., 'en', 'ru', 'de'). Auto-detect if not specified.",
                    },
                    "with_timestamps": {
                        "type": "boolean",
                        "description": "Include [MM:SS] timestamps per line. Default: false (plain text).",
                        "default": False,
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="youtube_get_available_languages",
            description="List available subtitle/transcript languages for a video. Shows which are auto-generated vs manual.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="youtube_get_comments",
            description="Get comments for a YouTube video. Requires YOUTUBE_API_KEY environment variable (YouTube Data API v3). Returns author, text, likes, and reply count for each top-level comment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "YouTube video URL or ID"},
                    "max_results": {
                        "type": "integer",
                        "description": "Max comments (default 20, max 100)",
                        "default": 20,
                    },
                },
                "required": ["url"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
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
            text=json.dumps({"error": f"Unexpected error: {e}", "hint": "Check that the URL/ID is valid and the video is accessible."}, ensure_ascii=False),
        )]


async def _handle_tool(name: str, args: dict) -> Any:
    match name:
        case "youtube_search":
            return await _search(args["query"], args.get("limit", 10))

        case "youtube_get_video_info":
            video_id = _extract_video_id(args["url"])
            return await _video_info(video_id)

        case "youtube_get_trending":
            return await _trending(args.get("limit", 10))

        case "youtube_get_channel_videos":
            return await _channel_videos(args["channel_url"], args.get("limit", 10))

        case "youtube_get_playlist":
            return await _playlist(args["playlist_url"], args.get("limit", 20))

        case "youtube_get_transcript":
            video_id = _extract_video_id(args["url"])
            return await _transcript(video_id, args.get("lang"), args.get("with_timestamps", False))

        case "youtube_get_available_languages":
            video_id = _extract_video_id(args["url"])
            return await _available_languages(video_id)

        case "youtube_get_comments":
            video_id = _extract_video_id(args["url"])
            return await _comments(video_id, args.get("max_results", 20))

        case _:
            raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _search(query: str, limit: int) -> dict:
    """Search YouTube using yt-dlp's built-in search."""
    limit = min(limit, 50)
    items = _run_ytdlp_multi([
        f"ytsearch{limit}:{query}",
        "--dump-json",
        "--flat-playlist",
        "--extractor-args", "youtube:max_comments=0",
    ], timeout=60)

    videos = []
    for data in items:
        vid = data.get("id", "")
        videos.append({
            "id": vid,
            "title": data.get("title", ""),
            "url": f"https://youtube.com/watch?v={vid}",
            "duration": data.get("duration"),
            "view_count": data.get("view_count"),
            "channel": data.get("channel") or data.get("uploader"),
            "channel_url": data.get("channel_url") or data.get("uploader_url"),
            "upload_date": data.get("upload_date"),
        })

    return {
        "query": query,
        "total_results": len(videos),
        "videos": videos,
    }


async def _video_info(video_id: str) -> dict:
    """Get rich metadata for a video."""
    url = f"https://youtube.com/watch?v={video_id}"
    data = _run_ytdlp([
        url,
        "--dump-json",
        "--extractor-args", "youtube:max_comments=0",
    ], timeout=30)

    if not data:
        raise RuntimeError(f"Could not fetch info for video {video_id}")

    info = _parse_video_info(data)
    return info.to_dict()


async def _trending(limit: int) -> dict:
    """Get trending videos (geo-dependent based on server IP)."""
    limit = min(limit, 30)
    # Use YouTube's trending results page
    items = _run_ytdlp_multi([
        "https://www.youtube.com/results?search_query=trending&sp=CAMSBAgEEAE%253D",
        "--dump-json",
        "--flat-playlist",
        "--playlist-end", str(limit),
    ], timeout=45)

    videos = []
    for data in items:
        vid = data.get("id", "")
        videos.append({
            "id": vid,
            "title": data.get("title", ""),
            "url": f"https://youtube.com/watch?v={vid}",
            "duration": data.get("duration"),
            "view_count": data.get("view_count"),
            "channel": data.get("channel") or data.get("uploader"),
        })

    return {
        "source": "YouTube Trending",
        "total_results": len(videos),
        "videos": videos,
    }


async def _channel_videos(channel_url: str, limit: int) -> dict:
    """Get recent videos from a channel."""
    limit = min(limit, 50)

    # Handle @handle format
    if not channel_url.startswith("http"):
        if channel_url.startswith("@"):
            channel_url = f"https://youtube.com/{channel_url}"
        else:
            channel_url = f"https://youtube.com/@{channel_url}"

    items = _run_ytdlp_multi([
        f"{channel_url}/videos",
        "--dump-json",
        "--flat-playlist",
        "--playlist-end", str(limit),
    ], timeout=45)

    videos = []
    channel_name = ""
    for data in items:
        vid = data.get("id", "")
        if not channel_name:
            channel_name = data.get("channel") or data.get("uploader") or ""
        videos.append({
            "id": vid,
            "title": data.get("title", ""),
            "url": f"https://youtube.com/watch?v={vid}",
            "duration": data.get("duration"),
            "view_count": data.get("view_count"),
            "upload_date": data.get("upload_date"),
        })

    return {
        "channel": channel_name,
        "channel_url": channel_url,
        "total_videos": len(videos),
        "videos": videos,
    }


async def _playlist(playlist_url: str, limit: int) -> dict:
    """Get videos in a playlist."""
    limit = min(limit, 100)
    items = _run_ytdlp_multi([
        playlist_url,
        "--dump-json",
        "--flat-playlist",
        "--playlist-end", str(limit),
    ], timeout=60)

    videos = []
    playlist_title = ""
    for data in items:
        vid = data.get("id", "")
        if not playlist_title:
            playlist_title = data.get("playlist_title") or data.get("title") or ""
        videos.append({
            "id": vid,
            "title": data.get("title", ""),
            "url": f"https://youtube.com/watch?v={vid}",
            "duration": data.get("duration"),
            "channel": data.get("channel") or data.get("uploader"),
        })

    return {
        "playlist_title": playlist_title,
        "playlist_url": playlist_url,
        "total_videos": len(videos),
        "videos": videos,
    }


async def _transcript(video_id: str, lang: str | None, with_timestamps: bool = False) -> dict:
    """Get transcript — plain text or with [MM:SS] timestamps."""
    result = await asyncio.to_thread(_get_transcript_with_meta, video_id, lang)
    segments = result["segments"]

    if with_timestamps:
        lines = []
        for s in segments:
            start = s["start"]
            minutes = int(start // 60)
            seconds = int(start % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            text = s["text"].strip().replace("\n", " ")
            lines.append(f"{timestamp} {text}")
        output = "\n".join(lines)
    else:
        output = " ".join(s["text"] for s in segments)

    return {
        "video_id": video_id,
        "language": result["language"],
        "is_generated": result["is_generated"],
        "segment_count": len(segments),
        "with_timestamps": with_timestamps,
        "text": output,
    }


async def _available_languages(video_id: str) -> dict:
    """List available transcript languages."""
    langs = await asyncio.to_thread(_get_available_languages, video_id)
    return {
        "video_id": video_id,
        "total_languages": len(langs),
        "languages": langs,
    }


async def _comments(video_id: str, max_results: int) -> dict:
    """Get video comments via YouTube Data API v3."""
    comments = await asyncio.to_thread(_get_comments_api, video_id, max_results)
    return {
        "video_id": video_id,
        "total_comments": len(comments),
        "comments": comments,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main():
    """Run the MCP server via stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
