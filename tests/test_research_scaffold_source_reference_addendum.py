"""Addendum: corpus scaffolds carry compact stable refs from source artifacts."""

from __future__ import annotations

import pytest

from tube_bridge import research_artifacts, tools


@pytest.mark.asyncio
async def test_corpus_scaffold_carries_compact_transcript_source_reference(
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
            "channel_metadata": {"status": "unavailable"},
            "transcript": {
                "status": "ready",
                "transcript_version_id": "trv_hash",
                "source_sha256": "hash",
            },
            "source_segments": [
                {
                    "segment_id": "seg_hash_00000000",
                    "ordinal": 0,
                    "start_ms": 0,
                    "end_ms": 1000,
                    "text": "exact text must not be copied into corpus refs",
                },
                {
                    "segment_id": "seg_hash_00000001",
                    "ordinal": 1,
                    "start_ms": 1000,
                    "end_ms": 2000,
                    "text": "second exact segment",
                },
            ],
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
    monkeypatch.setattr(tools.cache, "get_video_info", lambda video_id: None)
    monkeypatch.setattr(tools.cache, "get_transcript", lambda *args: None)

    corpus_artifact = await tools.research_scaffold_create(
        "corpus-study-v1", {"type": "corpus", "corpus_id": "local-corpus"}
    )
    corpus_source = corpus_artifact["machine_fields"]["sources"][0]
    assert corpus_source["structured_source_artifact_id"] == source["artifact_id"]
    assert corpus_source["source_reference"] == {
        "transcript_version_id": "trv_hash",
        "source_sha256": "hash",
        "segments": [
            {"segment_id": "seg_hash_00000000", "start_ms": 0, "end_ms": 1000},
            {"segment_id": "seg_hash_00000001", "start_ms": 1000, "end_ms": 2000},
        ],
    }
    assert "text" not in corpus_source["source_reference"]["segments"][0]
