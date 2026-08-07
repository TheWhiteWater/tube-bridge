"""tube-bridge — YouTube transcript extraction (youtube-transcript-api)."""

from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound


_api: Any = None


def _get_api():
    global _api
    if _api is None:
        _api = YouTubeTranscriptApi()
    return _api


def get_transcript(video_id: str, lang: str | None = None) -> tuple[list[dict], str, bool]:
    """Get transcript segments. Returns (segments, language_code, is_generated).
    Prioritizes manual subtitles over auto-generated (ASR)."""
    api = _get_api()

    def _try_fetch(transcript_obj) -> list[dict] | None:
        try:
            fetched = transcript_obj.fetch()
            return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
        except Exception:
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

    except (TranscriptsDisabled, NoTranscriptFound):
        pass
    except Exception:
        pass

    try:
        languages = [lang] if lang else None
        transcript = api.fetch(video_id, languages=languages)
        segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in transcript]
        return segments, lang or "unknown", False
    except Exception:
        pass

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
    except Exception:
        return []
