"""Frozen addendum: safe retry after subtitle-listing failures.

The v1.1.0 selector must never call youtube-transcript-api's implicit-English
``fetch(video_id)`` fallback when no language cohort could be established.
"""

import pytest
from youtube_transcript_api._errors import TranscriptsDisabled

from tube_bridge.youtube import transcript as transcript_module


class _ListingFailureApi:
    def __init__(self) -> None:
        self.fetch_calls: list[object] = []

    def list(self, _video_id: str):
        raise OSError("subtitle listing network failure")

    def fetch(self, _video_id: str, languages=None):
        self.fetch_calls.append(languages)
        raise AssertionError("unsafe implicit-language retry")


def test_default_listing_failure_never_retries_with_implicit_english(monkeypatch):
    api = _ListingFailureApi()
    monkeypatch.setattr(transcript_module, "_api", api)

    with pytest.raises(RuntimeError, match="OSError: subtitle listing network failure"):
        transcript_module.get_transcript("abcdefghijk")

    assert api.fetch_calls == []


def test_explicit_retry_absence_does_not_erase_listing_network_error(monkeypatch):
    class ExplicitRetryApi(_ListingFailureApi):
        def fetch(self, video_id: str, languages=None):
            self.fetch_calls.append(languages)
            assert languages == ["fr"]
            raise TranscriptsDisabled(video_id)

    api = ExplicitRetryApi()
    monkeypatch.setattr(transcript_module, "_api", api)

    with pytest.raises(RuntimeError, match="OSError: subtitle listing network failure"):
        transcript_module.get_transcript("abcdefghijk", lang="fr")

    assert api.fetch_calls == [["fr"]]
