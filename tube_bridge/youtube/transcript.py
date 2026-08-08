"""tube-bridge - YouTube transcript extraction (youtube-transcript-api)."""

import os
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


_api: Any = None


def _get_proxy() -> str | None:
    return os.environ.get("TUBE_BRIDGE_PROXY") or os.environ.get("HTTPS_PROXY")


def _get_api():
    global _api
    if _api is None:
        proxy_url = _get_proxy()
        if proxy_url:
            from youtube_transcript_api.proxies import GenericProxyConfig
            _api = YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url))
        else:
            _api = YouTubeTranscriptApi()
    return _api


def get_transcript(video_id: str, lang: str | None = None) -> tuple[list[dict], str, bool]:
    """Get transcript segments. Returns (segments, language_code, is_generated).
    Prioritizes manual subtitles over auto-generated (ASR)."""
    api = _get_api()
    last_error: Exception | None = None

    def _try_fetch(transcript_obj) -> list[dict] | None:
        nonlocal last_error
        try:
            fetched = transcript_obj.fetch()
            return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
        except Exception as e:
            last_error = e
            return None

    try:
        transcript_list = api.list(video_id)
        manual = [t for t in transcript_list if not t.is_generated]
        generated = [t for t in transcript_list if t.is_generated]

        if lang:
            manual = [t for t in manual if t.language_code == lang]
            generated = [t for t in generated if t.language_code == lang]

        for t in manual + generated:
            segments = _try_fetch(t)
            if segments:
                return segments, t.language_code, t.is_generated

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        last_error = e
    except Exception as e:
        last_error = e

    try:
        languages = [lang] if lang else None
        transcript = api.fetch(video_id, languages=languages)
        segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in transcript]
        return segments, lang or "unknown", False
    except Exception as e:
        last_error = e

    # A confirmed "this video has no captions" (TranscriptsDisabled/NoTranscriptFound) is
    # indistinguishable, otherwise, from every other failure mode (IP block, network error,
    # proxy misconfiguration) -- all of which used to collapse into the same generic message.
    # Surface the real cause whenever it's something other than a confirmed absence of captions.
    if last_error is not None and not isinstance(last_error, (TranscriptsDisabled, NoTranscriptFound)):
        raise RuntimeError(
            f"No transcript found for video {video_id}: {type(last_error).__name__}: {last_error}"
        ) from last_error
    raise RuntimeError(f"No transcript found for video {video_id}")


def get_available_languages(video_id: str) -> list[dict]:
    """List available transcript languages."""
    api = _get_api()
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
    except (TranscriptsDisabled, NoTranscriptFound):
        return []
    except Exception as e:
        # Same distinction as get_transcript: don't let a block/network failure masquerade
        # as "this video simply has no captions" (an empty list looks identical to callers).
        raise RuntimeError(
            f"Could not list transcript languages for video {video_id}: {type(e).__name__}: {e}"
        ) from e
