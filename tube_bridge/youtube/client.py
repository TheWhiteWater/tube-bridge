"""tube-bridge — yt-dlp subprocess client with retry + stderr capture."""

import json
import os
import re
import subprocess
import time

from ..errors import (
    ErrorSource,
    InvalidArgumentError,
    NotFoundError,
    RateLimitedError,
    UpstreamUnavailableError,
)
from .models import VideoInfo


def get_proxy() -> str | None:
    """Get an HTTP(S) or SOCKS proxy URL from the environment."""
    return os.environ.get("TUBE_BRIDGE_PROXY") or os.environ.get("HTTPS_PROXY")


def run_ytdlp(args: list[str], timeout: int = 60, retries: int = 2) -> tuple[dict | None, str]:
    """Run yt-dlp --dump-json. Returns (data, stderr_info). Retries on transient failures."""
    cmd = ["yt-dlp", "--no-warnings", "--no-playlist"]
    proxy = get_proxy()
    if proxy:
        cmd.extend(["--proxy", proxy])
    cmd.extend(args)
    
    last_stderr = ""
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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


def run_ytdlp_multi(args: list[str], timeout: int = 60, retries: int = 2) -> tuple[list[dict], str]:
    """Run yt-dlp --dump-json (multi-line). Returns (items, stderr_info). Retries on transient failures."""
    cmd = ["yt-dlp", "--no-warnings"]
    proxy = get_proxy()
    if proxy:
        cmd.extend(["--proxy", proxy])
    cmd.extend(args)
    
    last_stderr = ""
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
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


def ytdlp_failure(message: str, stderr: str = ""):
    """Classify from yt-dlp stderr without exposing its raw contents to clients."""
    normalized = stderr.strip().lower()
    if "http error 429" in normalized or "too many requests" in normalized:
        return RateLimitedError(message, source=ErrorSource.YT_DLP)
    if "video unavailable" in normalized or "private video" in normalized:
        return NotFoundError(message, source=ErrorSource.YT_DLP)
    if (
        "unsupported url" in normalized
        or "invalid url" in normalized
        or "is not a valid url" in normalized
    ):
        return InvalidArgumentError(message, source=ErrorSource.YT_DLP)
    if "sign in to confirm your age" in normalized or "age-restricted" in normalized:
        return UpstreamUnavailableError(
            message, source=ErrorSource.YT_DLP, retryable=False
        )
    return UpstreamUnavailableError(message, source=ErrorSource.YT_DLP)


def extract_video_id(url_or_id: str) -> str:
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


def parse_video_info(data: dict) -> VideoInfo:
    """Parse yt-dlp JSON output into VideoInfo."""
    return VideoInfo(
        id=data.get("id", ""),
        title=data.get("title", ""),
        url=data.get("webpage_url", f"https://youtube.com/watch?v={data.get('id', '')}"),
        duration=data.get("duration"),
        view_count=data.get("view_count"),
        channel=data.get("channel") or data.get("uploader"),
        channel_id=data.get("channel_id") or data.get("uploader_id"),
        channel_url=data.get("channel_url") or data.get("uploader_url"),
        upload_date=data.get("upload_date"),
        description=(data.get("description", "") or "")[:500],
        thumbnail=data.get("thumbnail"),
        categories=data.get("categories"),
        tags=data.get("tags", [])[:20] if data.get("tags") else None,
    )


def channel_metadata(channel_id: str | None, channel_url: str | None) -> dict:
    """Fetch bounded, observable channel-page metadata through keyless yt-dlp."""
    target = channel_url or (
        f"https://www.youtube.com/channel/{channel_id}" if channel_id else None
    )
    if not target:
        raise InvalidArgumentError("Channel ID or URL is required")
    items, stderr = run_ytdlp_multi(
        [
            target,
            "--dump-single-json",
            "--flat-playlist",
            "--playlist-end",
            "1",
        ],
        timeout=45,
    )
    if not items:
        raise ytdlp_failure("Could not fetch observable channel metadata", stderr)
    data = items[0]
    raw_description = data.get("description")
    description = raw_description if isinstance(raw_description, str) else None
    if description is not None and len(description) > 5_000:
        description = description[:5_000]
        description_truncated = True
    else:
        description_truncated = False
    observed_channel_id = data.get("channel_id") or data.get("id") or channel_id
    canonical_url = data.get("channel_url") or (
        f"https://www.youtube.com/channel/{observed_channel_id}"
        if observed_channel_id
        else target
    )
    return {
        "channel_id": observed_channel_id,
        "title": data.get("channel") or data.get("uploader") or data.get("title"),
        "description": description,
        "description_truncated": description_truncated,
        "canonical_url": canonical_url,
        "country": None,
        "provider": "yt-dlp",
    }
