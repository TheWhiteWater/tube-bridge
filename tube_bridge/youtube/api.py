"""tube-bridge — YouTube Data API v3 client (optional, requires YOUTUBE_API_KEY)."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request


def get_api_key() -> str | None:
    """Get YouTube Data API key from environment."""
    return os.environ.get("YOUTUBE_API_KEY")


def api_call(endpoint: str, params: dict) -> dict:
    """Make a YouTube Data API v3 request. Raises RuntimeError with specific error codes."""
    key = get_api_key()
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
                    raise RuntimeError("QUOTA_EXCEEDED: YouTube Data API daily quota exhausted.")
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
