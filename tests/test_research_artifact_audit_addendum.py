"""Audit-fix addendum for schema, corpus source references, and preview gating."""

from __future__ import annotations

import json

from mcp.types import CallToolResult
import pytest

from tube_bridge import research_artifacts
from tube_bridge.errors import InvalidArgumentError
from tube_bridge.server import call_tool


@pytest.fixture
def isolated_research_store(tmp_path, monkeypatch):
    monkeypatch.setattr(research_artifacts, "DB_PATH", tmp_path / "research-artifacts.db")


def test_template_schema_rejects_wrong_typed_agent_fields(
    isolated_research_store,
) -> None:
    created = research_artifacts.create_artifact(
        "structured-source-v1",
        "video",
        "abcdefghijk",
        {
            "target": {"type": "video", "video_id": "abcdefghijk"},
            "video_metadata": {"title": "Observed"},
            "channel_metadata": {"status": "unavailable"},
            "transcript": {"status": "unavailable"},
            "source_segments": [],
        },
    )
    invalid = created["agent_fields"]
    invalid["metadata_annotation"]["tags"] = "not-an-array"
    with pytest.raises(InvalidArgumentError, match="schema"):
        research_artifacts.save_artifact(
            created["artifact_id"], 1, invalid, author=None
        )


def _corpus_machine_fields() -> dict:
    return {
        "target": {"type": "corpus", "corpus_id": "sample"},
        "corpus_snapshot": {"corpus_id": "sample", "source_count": 1},
        "sources": [
            {
                "video_id": "abcdefghijk",
                "title": "Observed source",
                "structured_source_artifact_id": "rart_source",
                "source_reference": {
                    "transcript_version_id": "trv_hash",
                    "source_sha256": "hash",
                    "segments": [
                        {"segment_id": "seg_hash_00000000", "start_ms": 0, "end_ms": 1000},
                        {"segment_id": "seg_hash_00000001", "start_ms": 1000, "end_ms": 2000},
                    ],
                },
            }
        ],
    }


def _coding_fields(created: dict) -> dict:
    fields = created["agent_fields"]
    fields["coding_rows"] = {
        "completion": "complete",
        "rows": [
            {
                "row_id": "row-1",
                "video_id": "abcdefghijk",
                "transcript_version_id": "trv_hash",
                "first_segment_id": "seg_hash_00000000",
                "last_segment_id": "seg_hash_00000001",
                "start_ms": 0,
                "end_ms": 2000,
                "code_ids": ["code-a"],
                "quotation": "Observed quotation",
                "context_before": None,
                "context_after": None,
                "agent_note": None,
                "confidence": "high",
            }
        ],
    }
    return fields


def test_corpus_coding_rows_validate_transcript_and_segment_bindings(
    isolated_research_store,
) -> None:
    created = research_artifacts.create_artifact(
        "corpus-study-v1", "corpus", "sample", _corpus_machine_fields()
    )
    valid = _coding_fields(created)
    saved = research_artifacts.save_artifact(
        created["artifact_id"], 1, valid, author=None
    )
    assert saved["revision"] == 2

    wrong_version = _coding_fields(saved)
    wrong_version["coding_rows"]["rows"][0]["transcript_version_id"] = "trv_other"
    with pytest.raises(InvalidArgumentError, match="transcript_version_id"):
        research_artifacts.save_artifact(
            created["artifact_id"], 2, wrong_version, author=None
        )

    wrong_segment = _coding_fields(saved)
    wrong_segment["coding_rows"]["rows"][0]["last_segment_id"] = "seg_missing"
    with pytest.raises(InvalidArgumentError, match="segment"):
        research_artifacts.save_artifact(
            created["artifact_id"], 2, wrong_segment, author=None
        )


def test_corpus_coding_row_requires_attached_source_reference(
    isolated_research_store,
) -> None:
    machine = _corpus_machine_fields()
    machine["sources"][0]["source_reference"] = None
    created = research_artifacts.create_artifact(
        "corpus-study-v1", "corpus", "sample", machine
    )
    with pytest.raises(InvalidArgumentError, match="source reference"):
        research_artifacts.save_artifact(
            created["artifact_id"], 1, _coding_fields(created), author=None
        )


@pytest.mark.asyncio
async def test_disabled_preview_tool_is_rejected_by_call_tool() -> None:
    result = await call_tool("research_templates_list", {})
    assert isinstance(result, CallToolResult)
    assert result.isError is True
    payload = json.loads(result.content[0].text)
    assert payload["code"] == "invalid_argument"
    assert payload["source"] == "tube_bridge"
    assert "not active" in payload["error"].lower()
