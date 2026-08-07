"""tube-bridge — yt-dlp subprocess client with retry + stderr capture."""

import json
import re
import subprocess
import time

from .models import VideoInfo


def run_ytdlp(args: list[str], timeout: int = 60, retries: int = 2) -> tuple[dict | None, str]:
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


def run_ytdlp_multi(args: list[str], timeout: int = 60, retries: int = 2) -> tuple[list[dict], str]:
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
        channel_url=data.get("channel_url") or data.get("uploader_url"),
        upload_date=data.get("upload_date"),
        description=(data.get("description", "") or "")[:500],
        thumbnail=data.get("thumbnail"),
        categories=data.get("categories"),
        tags=data.get("tags", [])[:20] if data.get("tags") else None,
    )
