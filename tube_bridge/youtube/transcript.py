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


def _language_family(language_code: str) -> str:
    """Return the base BCP-47 language subtag used for track matching."""
    return language_code.strip().lower().replace("_", "-").split("-", 1)[0]


def _ordered_tracks(tracks: list[Any], lang: str | None) -> tuple[list[Any], str | None]:
    """Choose one language cohort without falling through to a foreign dub."""
    manual = [track for track in tracks if not track.is_generated]
    generated = [track for track in tracks if track.is_generated]

    if lang:
        return (
            [track for track in manual if track.language_code == lang]
            + [track for track in generated if track.language_code == lang],
            lang,
        )

    if generated:
        default_code = generated[0].language_code
        default_family = _language_family(default_code)
        matching_manual = [
            track for track in manual if track.language_code == default_code
        ] + [
            track
            for track in manual
            if track.language_code != default_code
            and _language_family(track.language_code) == default_family
        ]
        matching_generated = [
            track for track in generated if track.language_code == default_code
        ] + [
            track
            for track in generated
            if track.language_code != default_code
            and _language_family(track.language_code) == default_family
        ]
        return matching_manual + matching_generated, default_code

    if manual:
        return [manual[0]], manual[0].language_code

    return [], None


def get_transcript(video_id: str, lang: str | None = None) -> tuple[list[dict], str, bool]:
    """Get transcript segments as ``(segments, language_code, is_generated)``.

    With no explicit language, stay in the original/default language cohort and
    prefer a matching manual track over ASR. Never fall through to an unrelated
    foreign manual track merely because it is manual.
    """
    api = _get_api()
    last_error: Exception | None = None
    fallback_language = lang

    def _try_fetch(transcript_obj) -> list[dict] | None:
        nonlocal last_error
        try:
            fetched = transcript_obj.fetch()
            return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
        except Exception as e:
            last_error = e
            return None

    try:
        tracks, fallback_language = _ordered_tracks(list(api.list(video_id)), lang)

        for t in tracks:
            segments = _try_fetch(t)
            if segments:
                return segments, t.language_code, t.is_generated

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        last_error = e
    except Exception as e:
        last_error = e

    # A direct retry is safe only after a language was established explicitly or
    # from a successfully listed default cohort. Calling api.fetch() without a
    # language defaults to English in youtube-transcript-api and can silently
    # cross into an unrelated dub after a listing/network failure.
    if fallback_language:
        previous_error = last_error
        try:
            transcript = api.fetch(video_id, languages=[fallback_language])
            segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in transcript]
            selected_language = getattr(transcript, "language_code", fallback_language)
            selected_is_generated = bool(getattr(transcript, "is_generated", False))
            return segments, selected_language, selected_is_generated
        except Exception as e:
            # Do not let an absence-shaped retry error erase an earlier network,
            # proxy, or track-fetch failure.
            if (
                isinstance(e, (TranscriptsDisabled, NoTranscriptFound))
                and previous_error is not None
                and not isinstance(previous_error, (TranscriptsDisabled, NoTranscriptFound))
            ):
                last_error = previous_error
            else:
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
