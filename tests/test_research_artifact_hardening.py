"""Frozen regressions for the four L0 research-preview findings."""

from __future__ import annotations

import csv
import importlib
import io

import pytest

from tube_bridge import research_artifacts, tools

server_module = importlib.import_module("tube_bridge.server")
from tube_bridge.errors import InvalidArgumentError


VIDEO_ID = "abcdefghijk"


@pytest.fixture
def isolated_research_store(tmp_path, monkeypatch):
    monkeypatch.setattr(research_artifacts, "DB_PATH", tmp_path / "research-artifacts.db")


def _source_machine(language: str, digest: str) -> dict:
    return {
        "target": {"type": "video", "video_id": VIDEO_ID},
        "video_metadata": {"title": f"Observed {language}"},
        "channel_metadata": {
            "status": "ready",
            "channel_id": "UC-observed",
            "title": "Observed channel",
            "description": "Observed channel description",
            "provider": "yt-dlp",
        },
        "transcript": {
            "status": "ready",
            "transcript_version_id": f"trv_{digest}",
            "source_sha256": digest,
            "selected_language": language,
            "track_kind": "manual",
        },
        "source_segments": [
            {
                "segment_id": f"seg_{digest}_00000000",
                "ordinal": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "text": f"{language} first",
            },
            {
                "segment_id": f"seg_{digest}_00000001",
                "ordinal": 1,
                "start_ms": 1000,
                "end_ms": 2000,
                "text": f"{language} second",
            },
        ],
    }


def _source_ref(language: str, digest: str) -> dict:
    return {
        "video_id": VIDEO_ID,
        "transcript_version_id": f"trv_{digest}",
        "first_segment_id": f"seg_{digest}_00000000",
        "last_segment_id": f"seg_{digest}_00000001",
        "start_ms": 0,
        "end_ms": 2000,
    }


