"""Frozen persistence and validation contract for user-filled research artifacts."""

from __future__ import annotations

import json
import sqlite3

import pytest

from tube_bridge import research_artifacts
from tube_bridge.errors import InvalidArgumentError, NotFoundError


@pytest.fixture
def isolated_research_store(tmp_path, monkeypatch):
    path = tmp_path / "research-artifacts.db"
    monkeypatch.setattr(research_artifacts, "DB_PATH", path)
    return path


def _source_machine_fields() -> dict:
    return {
        "target": {"type": "video", "video_id": "abcdefghijk"},
        "video_metadata": {
            "title": "Observed title",
            "channel_id": "UC-observed",
            "channel_name": "Observed channel",
        },
        "channel_metadata": {
            "status": "ready",
            "title": "Observed channel",
            "description": "Exact observed channel description",
            "provider": "youtube-data-api",
        },
        "transcript": {
            "status": "ready",
            "transcript_version_id": "trv_sourcehash",
            "source_sha256": "sourcehash",
            "segment_count": 2,
            "first_segment_id": "seg_sourcehash_00000000",
            "last_segment_id": "seg_sourcehash_00000001",
        },
        "source_segments": [
            {
                "segment_id": "seg_sourcehash_00000000",
                "ordinal": 0,
                "start_ms": 0,
                "end_ms": 1000,
                "text": "first",
            },
            {
                "segment_id": "seg_sourcehash_00000001",
                "ordinal": 1,
                "start_ms": 1000,
                "end_ms": 2000,
                "text": "second",
            },
        ],
    }


def test_create_get_list_and_append_only_save(isolated_research_store) -> None:
    created = research_artifacts.create_artifact(
        "structured-source-v1",
        target_type="video",
        target_id="abcdefghijk",
        machine_fields=_source_machine_fields(),
    )
    assert created["revision"] == 1
    assert created["machine_fields"]["channel_metadata"]["description"].startswith("Exact")
    assert created["agent_fields"]["metadata_annotation"]["completion"] == "unfilled"
    assert created["agent_fields"]["content_structure"]["sections"] == []

    agent_fields = created["agent_fields"]
    agent_fields["content_structure"] = {
        "completion": "complete",
        "root_title": "Agent-authored root",
        "root_tags": ["topic/test"],
        "sections": [
            {
                "section_id": "sec-001",
                "ordinal": 0,
                "title": "Agent-authored section",
                "first_segment_id": "seg_sourcehash_00000000",
                "last_segment_id": "seg_sourcehash_00000001",
                "start_ms": 0,
                "end_ms": 2000,
                "tags": ["topic/test/child"],
                "notes": None,
            }
        ],
        "custom_fields": {},
    }
    saved = research_artifacts.save_artifact(
        created["artifact_id"],
        expected_revision=1,
        agent_fields=agent_fields,
        author={"type": "agent", "name": "client-agent"},
    )
    assert saved["revision"] == 2
    assert saved["machine_fields"] == created["machine_fields"]
    assert saved["agent_fields"]["content_structure"]["completion"] == "complete"

    assert research_artifacts.get_artifact(created["artifact_id"], revision=1)["revision"] == 1
    assert research_artifacts.get_artifact(created["artifact_id"])["revision"] == 2
    listed = research_artifacts.list_artifacts(target_type="video", target_id="abcdefghijk")
    assert [item["artifact_id"] for item in listed["artifacts"]] == [created["artifact_id"]]

    with sqlite3.connect(isolated_research_store) as conn:
        rows = conn.execute(
            "SELECT revision FROM artifact_revisions WHERE artifact_id=? ORDER BY revision",
            (created["artifact_id"],),
        ).fetchall()
    assert rows == [(1,), (2,)]


