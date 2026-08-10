"""Frozen selection contract for YouTube subtitle tracks."""

from dataclasses import dataclass

from tube_bridge import cache as cache_module
from tube_bridge.youtube import transcript as transcript_module


@dataclass
class _Segment:
    text: str
    start: float = 0.0
    duration: float = 1.0


class _Track:
    def __init__(self, language_code: str, *, generated: bool, text: str):
        self.language_code = language_code
        self.is_generated = generated
        self.language = language_code
        self._text = text
        self.fetch_count = 0

    def fetch(self):
        self.fetch_count += 1
        return [_Segment(self._text)]


class _FetchedTranscript(list):
    def __init__(self, language_code: str, *, generated: bool, text: str):
        super().__init__([_Segment(text)])
        self.language_code = language_code
        self.is_generated = generated


class _Api:
    def __init__(self, tracks: list[_Track]):
        self._tracks = tracks
        self.fallback_fetch_count = 0

    def list(self, _video_id: str):
        return list(self._tracks)

    def fetch(self, _video_id: str, languages=None):
        self.fallback_fetch_count += 1
        raise AssertionError(f"unexpected fallback fetch for {languages!r}")


def test_default_uses_generated_track_language_instead_of_foreign_manual(monkeypatch):
    spanish_manual = _Track("es", generated=False, text="doblaje")
    english_generated = _Track("en", generated=True, text="original speech")
    api = _Api([spanish_manual, english_generated])
    monkeypatch.setattr(transcript_module, "_api", api)

    segments, language, generated = transcript_module.get_transcript("abcdefghijk")

    assert segments[0]["text"] == "original speech"
    assert (language, generated) == ("en", True)
    assert spanish_manual.fetch_count == 0
    assert english_generated.fetch_count == 1


def test_default_prefers_manual_track_only_within_original_language(monkeypatch):
    spanish_manual = _Track("es", generated=False, text="doblaje")
    english_manual = _Track("en-US", generated=False, text="edited original captions")
    english_generated = _Track("en", generated=True, text="automatic original captions")
    api = _Api([spanish_manual, english_manual, english_generated])
    monkeypatch.setattr(transcript_module, "_api", api)

    segments, language, generated = transcript_module.get_transcript("abcdefghijk")

    assert segments[0]["text"] == "edited original captions"
    assert (language, generated) == ("en-US", False)
    assert spanish_manual.fetch_count == 0
    assert english_manual.fetch_count == 1
    assert english_generated.fetch_count == 0


def test_default_prefers_exact_manual_language_before_regional_variant(monkeypatch):
    british_manual = _Track("en-GB", generated=False, text="regional captions")
    english_manual = _Track("en", generated=False, text="exact captions")
    english_generated = _Track("en", generated=True, text="automatic captions")
    api = _Api([british_manual, english_manual, english_generated])
    monkeypatch.setattr(transcript_module, "_api", api)

    segments, language, generated = transcript_module.get_transcript("abcdefghijk")

    assert segments[0]["text"] == "exact captions"
    assert (language, generated) == ("en", False)
    assert british_manual.fetch_count == 0
    assert english_manual.fetch_count == 1


def test_default_retry_reports_actual_selected_track_metadata(monkeypatch):
    class FailingTrack(_Track):
        def fetch(self):
            self.fetch_count += 1
            raise OSError("temporary track fetch failure")

    class RetryApi(_Api):
        def fetch(self, _video_id: str, languages=None):
            self.fallback_fetch_count += 1
            assert languages == ["en"]
            return _FetchedTranscript("en", generated=True, text="retry succeeded")

    spanish_manual = _Track("es", generated=False, text="doblaje")
    english_generated = FailingTrack("en", generated=True, text="unused")
    api = RetryApi([spanish_manual, english_generated])
    monkeypatch.setattr(transcript_module, "_api", api)

    segments, language, generated = transcript_module.get_transcript("abcdefghijk")

    assert segments[0]["text"] == "retry succeeded"
    assert (language, generated) == ("en", True)
    assert spanish_manual.fetch_count == 0
    assert api.fallback_fetch_count == 1


def test_default_cache_does_not_reuse_legacy_arbitrary_language_entry(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cache_module, "DB_PATH", tmp_path / "cache.db")
    legacy_segments = [{"text": "old foreign track", "start": 0.0, "duration": 1.0}]
    with cache_module._connection() as connection:
        connection.execute(
            "INSERT INTO transcripts VALUES (?, ?, ?, ?, ?, ?)",
            ("abcdefghijk", "__any__", "[]", "es", 0, 1.0),
        )
        connection.commit()

    assert cache_module.get_transcript("abcdefghijk", None) is None

    cache_module.set_transcript(
        "abcdefghijk", None, legacy_segments, "en", True
    )
    with cache_module._connection() as connection:
        keys = connection.execute(
            "SELECT lang FROM transcripts WHERE video_id='abcdefghijk' ORDER BY lang"
        ).fetchall()
    assert keys == [("__any__",), ("__default_v2__",)]


def test_explicit_language_remains_strict_manual_then_generated_override(monkeypatch):
    spanish_generated = _Track("es", generated=True, text="automatic Spanish")
    spanish_manual = _Track("es", generated=False, text="manual Spanish")
    english_generated = _Track("en", generated=True, text="original speech")
    api = _Api([spanish_generated, spanish_manual, english_generated])
    monkeypatch.setattr(transcript_module, "_api", api)

    segments, language, generated = transcript_module.get_transcript(
        "abcdefghijk", lang="es"
    )

    assert segments[0]["text"] == "manual Spanish"
    assert (language, generated) == ("es", False)
    assert spanish_manual.fetch_count == 1
    assert spanish_generated.fetch_count == 0
    assert english_generated.fetch_count == 0
