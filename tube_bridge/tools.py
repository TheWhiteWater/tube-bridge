"""tube-bridge — tool implementations (search, transcripts, discovery, comments)."""

import asyncio
import functools

from . import cache
from .youtube import client as yt
from .youtube import api, frame as frame_extractor, transcript as tr


MAX_FRAME_JPEG_BYTES = 1_500_000


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


async def search(query: str, limit: int, args: dict) -> dict:
    """Search YouTube — Data API v3 primary when key present, yt-dlp as fallback."""
    has_api = bool(api.get_api_key())

    if has_api:
        filters = {k: v for k, v in args.items()
                   if k in ("order", "published_after", "published_before", "channel_id", "video_duration", "video_definition", "safe_search")
                   and v is not None}
        try:
            return await asyncio.to_thread(api.search_videos, query, limit, **filters)
        except RuntimeError as e:
            if "QUOTA_EXCEEDED" in str(e):
                pass
            else:
                raise

    limit = min(limit, 50)
    items, stderr = yt.run_ytdlp_multi([
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
    return result


async def search_channels(query: str, limit: int, args: dict) -> dict:
    """Search YouTube channels via Data API v3."""
    filters = {k: v for k, v in args.items()
               if k in ("min_subscribers", "max_subscribers", "order")
               and v is not None}
    return await asyncio.to_thread(api.search_channels, query, limit, **filters)


# ---------------------------------------------------------------------------
# Video info (cached, dual-source: API v3 → yt-dlp fallback)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=64)
def _video_info_cached(video_id: str) -> dict:
    # Check persistent cache first
    cached = cache.get_video_info(video_id)
    if cached:
        return cached

    # Try Data API v3 first (avoids datacenter IP bot detection)
    if api.get_api_key():
        try:
            result = api.get_video_info(video_id)
            cache.set_video_info(video_id, result)
            return result
        except RuntimeError as e:
            if "QUOTA_EXCEEDED" in str(e):
                pass
            else:
                raise

    # Fallback: yt-dlp
    url = f"https://youtube.com/watch?v={video_id}"
    data, stderr = yt.run_ytdlp([
        url, "--dump-json",
        "--extractor-args", "youtube:max_comments=0",
    ], timeout=30)

    if not data:
        raise RuntimeError(f"Could not fetch info for video {video_id}" + (f": {stderr}" if stderr else ""))

    info = yt.parse_video_info(data)
    result = info.to_dict()
    if stderr:
        result["_ytdlp_stderr"] = stderr
    cache.set_video_info(video_id, result)
    return result


async def video_info(video_id: str) -> dict:
    """Get rich metadata for a video (cached)."""
    return await asyncio.to_thread(_video_info_cached, video_id)


# ---------------------------------------------------------------------------
# Trending
# ---------------------------------------------------------------------------


async def trending(limit: int) -> dict:
    return await asyncio.to_thread(_trending_sync, limit)


def _trending_sync(limit: int) -> dict:
    limit = min(limit, 30)

    if api.get_api_key():
        try:
            return api.get_trending(limit)
        except RuntimeError as e:
            if "QUOTA_EXCEEDED" not in str(e):
                raise

    items, stderr = yt.run_ytdlp_multi([
        "https://www.youtube.com/results?search_query=trending&sp=CAMSBAgEEAE%253D",
        "--dump-json", "--flat-playlist", "--playlist-end", str(limit),
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


# ---------------------------------------------------------------------------
# Channel videos
# ---------------------------------------------------------------------------


async def channel_videos(channel_url: str, limit: int) -> dict:
    return await asyncio.to_thread(_channel_videos_sync, channel_url, limit)


def _channel_videos_sync(channel_url: str, limit: int) -> dict:
    limit = min(limit, 50)

    if not channel_url.startswith("http"):
        if channel_url.startswith("@"):
            channel_url = f"https://youtube.com/{channel_url}"
        else:
            channel_url = f"https://youtube.com/@{channel_url}"

    items, stderr = yt.run_ytdlp_multi([
        f"{channel_url}/videos",
        "--dump-json", "--flat-playlist", "--playlist-end", str(limit),
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


# ---------------------------------------------------------------------------
# Playlist
# ---------------------------------------------------------------------------


async def playlist(playlist_url: str, limit: int) -> dict:
    return await asyncio.to_thread(_playlist_sync, playlist_url, limit)


def _playlist_sync(playlist_url: str, limit: int) -> dict:
    limit = min(limit, 100)
    items, stderr = yt.run_ytdlp_multi([
        playlist_url,
        "--dump-json", "--flat-playlist", "--playlist-end", str(limit),
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


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=32)
def _get_transcript_cached(video_id: str, lang: str | None = None):
    """Get transcript — persistent cache → live fetch → cache."""
    cached = cache.get_transcript(video_id, lang)
    if cached:
        return cached["segments"], cached["language"], cached["is_generated"]

    segments, language_code, is_generated = tr.get_transcript(video_id, lang)
    cache.set_transcript(video_id, lang, segments, language_code, is_generated)
    return segments, language_code, is_generated


def _get_transcript_with_meta(video_id: str, lang: str | None = None) -> dict:
    segments, language_code, is_generated = _get_transcript_cached(video_id, lang)
    return {"segments": segments, "language": language_code, "is_generated": is_generated}


async def transcript(video_id: str, lang: str | None, with_timestamps: bool = False) -> dict:
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


async def available_languages(video_id: str) -> dict:
    langs = await asyncio.to_thread(tr.get_available_languages, video_id)
    return {
        "video_id": video_id,
        "total_languages": len(langs),
        "languages": langs,
    }


async def video_frame(video_id: str, timestamp_ms: int, max_width: int = 640):
    """Return one ephemeral frame artifact for MCP ImageContent serialization."""
    if isinstance(max_width, bool) or not isinstance(max_width, int):
        raise ValueError("max_width must be an integer")
    if not 64 <= max_width <= 1280:
        raise ValueError("max_width must be between 64 and 1280")
    artifact = await asyncio.to_thread(
        frame_extractor.extract_frame,
        video_id,
        timestamp_ms=timestamp_ms,
        max_width=max_width,
    )
    if len(artifact.data) > MAX_FRAME_JPEG_BYTES:
        raise RuntimeError(
            f"Frame exceeds {MAX_FRAME_JPEG_BYTES}-byte response limit"
        )
    return artifact


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


async def comments(video_id: str, max_results: int) -> dict:
    result = await asyncio.to_thread(api.get_comments, video_id, max_results)
    return {
        "video_id": video_id,
        "total_comments": len(result),
        "comments": result,
    }


# ---------------------------------------------------------------------------
# Channel info (API-powered)
# ---------------------------------------------------------------------------


async def channel_info(channel_id: str) -> dict:
    return await asyncio.to_thread(api.channel_info, channel_id)


# ---------------------------------------------------------------------------
# Bridge Corpus — semantic search over transcripts
# ---------------------------------------------------------------------------


async def corpus_create(corpus_id: str, label: str | None = None) -> dict:
    from . import corpus
    return await asyncio.to_thread(corpus.corpus_create, corpus_id, label)


async def corpus_add(corpus_id: str, video_id: str, force_reembed: bool = False) -> dict:
    """Add a transcript plus cache-only title metadata to a corpus."""
    result = await asyncio.to_thread(_get_transcript_with_meta, video_id, None)
    segments = result["segments"]
    try:
        cached_info = await asyncio.to_thread(cache.get_video_info, video_id)
    except Exception:
        cached_info = None
    title = cached_info.get("title") if isinstance(cached_info, dict) else None
    from . import corpus
    return await asyncio.to_thread(
        corpus.corpus_add,
        corpus_id,
        video_id,
        segments,
        force_reembed,
        title,
    )


async def corpus_search(corpus_id: str, query: str, top_k: int = 10) -> dict:
    from . import corpus
    return await asyncio.to_thread(corpus.corpus_search, corpus_id, query, top_k)


async def corpus_list() -> dict:
    from . import corpus
    return await asyncio.to_thread(corpus.corpus_list)


async def corpus_delete(corpus_id: str) -> dict:
    from . import corpus
    return await asyncio.to_thread(corpus.corpus_delete, corpus_id)