def _corpus_machine(digest: str = "enhash") -> dict:
    return {
        "target": {"type": "corpus", "corpus_id": "sample"},
        "corpus_snapshot": {"corpus_id": "sample", "source_count": 1},
        "sources": [
            {
                "video_id": VIDEO_ID,
                "source_selection_status": "selected_explicit",
                "structured_source_artifact_id": "rart_source",
                "source_reference": {
                    "transcript_version_id": f"trv_{digest}",
                    "source_sha256": digest,
                    "segments": [
                        {
                            "segment_id": f"seg_{digest}_00000000",
                            "start_ms": 0,
                            "end_ms": 1000,
                        },
                        {
                            "segment_id": f"seg_{digest}_00000001",
                            "start_ms": 1000,
                            "end_ms": 2000,
                        },
                    ],
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_multilingual_corpus_source_is_ambiguous_until_explicitly_selected(
    isolated_research_store, monkeypatch
) -> None:
    from tube_bridge import corpus

    english = research_artifacts.create_artifact(
        "structured-source-v1", "video", VIDEO_ID, _source_machine("en", "enhash")
    )
    russian = research_artifacts.create_artifact(
        "structured-source-v1", "video", VIDEO_ID, _source_machine("ru", "ruhash")
    )
    monkeypatch.setattr(
        corpus,
        "corpus_snapshot",
        lambda corpus_id: {
            "corpus_id": corpus_id,
            "label": "Multilingual",
            "sources": [{"video_id": VIDEO_ID, "title": "Source", "added_at": 1.0}],
        },
    )
    monkeypatch.setattr(tools.cache, "get_video_info", lambda video_id: None)
    monkeypatch.setattr(tools.cache, "get_transcript", lambda *args: None)

    ambiguous = await tools.research_scaffold_create(
        "corpus-study-v1", {"type": "corpus", "corpus_id": "sample"}
    )
    source = ambiguous["machine_fields"]["sources"][0]
    assert source["source_selection_status"] == "ambiguous"
    assert source["structured_source_artifact_id"] is None
    assert source["source_reference"] is None
    assert source["transcript_status"] == "ambiguous"
    assert source["selected_language"] is None
    assert {
        (item["artifact_id"], item["transcript_version_id"], item["selected_language"])
        for item in source["available_source_artifacts"]
    } == {
        (english["artifact_id"], "trv_enhash", "en"),
        (russian["artifact_id"], "trv_ruhash", "ru"),
    }

    selected = await tools.research_scaffold_create(
        "corpus-study-v1",
        {
            "type": "corpus",
            "corpus_id": "sample",
            "source_artifact_ids": [english["artifact_id"]],
        },
    )
    selected_source = selected["machine_fields"]["sources"][0]
    assert selected_source["source_selection_status"] == "selected_explicit"
    assert selected_source["structured_source_artifact_id"] == english["artifact_id"]
    assert selected_source["source_reference"]["transcript_version_id"] == "trv_enhash"
    assert selected_source["transcript_status"] == "ready"
    assert selected_source["selected_language"] == "en"


def test_research_tool_schema_accepts_explicit_source_artifact_ids() -> None:
    create = next(
        item for item in server_module._build_tools(include_research=True)
        if item.name == "research_scaffold_create"
    )
    selection = create.inputSchema["properties"]["target"]["properties"][
        "source_artifact_ids"
    ]
    assert selection == {
        "type": "array",
        "items": {"type": "string", "minLength": 1},
        "uniqueItems": True,
    }


def test_partial_agent_save_deep_merges_documented_fields(
    isolated_research_store,
) -> None:
    created = research_artifacts.create_artifact(
        "structured-source-v1", "video", VIDEO_ID, _source_machine("en", "enhash")
    )
    saved = research_artifacts.save_artifact(
        created["artifact_id"],
        1,
        {"metadata_annotation": {"summary": "Agent-authored summary"}},
        author=None,
    )
    metadata = saved["agent_fields"]["metadata_annotation"]
    assert metadata == {
        "completion": "unfilled",
        "summary": "Agent-authored summary",
        "tags": [],
        "custom_fields": {},
    }
    assert saved["agent_fields"]["content_structure"] == created["agent_fields"][
        "content_structure"
    ]


def test_all_claimed_source_references_use_one_validated_contract(
    isolated_research_store,
) -> None:
    source = research_artifacts.create_artifact(
        "structured-source-v1", "video", VIDEO_ID, _source_machine("en", "enhash")
    )
    valid_source_fields = source["agent_fields"]
    valid_source_fields["source_annotation"]["evidence_refs"] = [
        _source_ref("en", "enhash")
    ]
    saved = research_artifacts.save_artifact(
        source["artifact_id"], 1, valid_source_fields, author=None
    )
    assert saved["revision"] == 2

    nonsense = saved["agent_fields"]
    nonsense["source_annotation"]["evidence_refs"] = [{"nonsense": "accepted"}]
    with pytest.raises(InvalidArgumentError, match="schema"):
        research_artifacts.save_artifact(
            source["artifact_id"], 2, nonsense, author=None
        )

    wrong_version = saved["agent_fields"]
    wrong_version["source_annotation"]["evidence_refs"] = [
        {**_source_ref("en", "enhash"), "transcript_version_id": "trv_wrong"}
    ]
    with pytest.raises(InvalidArgumentError, match="transcript_version_id"):
        research_artifacts.save_artifact(
            source["artifact_id"], 2, wrong_version, author=None
        )

    corpus = research_artifacts.create_artifact(
        "corpus-study-v1", "corpus", "sample", _corpus_machine()
    )
    corpus_fields = corpus["agent_fields"]
    corpus_fields["evidence_ledger"] = {
        "completion": "complete",
        "entries": [
            {
                "evidence_id": "ev-1",
                "source_refs": [_source_ref("en", "enhash")],
                "observation": "Agent observation",
                "interpretation": None,
                "confidence": "high",
            }
        ],
    }
    saved_corpus = research_artifacts.save_artifact(
        corpus["artifact_id"], 1, corpus_fields, author=None
    )
    assert saved_corpus["revision"] == 2

    bad_ledger = saved_corpus["agent_fields"]
    bad_ledger["evidence_ledger"] = {
        "completion": "complete",
        "entries": [{"nonsense": "accepted"}],
    }
    with pytest.raises(InvalidArgumentError, match="schema"):
        research_artifacts.save_artifact(
            corpus["artifact_id"], 2, bad_ledger, author=None
        )


def test_csv_export_preserves_complete_coding_row_provenance(
    isolated_research_store,
) -> None:
    corpus = research_artifacts.create_artifact(
        "corpus-study-v1", "corpus", "sample", _corpus_machine()
    )
    fields = corpus["agent_fields"]
    fields["coding_rows"] = {
        "completion": "complete",
        "rows": [
            {
                "row_id": "row-1",
                **_source_ref("en", "enhash"),
                "code_ids": ["code-a", "code-b"],
                "quotation": "Quoted source text",
                "context_before": "Before",
                "context_after": "After",
                "agent_note": "Researcher note",
                "confidence": "high",
            }
        ],
    }
    saved = research_artifacts.save_artifact(
        corpus["artifact_id"], 1, fields, author=None
    )
    exported = research_artifacts.export_artifact(saved["artifact_id"], "csv")
    row = next(csv.DictReader(io.StringIO(exported["content"])))
    assert row == {
        "row_id": "row-1",
        "video_id": VIDEO_ID,
        "transcript_version_id": "trv_enhash",
        "first_segment_id": "seg_enhash_00000000",
        "last_segment_id": "seg_enhash_00000001",
        "start_ms": "0",
        "end_ms": "2000",
        "code_ids": "code-a|code-b",
        "quotation": "Quoted source text",
        "context_before": "Before",
        "context_after": "After",
        "agent_note": "Researcher note",
        "confidence": "high",
    }
