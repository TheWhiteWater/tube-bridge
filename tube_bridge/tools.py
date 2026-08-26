"""tube-bridge — tool implementations (search, transcripts, discovery, comments)."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import functools
import hashlib
import json

from . import cache
from .errors import QuotaExceededError, TubeBridgeError
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
        except QuotaExceededError:
            pass

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

    if stderr and not videos:
        raise yt.ytdlp_failure(f"Could not search YouTube for {query!r}", stderr)
    return {
        "query": query,
        "source": "yt-dlp (anonymous)",
        "total_results": len(videos),
        "videos": videos,
    }


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
        except QuotaExceededError:
            pass

    # Fallback: yt-dlp
    url = f"https://youtube.com/watch?v={video_id}"
    data, stderr = yt.run_ytdlp([
        url, "--dump-json",
        "--extractor-args", "youtube:max_comments=0",
    ], timeout=30)

    if not data:
        raise yt.ytdlp_failure(
            f"Could not fetch info for video {video_id}", stderr
        )

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
        except QuotaExceededError:
            pass

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

    if stderr and not videos:
        raise yt.ytdlp_failure("Could not fetch YouTube trending videos", stderr)
    return {
        "source": "yt-dlp (trending page)",
        "total_results": len(videos),
        "videos": videos,
    }


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

    if stderr and not videos:
        raise yt.ytdlp_failure(
            f"Could not fetch videos for channel {channel_url}", stderr
        )
    result = {
        "channel": channel_name,
        "channel_url": channel_url,
        "total_videos": len(videos),
        "videos": videos,
    }
    if not videos:
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

    if stderr and not videos:
        raise yt.ytdlp_failure(f"Could not fetch playlist {playlist_url}", stderr)
    return {
        "playlist_title": playlist_title,
        "playlist_url": playlist_url,
        "total_videos": len(videos),
        "videos": videos,
    }


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


# ---------------------------------------------------------------------------
# User-filled research artifact preview
# ---------------------------------------------------------------------------


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _source_ms(seconds: object) -> int:
    value = Decimal(str(seconds or 0)) * Decimal(1000)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _transcript_machine_fields(
    video_id: str, requested_language: str | None, result: dict
) -> tuple[dict, list[dict]]:
    track_kind = "generated" if result["is_generated"] else "manual"
    source_segments = []
    envelope_segments = []
    for ordinal, segment in enumerate(result["segments"]):
        start_ms = _source_ms(segment.get("start", 0))
        end_ms = _source_ms(
            Decimal(str(segment.get("start", 0)))
            + Decimal(str(segment.get("duration", 0)))
        )
        text = str(segment.get("text", ""))
        envelope_segments.append(
            {
                "ordinal": ordinal,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text,
            }
        )
    envelope = {
        "schema": "tube-bridge.transcript-source.v2",
        "video_id": video_id,
        "selected_language": result["language"],
        "track_kind": track_kind,
        "segments": envelope_segments,
    }
    source_sha256 = hashlib.sha256(_canonical_json_bytes(envelope)).hexdigest()
    for segment in envelope_segments:
        source_segments.append(
            {
                "segment_id": (
                    f"seg_{source_sha256}_{segment['ordinal']:08d}"
                ),
                **segment,
            }
        )
    transcript = {
        "status": "ready",
        "transcript_version_id": f"trv_{source_sha256}",
        "source_sha256": source_sha256,
        "source_envelope": envelope,
        "requested_language": requested_language,
        "selected_language": result["language"],
        "track_kind": track_kind,
        "provider": "youtube-transcript-api",
        "segment_count": len(source_segments),
        "first_segment_id": source_segments[0]["segment_id"] if source_segments else None,
        "last_segment_id": source_segments[-1]["segment_id"] if source_segments else None,
        "start_ms": source_segments[0]["start_ms"] if source_segments else None,
        "end_ms": source_segments[-1]["end_ms"] if source_segments else None,
        "error": None,
    }
    return transcript, source_segments


def _safe_error_fields(error: TubeBridgeError) -> dict:
    return {
        "code": error.code.value,
        "source": error.source.value,
        "retryable": error.retryable,
    }


def _channel_context_sync(info: dict) -> dict:
    observed_at = datetime.now(timezone.utc).isoformat()
    channel_id = info.get("channel_id")
    channel_name = info.get("channel")
    channel_url = info.get("channel_url") or (
        f"https://youtube.com/channel/{channel_id}" if channel_id else None
    )
    api_error: TubeBridgeError | None = None
    if api.get_api_key() and channel_id:
        try:
            observed = api.channel_info(channel_id)
            return {
                "status": "ready",
                "channel_id": observed.get("channel_id") or channel_id,
                "title": observed.get("title") or channel_name,
                "description": observed.get("description"),
                "canonical_url": channel_url,
                "country": observed.get("country") or None,
                "provider": "youtube-data-api",
                "retrieval_mode": "live",
                "observed_at": observed_at,
                "warning": None,
            }
        except TubeBridgeError as error:
            api_error = error

    if channel_id or channel_url:
        try:
            observed = yt.channel_metadata(channel_id, channel_url)
            return {
                "status": "ready",
                "channel_id": observed.get("channel_id") or channel_id,
                "title": observed.get("title") or channel_name,
                "description": observed.get("description"),
                "description_truncated": bool(
                    observed.get("description_truncated", False)
                ),
                "canonical_url": observed.get("canonical_url") or channel_url,
                "country": observed.get("country"),
                "provider": "yt-dlp",
                "retrieval_mode": "fallback" if api_error else "live",
                "observed_at": observed_at,
                "warning": _safe_error_fields(api_error) if api_error else None,
            }
        except TubeBridgeError as error:
            final_error = error
    elif api_error:
        final_error = api_error
    else:
        final_error = None

    return {
        "status": "unavailable",
        "channel_id": channel_id,
        "title": channel_name,
        "description": None,
        "canonical_url": channel_url,
        "country": None,
        "provider": "video-metadata-fallback",
        "retrieval_mode": "fallback",
        "observed_at": observed_at,
        "warning": _safe_error_fields(final_error) if final_error else None,
    }


def _video_machine_fields(video_id: str, info: dict) -> dict:
    cached = bool(info.get("cached"))
    return {
        "video_id": video_id,
        "canonical_url": info.get("url")
        or f"https://youtube.com/watch?v={video_id}",
        "title": info.get("title") or "",
        "description": info.get("description"),
        "duration_seconds": info.get("duration"),
        "published_at": info.get("upload_date") or info.get("published_at"),
        "language_hint": info.get("language"),
        "channel_id": info.get("channel_id"),
        "channel_name": info.get("channel"),
        "channel_url": info.get("channel_url"),
        "provider": info.get("source") or (
            "unknown-cached-origin" if cached else "yt-dlp"
        ),
        "retrieval_mode": "cache" if cached else "live",
    }


async def research_templates() -> dict:
    from . import research_artifacts

    return await asyncio.to_thread(research_artifacts.list_templates)


async def research_scaffold_create(template_id: str, target: dict) -> dict:
    """Create a machine-prefilled scaffold; never fill research semantics."""
    from . import corpus, research_artifacts

    target_type = target.get("type") if isinstance(target, dict) else None
    if template_id == "structured-source-v1" and target_type == "video":
        video_id = yt.extract_video_id(target.get("video_id", ""))
        requested_language = target.get("language")
        info = await video_info(video_id)
        channel = await asyncio.to_thread(_channel_context_sync, info)
        try:
            transcript_result = await asyncio.to_thread(
                _get_transcript_with_meta, video_id, requested_language
            )
            transcript_fields, source_segments = _transcript_machine_fields(
                video_id, requested_language, transcript_result
            )
        except TubeBridgeError as error:
            transcript_fields = {
                "status": "unavailable",
                "transcript_version_id": None,
                "source_sha256": None,
                "source_envelope": None,
                "requested_language": requested_language,
                "selected_language": None,
                "track_kind": None,
                "provider": error.source.value,
                "segment_count": 0,
                "first_segment_id": None,
                "last_segment_id": None,
                "start_ms": None,
                "end_ms": None,
                "error": _safe_error_fields(error),
            }
            source_segments = []
        machine_fields = {
            "target": {"type": "video", "video_id": video_id},
            "video_metadata": _video_machine_fields(video_id, info),
            "channel_metadata": channel,
            "transcript": transcript_fields,
            "source_segments": source_segments,
        }
        return await asyncio.to_thread(
            research_artifacts.create_artifact,
            template_id,
            "video",
            video_id,
            machine_fields,
        )

    if template_id == "corpus-study-v1" and target_type == "corpus":
        corpus_id = target.get("corpus_id", "")
        snapshot = await asyncio.to_thread(corpus.corpus_snapshot, corpus_id)
        sources = []
        for source in snapshot.get("sources", []):
            video_id = source["video_id"]
            cached_info = await asyncio.to_thread(cache.get_video_info, video_id)
            cached_transcript = await asyncio.to_thread(
                cache.get_transcript, video_id, None
            )
            info = cached_info if isinstance(cached_info, dict) else {}
            sources.append(
                {
                    "video_id": video_id,
                    "canonical_url": f"https://youtube.com/watch?v={video_id}",
                    "title": info.get("title") or source.get("title"),
                    "description": info.get("description"),
                    "channel_id": info.get("channel_id"),
                    "channel_name": info.get("channel"),
                    "channel_url": info.get("channel_url"),
                    "metadata_retrieval_mode": "cache" if cached_info else "unavailable",
                    "transcript_status": "ready" if cached_transcript else "unknown",
                    "selected_language": (
                        cached_transcript.get("language") if cached_transcript else None
                    ),
                    "track_kind": (
                        "generated"
                        if cached_transcript and cached_transcript.get("is_generated")
                        else "manual" if cached_transcript else None
                    ),
                    "added_at": source.get("added_at"),
                }
            )
        snapshot_summary = {
            key: value for key, value in snapshot.items() if key != "sources"
        }
        snapshot_summary["source_count"] = len(sources)
        machine_fields = {
            "target": {"type": "corpus", "corpus_id": corpus_id},
            "corpus_snapshot": snapshot_summary,
            "sources": sources,
            "retrieval_summary": {
                "metadata_unavailable_video_ids": [
                    item["video_id"]
                    for item in sources
                    if item["metadata_retrieval_mode"] == "unavailable"
                ],
                "transcript_unknown_video_ids": [
                    item["video_id"]
                    for item in sources
                    if item["transcript_status"] != "ready"
                ],
            },
        }
        return await asyncio.to_thread(
            research_artifacts.create_artifact,
            template_id,
            "corpus",
            corpus_id,
            machine_fields,
        )

    raise ValueError(
        f"Template {template_id!r} does not support target type {target_type!r}"
    )


async def research_artifact_get(
    artifact_id: str, revision: int | None = None
) -> dict:
    from . import research_artifacts

    return await asyncio.to_thread(
        research_artifacts.get_artifact, artifact_id, revision
    )


async def research_artifact_save(
    artifact_id: str,
    expected_revision: int,
    agent_fields: dict,
    author: dict | None,
) -> dict:
    from . import research_artifacts

    return await asyncio.to_thread(
        research_artifacts.save_artifact,
        artifact_id,
        expected_revision,
        agent_fields,
        author,
    )


async def research_artifacts_list(
    target_type: str, target_id: str, template_id: str | None = None
) -> dict:
    from . import research_artifacts

    return await asyncio.to_thread(
        research_artifacts.list_artifacts,
        target_type,
        target_id,
        template_id,
    )


async def research_artifact_export(artifact_id: str, format: str) -> dict:
    from . import research_artifacts

    return await asyncio.to_thread(
        research_artifacts.export_artifact, artifact_id, format
    )