def test_save_rejects_stale_revision_and_machine_field_injection(isolated_research_store) -> None:
    created = research_artifacts.create_artifact(
        "structured-source-v1",
        target_type="video",
        target_id="abcdefghijk",
        machine_fields=_source_machine_fields(),
    )
    research_artifacts.save_artifact(
        created["artifact_id"], 1, created["agent_fields"], author=None
    )
    with pytest.raises(InvalidArgumentError, match="revision"):
        research_artifacts.save_artifact(
            created["artifact_id"], 1, created["agent_fields"], author=None
        )
    with pytest.raises(InvalidArgumentError, match="agent_fields"):
        research_artifacts.save_artifact(
            created["artifact_id"],
            2,
            {"agent_fields": created["agent_fields"], "machine_fields": {}},
            author=None,
        )


def test_complete_structure_requires_exact_ordered_segment_coverage(isolated_research_store) -> None:
    created = research_artifacts.create_artifact(
        "structured-source-v1",
        target_type="video",
        target_id="abcdefghijk",
        machine_fields=_source_machine_fields(),
    )
    invalid = created["agent_fields"]
    invalid["content_structure"] = {
        "completion": "complete",
        "root_title": "Incomplete",
        "root_tags": [],
        "sections": [
            {
                "section_id": "sec-001",
                "ordinal": 0,
                "title": "Only the second segment",
                "first_segment_id": "seg_sourcehash_00000001",
                "last_segment_id": "seg_sourcehash_00000001",
                "start_ms": 1000,
                "end_ms": 2000,
                "tags": [],
                "notes": None,
            }
        ],
        "custom_fields": {},
    }
    with pytest.raises(InvalidArgumentError, match="cover"):
        research_artifacts.save_artifact(
            created["artifact_id"], 1, invalid, author=None
        )


def test_missing_artifact_is_typed_not_found(isolated_research_store) -> None:
    with pytest.raises(NotFoundError):
        research_artifacts.get_artifact("rart_missing")


def test_json_and_coding_row_csv_export(isolated_research_store) -> None:
    machine = {
        "target": {"type": "corpus", "corpus_id": "sample"},
        "corpus_snapshot": {"corpus_id": "sample", "video_ids": ["abcdefghijk"]},
        "sources": [{"video_id": "abcdefghijk", "title": "Source title"}],
    }
    created = research_artifacts.create_artifact(
        "corpus-study-v1", "corpus", "sample", machine
    )
    fields = created["agent_fields"]
    fields["coding_rows"] = {
        "completion": "complete",
        "rows": [
            {
                "row_id": "row-1",
                "video_id": "abcdefghijk",
                "start_ms": 1000,
                "end_ms": 2000,
                "code_ids": ["code-a"],
                "quotation": "Quoted source text",
            }
        ],
    }
    saved = research_artifacts.save_artifact(created["artifact_id"], 1, fields, None)

    exported_json = research_artifacts.export_artifact(saved["artifact_id"], "json")
    assert json.loads(exported_json["content"])["revision"] == 2
    assert exported_json["mime_type"] == "application/json"

    exported_csv = research_artifacts.export_artifact(saved["artifact_id"], "csv")
    assert "row_id,video_id,start_ms,end_ms,code_ids,quotation" in exported_csv["content"]
    assert "row-1,abcdefghijk,1000,2000,code-a,Quoted source text" in exported_csv["content"]


def test_every_store_operation_closes_its_connection(
    isolated_research_store, monkeypatch
) -> None:
    lifecycle: list[str] = []
    original = research_artifacts._get_conn

    class Spy:
        def __init__(self, conn):
            self._conn = conn
            lifecycle.append("open")

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def close(self):
            lifecycle.append("close")
            return self._conn.close()

    monkeypatch.setattr(research_artifacts, "_get_conn", lambda: Spy(original()))
    created = research_artifacts.create_artifact(
        "structured-source-v1", "video", "abcdefghijk", _source_machine_fields()
    )
    research_artifacts.get_artifact(created["artifact_id"])
    research_artifacts.list_artifacts("video", "abcdefghijk")
    research_artifacts.save_artifact(
        created["artifact_id"], 1, created["agent_fields"], None
    )
    assert lifecycle.count("open") == lifecycle.count("close")
