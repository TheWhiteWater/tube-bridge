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
import functools
import json
import os
import re
import subprocess
import sys
import time
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


def _run_ytdlp(args: list[str], timeout: int = 60, retries: int = 2) -> tuple[dict | None, str]:
    """Run yt-dlp --dump-json. Returns (data, stderr_info). Retries on transient failures."""
    last_stderr = ""
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["yt-dlp", "--no-warnings", "--no-playlist", *args],
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode != 0:
                last_stderr = result.stderr.strip()[-500:]
                if attempt < retries:
                    time.sleep(1.5 ** attempt)
                    continue
                return None, last_stderr
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if not lines:
                return None, "yt-dlp returned empty output"
            data = json.loads(lines[0])
            return data, ""
        except subprocess.TimeoutExpired:
            last_stderr = f"yt-dlp timed out after {timeout}s"
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            return None, last_stderr
        except Exception as e:
            last_stderr = str(e)[-500:]
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            return None, last_stderr
    return None, last_stderr


def _run_ytdlp_multi(args: list[str], timeout: int = 60, retries: int = 2) -> tuple[list[dict], str]:
    """Run yt-dlp --dump-json (multi-line). Returns (items, stderr_info). Retries on transient failures."""
    last_stderr = ""
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ["yt-dlp", "--no-warnings", *args],
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode != 0:
                last_stderr = result.stderr.strip()[-500:]
                if attempt < retries:
                    time.sleep(1.5 ** attempt)
                    continue
                return [], last_stderr
            items = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return items, ""
        except subprocess.TimeoutExpired:
            last_stderr = f"yt-dlp timed out after {timeout}s"
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            return [], last_stderr
        except Exception as e:
            last_stderr = str(e)[-500:]
            if attempt < retries:
                time.sleep(1.5 ** attempt)
                continue
            return [], last_stderr
    return [], last_stderr


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
    """Make a YouTube Data API v3 request. Raises RuntimeError with specific error codes."""
    key = _api_key()
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not set. Set it to enable API-powered features.")
    params["key"] = key
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if "error" in data:
                err = data["error"]
                code = err.get("code", 0)
                reason = err.get("errors", [{}])[0].get("reason", "")
                if code == 403 and reason == "quotaExceeded":
                    raise RuntimeError("QUOTA_EXCEEDED: YouTube Data API daily quota exhausted. Try again tomorrow or use yt-dlp fallback for search.")
                raise RuntimeError(f"API_ERROR_{code}: {err.get('message', str(err))}")
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if "quotaExceeded" in body:
            raise RuntimeError("QUOTA_EXCEEDED: YouTube Data API daily quota exhausted.")
        raise RuntimeError(f"HTTP_{e.code}: {body[:200]}")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"NETWORK_ERROR: {e}")


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


def _search_videos_api(query: str, max_results: int = 10, **filters) -> dict:
    """Search videos via Data API v3 with rich filters."""
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": min(max_results, 50),
        "type": "video",
    }
    # Rich filters (inspired by ZubeidHendricks + our own)
    if filters.get("order"):
        params["order"] = filters["order"]  # date, rating, relevance, viewCount
    if filters.get("published_after"):
        params["publishedAfter"] = filters["published_after"]  # ISO 8601
    if filters.get("published_before"):
        params["publishedBefore"] = filters["published_before"]
    if filters.get("channel_id"):
        params["channelId"] = filters["channel_id"]
    if filters.get("video_duration"):
        params["videoDuration"] = filters["video_duration"]  # short, medium, long
    if filters.get("video_definition"):
        params["videoDefinition"] = filters["video_definition"]  # high, standard
    if filters.get("safe_search"):
        params["safeSearch"] = filters["safe_search"]

    data = _api_call("search", params)
    videos = []
    for item in data.get("items", []):
        vid = item["id"]["videoId"]
        sn = item.get("snippet", {})
        videos.append({
            "id": vid,
            "title": sn.get("title", ""),
            "url": f"https://youtube.com/watch?v={vid}",
            "channel": sn.get("channelTitle", ""),
            "channel_id": sn.get("channelId", ""),
            "published_at": sn.get("publishedAt", ""),
            "description": (sn.get("description", "") or "")[:200],
            "thumbnail": sn.get("thumbnails", {}).get("default", {}).get("url"),
        })
    return {
        "query": query,
        "source": "YouTube Data API v3",
        "total_results": len(videos),
        "next_page_token": data.get("nextPageToken"),
        "videos": videos,
    }


