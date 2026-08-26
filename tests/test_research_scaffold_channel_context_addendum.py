"""Addendum: corpus scaffolds reuse source-artifact channel context without network fan-out."""

from __future__ import annotations

import pytest

from tube_bridge import research_artifacts, tools


@pytest.mark.asyncio
async def test_corpus_scaffold_reuses_attached_source_channel_description(
    tmp_path, monkeypatch
) -> None:
    from tube_bridge import corpus

    monkeypatch.setattr(research_artifacts, "DB_PATH", tmp_path / "research-artifacts.db")
    source = research_artifacts.create_artifact(
        "structured-source-v1",
        "video",
        "abcdefghijk",
        {
            "target": {"type": "video", "video_id": "abcdefghijk"},
            "video_metadata": {"title": "Observed video title"},
            "channel_metadata": {
                "status": "ready",
                "channel_id": "UC-source",
                "title": "Observed channel title",
                "description": "Exact observed channel description",
                "canonical_url": "https://youtube.com/channel/UC-source",
                "country": "NZ",
                "provider": "yt-dlp",
                "retrieval_mode": "live",
            },
            "transcript": {"status": "unavailable"},
            "source_segments": [],
        },
    )
    monkeypatch.setattr(
        corpus,
        "corpus_snapshot",
        lambda corpus_id: {
            "corpus_id": corpus_id,
            "label": "Local corpus",
            "embedding_model": "model",
            "created_at": 1.0,
            "chunk_count": 1,
            "sources": [
                {"video_id": "abcdefghijk", "title": "Corpus title", "added_at": 2.0}
            ],
        },
    )
    monkeypatch.setattr(
        tools.cache,
        "get_video_info",
        lambda video_id: {"id": video_id, "title": "Cached video title", "cached": True},
    )
    monkeypatch.setattr(tools.cache, "get_transcript", lambda *args: None)
    monkeypatch.setattr(
        tools,
        "video_info",
        lambda *args: (_ for _ in ()).throw(AssertionError("network fan-out")),
    )

    corpus_artifact = await tools.research_scaffold_create(
        "corpus-study-v1", {"type": "corpus", "corpus_id": "local-corpus"}
    )
    corpus_source = corpus_artifact["machine_fields"]["sources"][0]
    assert corpus_source["channel_id"] == "UC-source"
    assert corpus_source["channel_name"] == "Observed channel title"
    assert corpus_source["channel_description"] == "Exact observed channel description"
    assert corpus_source["channel_metadata_provider"] == "yt-dlp"
    assert corpus_source["channel_context_artifact_id"] == source["artifact_id"]
