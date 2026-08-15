"""tube-bridge — YouTube Data API v3 client (optional, requires YOUTUBE_API_KEY)."""

import json
import math
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import urllib.error
import urllib.parse
import urllib.request

from ..errors import (
    ErrorSource,
    InvalidArgumentError,
    NotFoundError,
    QuotaExceededError,
    RateLimitedError,
    TubeBridgeError,
    UpstreamUnavailableError,
)


def get_api_key() -> str | None:
    """Get YouTube Data API key from environment."""
    return os.environ.get("YOUTUBE_API_KEY")


_QUOTA_REASONS = {
    "quotaExceeded",
    "dailyLimitExceeded",
    "dailyLimitExceededUnreg",
}
_RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded"}
_TRANSIENT_HTTP_STATUSES = {408, 425, 500, 502, 503, 504}


def _retry_after_seconds(headers) -> int | None:
    raw = headers.get("Retry-After") if headers is not None else None
    if not raw:
        return None
    value = str(raw).strip()
    if value.isdecimal():
        seconds = int(value)
        return seconds if seconds >= 1 else None
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = math.ceil((retry_at - datetime.now(timezone.utc)).total_seconds())
        return seconds if seconds >= 1 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _error_fields(payload: object, default_status: int) -> tuple[int, str, str]:
    if not isinstance(payload, dict):
        return default_status, "", str(payload)
    error = payload.get("error", payload)
    if not isinstance(error, dict):
        return default_status, "", str(error)
    status = error.get("code", default_status)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = default_status
    entries = error.get("errors")
    reason = ""
    if isinstance(entries, list) and entries and isinstance(entries[0], dict):
        reason = str(entries[0].get("reason", ""))
    return status, reason, str(error.get("message", "YouTube Data API request failed"))


def _raise_api_error(
    status: int,
    reason: str,
    message: str,
    *,
    retry_after_seconds: int | None = None,
) -> None:
    if status == 429 or reason in _RATE_LIMIT_REASONS:
        raise RateLimitedError(
            message,
            source=ErrorSource.YOUTUBE_DATA_API,
            retry_after_seconds=retry_after_seconds,
        )
    if reason in _QUOTA_REASONS:
        raise QuotaExceededError(message)
    if status == 404:
        raise NotFoundError(message, source=ErrorSource.YOUTUBE_DATA_API)
    if status == 400:
        raise InvalidArgumentError(message, source=ErrorSource.YOUTUBE_DATA_API)
    retryable = status in _TRANSIENT_HTTP_STATUSES
    raise UpstreamUnavailableError(
        message,
        source=ErrorSource.YOUTUBE_DATA_API,
        retryable=retryable,
        retry_after_seconds=retry_after_seconds if retryable else None,
    )


def api_call(endpoint: str, params: dict) -> dict:
    """Make a typed YouTube Data API v3 request."""
    key = get_api_key()
    if not key:
        raise UpstreamUnavailableError(
            "YOUTUBE_API_KEY not set. Set it to enable API-powered features.",
            source=ErrorSource.YOUTUBE_DATA_API,
            retryable=False,
        )
    params["key"] = key
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if "error" in data:
                status, reason, message = _error_fields(data, 0)
                _raise_api_error(status, reason, message)
            return data
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace") if error.fp else ""
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"error": {"code": error.code, "message": body[:200]}}
        status, reason, message = _error_fields(payload, error.code)
        _raise_api_error(
            status,
            reason,
            message,
            retry_after_seconds=_retry_after_seconds(error.headers),
        )
    except TubeBridgeError:
        raise
    except urllib.error.URLError as error:
        raise UpstreamUnavailableError(
            f"YouTube Data API network error: {error.reason}",
            source=ErrorSource.YOUTUBE_DATA_API,
        ) from error
    except Exception as error:
        raise UpstreamUnavailableError(
            f"YouTube Data API network error: {error}",
            source=ErrorSource.YOUTUBE_DATA_API,
        ) from error


def search_videos(query: str, max_results: int = 10, **filters) -> dict:
    """Search videos via Data API v3 with rich filters."""
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": min(max_results, 50),
        "type": "video",
    }
    if filters.get("order"):
        params["order"] = filters["order"]
    if filters.get("published_after"):
        params["publishedAfter"] = filters["published_after"]
    if filters.get("published_before"):
        params["publishedBefore"] = filters["published_before"]
    if filters.get("channel_id"):
        params["channelId"] = filters["channel_id"]
    if filters.get("video_duration"):
        params["videoDuration"] = filters["video_duration"]
    if filters.get("video_definition"):
        params["videoDefinition"] = filters["video_definition"]
    if filters.get("safe_search"):
        params["safeSearch"] = filters["safe_search"]

    data = api_call("search", params)
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


def search_channels(query: str, max_results: int = 10, **filters) -> dict:
    """Search YouTube channels via Data API v3 with subscriber enrichment."""
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": min(max_results, 50),
        "type": "channel",
    }
    if filters.get("order"):
        params["order"] = filters["order"]

    data = api_call("search", params)
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

    # Enrich with subscriber counts
    if channel_ids:
        try:
            stats = api_call("channels", {
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


def channel_info(channel_id: str) -> dict:
    """Get detailed channel info via Data API v3."""
    data = api_call("channels", {
        "part": "snippet,statistics,brandingSettings",
        "id": channel_id,
    })
    items = data.get("items", [])
    if not items:
        raise NotFoundError(
            f"Channel not found: {channel_id}",
            source=ErrorSource.YOUTUBE_DATA_API,
        )
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


def get_comments(video_id: str, max_results: int = 20) -> list[dict]:
    """Get top-level comments for a video via Data API v3."""
    data = api_call("commentThreads", {
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


def get_trending(limit: int = 10) -> dict:
    """Get trending videos via Data API v3."""
    data = api_call("videos", {
        "part": "snippet",
        "chart": "mostPopular",
        "maxResults": min(limit, 50),
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


def get_video_info(video_id: str) -> dict:
    """Get video metadata via Data API v3."""
    data = api_call("videos", {
        "part": "snippet,statistics,contentDetails",
        "id": video_id,
    })
    items = data.get("items", [])
    if not items:
        raise NotFoundError(
            f"Video not found: {video_id}",
            source=ErrorSource.YOUTUBE_DATA_API,
        )
    v = items[0]
    sn = v.get("snippet", {})
    st = v.get("statistics", {})
    cd = v.get("contentDetails", {})
    # Parse ISO 8601 duration to seconds
    dur = cd.get("duration", "PT0S").replace("PT", "").replace("H", ":").replace("M", ":").replace("S", "")
    try:
        parts = dur.split(":")
        if len(parts) == 3:
            duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            duration = int(parts[0]) * 60 + int(parts[1])
        else:
            duration = int(parts[0]) if parts[0] else 0
    except (ValueError, IndexError):
        duration = None

    return {
        "id": video_id,
        "title": sn.get("title", ""),
        "url": f"https://youtube.com/watch?v={video_id}",
        "duration": duration,
        "view_count": int(st.get("viewCount", 0)) if st.get("viewCount") else None,
        "channel": sn.get("channelTitle", ""),
        "channel_id": sn.get("channelId", ""),
        "channel_url": f"https://youtube.com/channel/{sn.get('channelId', '')}",
        "upload_date": (sn.get("publishedAt", "")[:10]).replace("-", ""),
        "description": (sn.get("description", "") or "")[:500],
        "thumbnail": sn.get("thumbnails", {}).get("default", {}).get("url"),
        "tags": sn.get("tags", [])[:20] if sn.get("tags") else None,
        "source": "YouTube Data API v3",
    }
