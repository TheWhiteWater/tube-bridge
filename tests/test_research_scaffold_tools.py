"""Frozen source/corpus scaffold autofill contract."""

from __future__ import annotations

import hashlib

import pytest

from tube_bridge import research_artifacts
from tube_bridge import tools
from tube_bridge.errors import TranscriptUnavailableError, UpstreamUnavailableError, ErrorSource


@pytest.fixture
def isolated_research_store(tmp_path, monkeypatch):
    monkeypatch.setattr(research_artifacts, "DB_PATH", tmp_path / "research-artifacts.db")


@pytest.fixture
def source_upstreams(monkeypatch):
    async def fake_video_info(video_id: str) -> dict:
        assert video_id == "abcdefghijk"
        return {
            "id": video_id,
            "title": "Exact video title",
            "url": f"https://youtube.com/watch?v={video_id}",
            "description": "Exact video description",
            "duration": 12,
            "channel_id": "UC-source-channel",
            "channel": "Video channel title",
            "channel_url": "https://youtube.com/channel/UC-source-channel",
            "upload_date": "20260826",
            "source": "YouTube Data API v3",
        }

    def fake_transcript(video_id: str, lang: str | None):
        assert video_id == "abcdefghijk"
        assert lang == "en"
        return {
            "segments": [
                {"text": "first exact segment", "start": 0.0, "duration": 1.25},
                {"text": "second exact segment", "start": 1.25, "duration": 2.0},
            ],
            "language": "en",
            "is_generated": False,
        }

    monkeypatch.setattr(tools, "video_info", fake_video_info)
    monkeypatch.setattr(tools, "_get_transcript_with_meta", fake_transcript)
    monkeypatch.setattr(tools.api, "get_api_key", lambda: "configured")
    monkeypatch.setattr(
        tools.api,
        "channel_info",
        lambda channel_id: {
            "channel_id": channel_id,
            "title": "Exact channel title",
            "description": "Exact observed channel description",
            "custom_url": "@channel",
            "country": "NZ",
        },
    )


@pytest.mark.asyncio
async def test_source_scaffold_autofills_video_channel_and_transcript_provenance(
    isolated_research_store, source_upstreams
) -> None:
    artifact = await tools.research_scaffold_create(
        "structured-source-v1",
        {"type": "video", "video_id": "abcdefghijk", "language": "en"},
    )
    machine = artifact["machine_fields"]

    assert machine["video_metadata"] == {
        "video_id": "abcdefghijk",
        "canonical_url": "https://youtube.com/watch?v=abcdefghijk",
        "title": "Exact video title",
        "description": "Exact video description",
        "duration_seconds": 12,
        "published_at": "20260826",
        "language_hint": None,
        "channel_id": "UC-source-channel",
        "channel_name": "Video channel title",
        "channel_url": "https://youtube.com/channel/UC-source-channel",
        "provider": "YouTube Data API v3",
        "retrieval_mode": "live",
    }
    assert machine["channel_metadata"]["status"] == "ready"
    assert machine["channel_metadata"]["channel_id"] == "UC-source-channel"
    assert machine["channel_metadata"]["title"] == "Exact channel title"
    assert machine["channel_metadata"]["description"] == "Exact observed channel description"
    assert machine["channel_metadata"]["provider"] == "youtube-data-api"
    assert machine["channel_metadata"]["country"] == "NZ"

    transcript = machine["transcript"]
    assert transcript["status"] == "ready"
    assert transcript["track_kind"] == "manual"
    assert transcript["selected_language"] == "en"
    assert transcript["segment_count"] == 2
    assert transcript["transcript_version_id"] == "trv_" + transcript["source_sha256"]
    assert len(transcript["source_sha256"]) == 64

    segments = machine["source_segments"]
    assert segments == [
        {
            "segment_id": f"seg_{transcript['source_sha256']}_00000000",
            "ordinal": 0,
            "start_ms": 0,
            "end_ms": 1250,
            "text": "first exact segment",
        },
        {
            "segment_id": f"seg_{transcript['source_sha256']}_00000001",
            "ordinal": 1,
            "start_ms": 1250,
            "end_ms": 3250,
            "text": "second exact segment",
        },
    ]
    assert hashlib.sha256(
        tools._canonical_json_bytes(transcript["source_envelope"])
    ).hexdigest() == transcript["source_sha256"]

    assert artifact["agent_fields"]["metadata_annotation"]["completion"] == "unfilled"
    assert artifact["agent_fields"]["content_structure"]["sections"] == []
    assert artifact["agent_fields"]["source_annotation"]["media_market"] is None