def _search_channels_api(query: str, max_results: int = 10, **filters) -> dict:
    """Search YouTube channels via Data API v3."""
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": min(max_results, 50),
        "type": "channel",
    }
    if filters.get("order"):
        params["order"] = filters["order"]

    data = _api_call("search", params)
    channels = []
    channel_ids = []
    for item in data.get("items", []):
        cid = item["id"]["channelId"]
        channel_ids.append(cid)
        sn = item.get("snippet", {})
        channels.append({
            "channel_id": cid,
            "title": sn.get("title", ""),
            "description": (sn.get("description", "") or "")[:200],
            "published_at": sn.get("publishedAt", ""),
            "thumbnail": sn.get("thumbnails", {}).get("default", {}).get("url"),
        })

    # Enrich with subscriber counts from channels.list
    if channel_ids and _api_key():
        try:
            stats = _api_call("channels", {
                "part": "statistics,snippet",
                "id": ",".join(channel_ids[:50]),
            })
            stat_map = {}
            for ch in stats.get("items", []):
                stat_map[ch["id"]] = {
                    "subscriber_count": int(ch.get("statistics", {}).get("subscriberCount", 0)),
                    "video_count": int(ch.get("statistics", {}).get("videoCount", 0)),
                    "view_count": int(ch.get("statistics", {}).get("viewCount", 0)),
                    "country": ch.get("snippet", {}).get("country"),
                }
            for ch in channels:
                ch.update(stat_map.get(ch["channel_id"], {}))
        except Exception:
            pass

    # Apply subscriber filters
    if filters.get("min_subscribers"):
        min_subs = int(filters["min_subscribers"])
        channels = [c for c in channels if c.get("subscriber_count", 0) >= min_subs]
    if filters.get("max_subscribers"):
        max_subs = int(filters["max_subscribers"])
        channels = [c for c in channels if c.get("subscriber_count", 0) <= max_subs]

    return {
        "query": query,
        "source": "YouTube Data API v3",
        "total_results": len(channels),
        "channels": channels,
    }


def _channel_info_api(channel_id: str) -> dict:
    """Get detailed channel info via Data API v3."""
    data = _api_call("channels", {
        "part": "snippet,statistics,brandingSettings",
        "id": channel_id,
    })
    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"Channel not found: {channel_id}")
    ch = items[0]
    sn = ch.get("snippet", {})
    st = ch.get("statistics", {})
    br = ch.get("brandingSettings", {}).get("channel", {})
    return {
        "channel_id": ch["id"],
        "title": sn.get("title", ""),
        "description": sn.get("description", ""),
        "custom_url": sn.get("customUrl", ""),
        "published_at": sn.get("publishedAt", ""),
        "country": sn.get("country", ""),
        "thumbnail": sn.get("thumbnails", {}).get("default", {}).get("url"),
        "subscriber_count": int(st.get("subscriberCount", 0)),
        "video_count": int(st.get("videoCount", 0)),
        "view_count": int(st.get("viewCount", 0)),
        "keywords": br.get("keywords", ""),
    }


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
            description="Search YouTube videos. Uses Data API v3 with rich filters when YOUTUBE_API_KEY is set, falls back to yt-dlp (no key needed). Filters: date range, channel, duration, order, safe_search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (default 10, max 50)", "default": 10},
                    "order": {"type": "string", "description": "Sort order: date, rating, relevance, viewCount, title (API only)"},
                    "published_after": {"type": "string", "description": "Only videos published after this ISO 8601 date (API only)"},
                    "published_before": {"type": "string", "description": "Only videos published before this ISO 8601 date (API only)"},
                    "channel_id": {"type": "string", "description": "Restrict to a specific channel ID (API only)"},
                    "video_duration": {"type": "string", "description": "Filter by duration: short (<4min), medium (4-20min), long (>20min) (API only)"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="youtube_search_channels",
            description="Search YouTube channels by name or topic. Returns subscriber counts, video counts, country. Requires YOUTUBE_API_KEY.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Channel name or topic to search"},
                    "limit": {"type": "integer", "description": "Max results (default 10, max 50)", "default": 10},
                    "min_subscribers": {"type": "integer", "description": "Minimum subscriber count filter"},
                    "max_subscribers": {"type": "integer", "description": "Maximum subscriber count filter"},
                    "order": {"type": "string", "description": "Sort: relevance, date"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="youtube_get_channel_info",
            description="Get detailed channel metadata: subscriber count, total views, video count, country, keywords, description. Requires YOUTUBE_API_KEY.",
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
            return await _search(args["query"], args.get("limit", 10), args)

        case "youtube_search_channels":
            return await _search_channels_tool(args["query"], args.get("limit", 10), args)

        case "youtube_get_channel_info":
            return await _channel_info_tool(args["channel_id"])

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


async def _search(query: str, limit: int, args: dict) -> dict:
    """Search YouTube — uses Data API v3 when key is present, yt-dlp as fallback."""
    # Check if API key is available and rich filters requested
    has_api = bool(_api_key())
    has_filters = any(args.get(k) for k in ["order", "published_after", "published_before", "channel_id", "video_duration"])

    if has_api and has_filters:
        # Use Data API v3 with rich filters
        filters = {k: v for k, v in args.items()
                   if k in ("order", "published_after", "published_before", "channel_id", "video_duration", "video_definition", "safe_search")
                   and v is not None}
        return await asyncio.to_thread(_search_videos_api, query, limit, **filters)

    # Fallback: yt-dlp (works without key, fewer filters)
    limit = min(limit, 50)
    items, stderr = _run_ytdlp_multi([
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

    result = {
        "query": query,
        "source": "yt-dlp (anonymous)",
        "total_results": len(videos),
        "videos": videos,
    }
    if stderr and not videos:
        result["_warning"] = stderr
    if has_api and not has_filters:
        result["_hint"] = "YOUTUBE_API_KEY is set but no rich filters used. Add order/published_after/channel_id for API-powered search."
    return result


async def _search_channels_tool(query: str, limit: int, args: dict) -> dict:
    """Search YouTube channels via Data API v3."""
    filters = {k: v for k, v in args.items()
               if k in ("min_subscribers", "max_subscribers", "order")
               and v is not None}
    return await asyncio.to_thread(_search_channels_api, query, limit, **filters)


async def _channel_info_tool(channel_id: str) -> dict:
    """Get detailed channel info via Data API v3."""
    return await asyncio.to_thread(_channel_info_api, channel_id)


@functools.lru_cache(maxsize=64)
def _video_info_cached(video_id: str) -> dict:
    """Cached version — avoids re-fetching same video metadata."""
    url = f"https://youtube.com/watch?v={video_id}"
    data, stderr = _run_ytdlp([
        url,
        "--dump-json",
        "--extractor-args", "youtube:max_comments=0",
    ], timeout=30)

    if not data:
        raise RuntimeError(f"Could not fetch info for video {video_id}" + (f": {stderr}" if stderr else ""))

    info = _parse_video_info(data)
    result = info.to_dict()
    if stderr:
        result["_ytdlp_stderr"] = stderr
    return result


async def _video_info(video_id: str) -> dict:
    """Get rich metadata for a video (cached)."""
    return await asyncio.to_thread(_video_info_cached, video_id)


async def _trending(limit: int) -> dict:
    """Get trending videos (geo-dependent based on server IP)."""
    return await asyncio.to_thread(_trending_sync, limit)


def _trending_sync(limit: int) -> dict:
    """Get trending videos — Data API v3 when key present, yt-dlp fallback."""
    limit = min(limit, 30)

    # Try Data API v3 first (stable, region-independent)
    if _api_key():
        try:
            data = _api_call("videos", {
                "part": "snippet",
                "chart": "mostPopular",
                "maxResults": limit,
                "regionCode": "US",
            })
            videos = []
            for item in data.get("items", []):
                sn = item.get("snippet", {})
                vid = item["id"]
                videos.append({
                    "id": vid,
                    "title": sn.get("title", ""),
                    "url": f"https://youtube.com/watch?v={vid}",
                    "channel": sn.get("channelTitle", ""),
                    "channel_id": sn.get("channelId", ""),
                    "published_at": sn.get("publishedAt", ""),
                    "thumbnail": sn.get("thumbnails", {}).get("default", {}).get("url"),
                })
            return {
                "source": "YouTube Data API v3 (mostPopular, US)",
                "total_results": len(videos),
                "videos": videos,
            }
        except RuntimeError as e:
            if "QUOTA_EXCEEDED" in str(e):
                pass  # Fall through to yt-dlp
            else:
                raise

    # Fallback: yt-dlp (fragile URL, geo-dependent)
    items, stderr = _run_ytdlp_multi([
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

    result = {
        "source": "yt-dlp (trending page)",
        "total_results": len(videos),
        "videos": videos,
    }
    if stderr and not videos:
        result["_warning"] = stderr
    return result


async def _channel_videos(channel_url: str, limit: int) -> dict:
    """Get recent videos from a channel."""
    return await asyncio.to_thread(_channel_videos_sync, channel_url, limit)


def _channel_videos_sync(channel_url: str, limit: int) -> dict:
    limit = min(limit, 50)

    if not channel_url.startswith("http"):
        if channel_url.startswith("@"):
            channel_url = f"https://youtube.com/{channel_url}"
        else:
            channel_url = f"https://youtube.com/@{channel_url}"

    items, stderr = _run_ytdlp_multi([
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

    result = {
        "channel": channel_name,
        "channel_url": channel_url,
        "total_videos": len(videos),
        "videos": videos,
    }
    if stderr and not videos:
        result["_warning"] = stderr
    elif not videos and not stderr:
        result["_warning"] = "No videos found — channel may not exist or has no uploads"
    return result


async def _playlist(playlist_url: str, limit: int) -> dict:
    """Get videos in a playlist."""
    return await asyncio.to_thread(_playlist_sync, playlist_url, limit)


def _playlist_sync(playlist_url: str, limit: int) -> dict:
    limit = min(limit, 100)
    items, stderr = _run_ytdlp_multi([
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

    result = {
        "playlist_title": playlist_title,
        "playlist_url": playlist_url,
        "total_videos": len(videos),
        "videos": videos,
    }
    if stderr and not videos:
        result["_warning"] = stderr
    return result


@functools.lru_cache(maxsize=32)
def _get_transcript_cached(video_id: str, lang: str | None = None) -> tuple:
    """Cached transcript fetch — avoids re-fetching same video."""
    return _get_transcript(video_id, lang)


def _get_transcript_with_meta_cached(video_id: str, lang: str | None = None) -> dict:
    """Cached transcript + metadata."""
    segments, language_code, is_generated = _get_transcript_cached(video_id, lang)
    return {
        "segments": segments,
        "language": language_code,
        "is_generated": is_generated,
    }


async def _transcript(video_id: str, lang: str | None, with_timestamps: bool = False) -> dict:
    """Get transcript — plain text or with [MM:SS] timestamps."""
    result = await asyncio.to_thread(_get_transcript_with_meta_cached, video_id, lang)
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