@pytest.mark.asyncio
async def test_source_scaffold_uses_keyless_channel_description_fallback(
    isolated_research_store, source_upstreams, monkeypatch
) -> None:
    monkeypatch.setattr(tools.api, "get_api_key", lambda: None)
    monkeypatch.setattr(
        tools.yt,
        "channel_metadata",
        lambda channel_id, channel_url: {
            "channel_id": channel_id,
            "title": "Keyless channel title",
            "description": "Keyless exact channel description",
            "canonical_url": channel_url,
            "country": None,
            "provider": "yt-dlp",
        },
    )

    artifact = await tools.research_scaffold_create(
        "structured-source-v1",
        {"type": "video", "video_id": "abcdefghijk", "language": "en"},
    )
    channel = artifact["machine_fields"]["channel_metadata"]
    assert channel["status"] == "ready"
    assert channel["title"] == "Keyless channel title"
    assert channel["description"] == "Keyless exact channel description"
    assert channel["provider"] == "yt-dlp"


@pytest.mark.asyncio
async def test_missing_channel_description_and_transcript_are_explicit_not_invented(
    isolated_research_store, source_upstreams, monkeypatch
) -> None:
    monkeypatch.setattr(tools.api, "get_api_key", lambda: None)
    monkeypatch.setattr(
        tools.yt,
        "channel_metadata",
        lambda *args: (_ for _ in ()).throw(
            UpstreamUnavailableError(
                "Channel metadata unavailable",
                source=ErrorSource.YT_DLP,
                retryable=True,
            )
        ),
    )
    monkeypatch.setattr(
        tools,
        "_get_transcript_with_meta",
        lambda *args: (_ for _ in ()).throw(
            TranscriptUnavailableError("No transcript found")
        ),
    )

    artifact = await tools.research_scaffold_create(
        "structured-source-v1",
        {"type": "video", "video_id": "abcdefghijk", "language": "en"},
    )
    machine = artifact["machine_fields"]
    assert machine["channel_metadata"]["status"] == "unavailable"
    assert machine["channel_metadata"]["description"] is None
    assert machine["channel_metadata"]["warning"] == {
        "code": "upstream_unavailable",
        "source": "yt_dlp",
        "retryable": True,
    }
    assert machine["transcript"]["status"] == "unavailable"
    assert machine["transcript"]["error"] == {
        "code": "transcript_unavailable",
        "source": "youtube_transcript_api",
        "retryable": False,
    }
    assert machine["source_segments"] == []


@pytest.mark.asyncio
async def test_corpus_scaffold_uses_local_snapshot_without_hidden_network_fanout(
    isolated_research_store, monkeypatch
) -> None:
    from tube_bridge import corpus

    monkeypatch.setattr(
        corpus,
        "corpus_snapshot",
        lambda corpus_id: {
            "corpus_id": corpus_id,
            "label": "Local corpus",
            "embedding_model": "model",
            "created_at": 1.0,
            "chunk_count": 3,
            "sources": [
                {"video_id": "abcdefghijk", "title": "Cached title", "added_at": 2.0}
            ],
        },
    )
    monkeypatch.setattr(
        tools.cache,
        "get_video_info",
        lambda video_id: {
            "id": video_id,
            "title": "Cached title",
            "channel_id": "UC-cached",
            "channel": "Cached channel",
            "description": "Cached video description",
            "cached": True,
        },
    )
    monkeypatch.setattr(
        tools,
        "video_info",
        lambda *args: (_ for _ in ()).throw(AssertionError("network metadata fan-out")),
    )

    artifact = await tools.research_scaffold_create(
        "corpus-study-v1", {"type": "corpus", "corpus_id": "local-corpus"}
    )
    machine = artifact["machine_fields"]
    assert machine["corpus_snapshot"]["corpus_id"] == "local-corpus"
    assert machine["sources"][0]["channel_name"] == "Cached channel"
    assert machine["sources"][0]["metadata_retrieval_mode"] == "cache"
    assert artifact["agent_fields"]["research_frame"]["completion"] == "unfilled"
    assert artifact["agent_fields"]["coding_rows"]["rows"] == []
