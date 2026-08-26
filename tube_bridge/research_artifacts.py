"""Local user-filled research artifact templates and append-only persistence.

Tube Bridge owns only template validation, observable machine fields, stable source
references, and local revision storage. It never fills agent-owned research fields.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
import csv
from importlib import resources
import io
import json
import sqlite3
import time
import uuid
from pathlib import Path

import jsonschema

from .cache import CACHE_DIR
from .errors import ErrorSource, InvalidArgumentError, NotFoundError


DB_PATH = CACHE_DIR / "research-artifacts.db"
_TEMPLATE_PACKAGE = "tube_bridge"
_TEMPLATE_DIRECTORY = "research_templates"
_TEMPLATE_FILES = {
    "structured-source-v1": "structured-source-v1.json",
    "corpus-study-v1": "corpus-study-v1.json",
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_template(template_id: str) -> dict:
    """Load one bundled immutable template definition."""
    filename = _TEMPLATE_FILES.get(template_id)
    if filename is None:
        raise InvalidArgumentError(f"Unknown research template: {template_id}")
    path = resources.files(_TEMPLATE_PACKAGE).joinpath(_TEMPLATE_DIRECTORY, filename)
    definition = json.loads(path.read_text(encoding="utf-8"))
    if definition.get("template_id") != template_id:
        raise RuntimeError(f"Research template identity mismatch: {template_id}")
    return copy.deepcopy(definition)


def list_templates() -> dict:
    """List bundled user-fillable template definitions without instantiating them."""
    templates = []
    for template_id in sorted(_TEMPLATE_FILES):
        definition = load_template(template_id)
        templates.append(
            {
                "template_id": template_id,
                "template_version": definition["template_version"],
                "description": definition["description"],
                "target_types": definition["target_types"],
            }
        )
    return {"templates": templates, "total": len(templates)}


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS artifacts ("
            "artifact_id TEXT PRIMARY KEY, template_id TEXT NOT NULL, "
            "template_version INTEGER NOT NULL, target_type TEXT NOT NULL, "
            "target_id TEXT NOT NULL, created_at REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS artifact_revisions ("
            "artifact_id TEXT NOT NULL, revision INTEGER NOT NULL, "
            "machine_fields_json TEXT NOT NULL, agent_fields_json TEXT NOT NULL, "
            "author_json TEXT, created_at REAL NOT NULL, "
            "PRIMARY KEY (artifact_id, revision), "
            "FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id))"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_artifacts_target "
            "ON artifacts(target_type, target_id, template_id)"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS artifact_revisions_no_update "
            "BEFORE UPDATE ON artifact_revisions BEGIN "
            "SELECT RAISE(ABORT, 'artifact revisions are append-only'); END"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS artifact_revisions_no_delete "
            "BEFORE DELETE ON artifact_revisions BEGIN "
            "SELECT RAISE(ABORT, 'artifact revisions are append-only'); END"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS artifacts_no_update "
            "BEFORE UPDATE ON artifacts BEGIN "
            "SELECT RAISE(ABORT, 'artifact identities are immutable'); END"
        )
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS artifacts_no_delete "
            "BEFORE DELETE ON artifacts BEGIN "
            "SELECT RAISE(ABORT, 'artifact identities are immutable'); END"
        )
        conn.commit()
        return conn
    except Exception:
        conn.rollback()
        conn.close()
        raise


@contextmanager
def _connection():
    conn = _get_conn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _validate_target(definition: dict, target_type: str, target_id: str) -> None:
    if target_type not in definition.get("target_types", []):
        raise InvalidArgumentError(
            f"Template {definition['template_id']} does not support target type {target_type!r}"
        )
    if not isinstance(target_id, str) or not target_id.strip():
        raise InvalidArgumentError("target_id must be a non-empty string")


def _artifact_payload(identity: sqlite3.Row, revision: sqlite3.Row) -> dict:
    return {
        "schema": "tube-bridge.research-artifact.v1",
        "artifact_id": identity["artifact_id"],
        "template_id": identity["template_id"],
        "template_version": identity["template_version"],
        "revision": revision["revision"],
        "target": {
            "type": identity["target_type"],
            "id": identity["target_id"],
        },
        "field_ownership": {
            "machine_fields": "tube_bridge_read_only",
            "agent_fields": "user_or_agent_editable",
        },
        "machine_fields": json.loads(revision["machine_fields_json"]),
        "agent_fields": json.loads(revision["agent_fields_json"]),
        "author": json.loads(revision["author_json"]) if revision["author_json"] else None,
        "created_at": revision["created_at"],
    }


def create_artifact(
    template_id: str,
    target_type: str,
    target_id: str,
    machine_fields: dict,
) -> dict:
    """Create revision 1 with machine fields and an untouched agent scaffold."""
    definition = load_template(template_id)
    _validate_target(definition, target_type, target_id)
    if not isinstance(machine_fields, dict):
        raise InvalidArgumentError("machine_fields must be an object")
    artifact_id = f"rart_{uuid.uuid4().hex}"
    created_at = time.time()
    agent_fields = copy.deepcopy(definition["agent_fields"])
    try:
        machine_json = _canonical_json(machine_fields)
        agent_json = _canonical_json(agent_fields)
    except (TypeError, ValueError) as error:
        raise InvalidArgumentError("Artifact fields must be JSON serializable") from error

    with _connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                template_id,
                int(definition["template_version"]),
                target_type,
                target_id,
                created_at,
            ),
        )
        conn.execute(
            "INSERT INTO artifact_revisions VALUES (?, ?, ?, ?, ?, ?)",
            (artifact_id, 1, machine_json, agent_json, None, created_at),
        )
        conn.commit()
    return get_artifact(artifact_id, revision=1)


def _get_identity(conn: sqlite3.Connection, artifact_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(
            f"Research artifact not found: {artifact_id}",
            source=ErrorSource.TUBE_BRIDGE,
        )
    return row


def get_artifact(artifact_id: str, revision: int | None = None) -> dict:
    """Read one immutable artifact revision; latest when revision is omitted."""
    if revision is not None and (
        isinstance(revision, bool) or not isinstance(revision, int) or revision < 1
    ):
        raise InvalidArgumentError("revision must be a positive integer")
    with _connection() as conn:
        identity = _get_identity(conn, artifact_id)
        if revision is None:
            revision_row = conn.execute(
                "SELECT * FROM artifact_revisions WHERE artifact_id=? "
                "ORDER BY revision DESC LIMIT 1",
                (artifact_id,),
            ).fetchone()
        else:
            revision_row = conn.execute(
                "SELECT * FROM artifact_revisions WHERE artifact_id=? AND revision=?",
                (artifact_id, revision),
            ).fetchone()
        if revision_row is None:
            raise NotFoundError(
                f"Research artifact revision not found: {artifact_id}@{revision}",
                source=ErrorSource.TUBE_BRIDGE,
            )
        return _artifact_payload(identity, revision_row)


def list_artifacts(
    target_type: str, target_id: str, template_id: str | None = None
) -> dict:
    """List latest artifact revisions attached to one source or corpus target."""
    if not isinstance(target_type, str) or not target_type:
        raise InvalidArgumentError("target_type must be a non-empty string")
    if not isinstance(target_id, str) or not target_id:
        raise InvalidArgumentError("target_id must be a non-empty string")
    params: list[object] = [target_type, target_id]
    where = "a.target_type=? AND a.target_id=?"
    if template_id is not None:
        load_template(template_id)
        where += " AND a.template_id=?"
        params.append(template_id)
    with _connection() as conn:
        rows = conn.execute(
            f"SELECT a.*, MAX(r.revision) AS latest_revision "
            f"FROM artifacts a JOIN artifact_revisions r ON r.artifact_id=a.artifact_id "
            f"WHERE {where} GROUP BY a.artifact_id ORDER BY a.created_at, a.artifact_id",
            params,
        ).fetchall()
    return {
        "target": {"type": target_type, "id": target_id},
        "artifacts": [
            {
                "artifact_id": row["artifact_id"],
                "template_id": row["template_id"],
                "template_version": row["template_version"],
                "revision": row["latest_revision"],
                "created_at": row["created_at"],
            }
            for row in rows
        ],
        "total": len(rows),
    }


def _deep_merge(current: object, supplied: object) -> object:
    """Apply JSON Merge Patch-like object recursion; arrays/scalars replace."""
    if isinstance(current, dict) and isinstance(supplied, dict):
        merged = copy.deepcopy(current)
        for key, value in supplied.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged
    return copy.deepcopy(supplied)


def _merge_agent_fields(current: dict, supplied: dict, definition: dict) -> dict:
    if not isinstance(supplied, dict):
        raise InvalidArgumentError("agent_fields must be an object")
    allowed = set(definition["agent_fields"])
    unknown = set(supplied) - allowed
    if unknown:
        raise InvalidArgumentError(
            f"agent_fields contains unsupported fields: {sorted(unknown)}"
        )
    return _deep_merge(current, supplied)


def _validate_complete_content(machine_fields: dict, agent_fields: dict) -> None:
    structure = agent_fields.get("content_structure")
    if not isinstance(structure, dict) or structure.get("completion") != "complete":
        return
    source_segments = machine_fields.get("source_segments")
    if not isinstance(source_segments, list) or not source_segments:
        raise InvalidArgumentError(
            "A complete content structure cannot cover an unavailable transcript"
        )
    sections = structure.get("sections")
    if not isinstance(sections, list) or not sections:
        raise InvalidArgumentError("Complete content sections must cover every source segment")

    index = {
        segment.get("segment_id"): position
        for position, segment in enumerate(source_segments)
        if isinstance(segment, dict)
    }
    covered: list[int] = []
    for expected_ordinal, section in enumerate(sections):
        if not isinstance(section, dict):
            raise InvalidArgumentError("Every content section must be an object")
        if section.get("ordinal") != expected_ordinal:
            raise InvalidArgumentError("Content section ordinals must be dense and ordered")
        first = index.get(section.get("first_segment_id"))
        last = index.get(section.get("last_segment_id"))
        if first is None or last is None or first > last:
            raise InvalidArgumentError("Content section source references are invalid")
        if section.get("start_ms") != source_segments[first].get("start_ms"):
            raise InvalidArgumentError("Content section start_ms must match its first segment")
        if section.get("end_ms") != source_segments[last].get("end_ms"):
            raise InvalidArgumentError("Content section end_ms must match its last segment")
        covered.extend(range(first, last + 1))
    if covered != list(range(len(source_segments))):
        raise InvalidArgumentError(
            "Complete content sections must cover every source segment exactly once in order"
        )


def _machine_source_catalog(template_id: str, machine_fields: dict) -> dict[str, dict]:
    if template_id == "structured-source-v1":
        target = machine_fields.get("target")
        transcript = machine_fields.get("transcript")
        segments = machine_fields.get("source_segments")
        video_id = target.get("video_id") if isinstance(target, dict) else None
        if (
            isinstance(video_id, str)
            and isinstance(transcript, dict)
            and transcript.get("status") == "ready"
            and isinstance(segments, list)
            and segments
        ):
            return {
                video_id: {
                    "transcript_version_id": transcript.get("transcript_version_id"),
                    "segments": segments,
                }
            }
        return {}
    return {
        item["video_id"]: item["source_reference"]
        for item in machine_fields.get("sources", [])
        if isinstance(item, dict)
        and isinstance(item.get("video_id"), str)
        and isinstance(item.get("source_reference"), dict)
    }


def _validate_source_ref(
    source_ref: dict, catalog: dict[str, dict], label: str
) -> None:
    video_id = source_ref.get("video_id")
    source_reference = catalog.get(video_id)
    if not isinstance(source_reference, dict):
        raise InvalidArgumentError(
            f"{label} source reference has no selected transcript for video_id {video_id!r}"
        )
    if source_ref.get("transcript_version_id") != source_reference.get(
        "transcript_version_id"
    ):
        raise InvalidArgumentError(
            f"{label} transcript_version_id does not match the selected source reference"
        )
    segments = source_reference.get("segments")
    if not isinstance(segments, list) or not segments:
        raise InvalidArgumentError(f"{label} source reference has no segments")
    index = {
        segment.get("segment_id"): position
        for position, segment in enumerate(segments)
        if isinstance(segment, dict)
    }
    first = index.get(source_ref.get("first_segment_id"))
    last = index.get(source_ref.get("last_segment_id"))
    if first is None or last is None or first > last:
        raise InvalidArgumentError(f"{label} segment source reference is invalid")
    if source_ref.get("start_ms") != segments[first].get("start_ms"):
        raise InvalidArgumentError(
            f"{label} start_ms must match its first source segment"
        )
    if source_ref.get("end_ms") != segments[last].get("end_ms"):
        raise InvalidArgumentError(
            f"{label} end_ms must match its last source segment"
        )


def _validate_corpus_rows(machine_fields: dict, agent_fields: dict) -> None:
    rows = agent_fields.get("coding_rows", {}).get("rows", [])
    source_ids = {
        item.get("video_id")
        for item in machine_fields.get("sources", [])
        if isinstance(item, dict)
    }
    for row in rows:
        if row.get("video_id") not in source_ids:
            raise InvalidArgumentError("Coding row video_id must belong to the corpus snapshot")
        start_ms, end_ms = row.get("start_ms"), row.get("end_ms")
        if (
            isinstance(start_ms, bool)
            or isinstance(end_ms, bool)
            or not isinstance(start_ms, int)
            or not isinstance(end_ms, int)
            or start_ms < 0
            or end_ms < start_ms
        ):
            raise InvalidArgumentError("Coding row timestamp range is invalid")


def _validate_all_source_refs(
    template_id: str, machine_fields: dict, agent_fields: dict
) -> None:
    catalog = _machine_source_catalog(template_id, machine_fields)
    refs: list[tuple[str, dict]] = []
    if template_id == "structured-source-v1":
        refs.extend(
            ("Source annotation evidence", ref)
            for ref in agent_fields.get("source_annotation", {}).get(
                "evidence_refs", []
            )
        )
    elif template_id == "corpus-study-v1":
        _validate_corpus_rows(machine_fields, agent_fields)
        for row in agent_fields.get("coding_rows", {}).get("rows", []):
            reference_keys = (
                "transcript_version_id",
                "first_segment_id",
                "last_segment_id",
            )
            supplied = [row.get(key) for key in reference_keys]
            if any(value is not None for value in supplied):
                if not all(isinstance(value, str) and value for value in supplied):
                    raise InvalidArgumentError(
                        "Coding row source reference requires transcript and both segment IDs"
                    )
                refs.append(("Coding row", row))
        for group in agent_fields.get("channel_groups", {}).get("groups", []):
            refs.extend(
                ("Channel group evidence", ref)
                for ref in group.get("evidence_refs", [])
            )
        for cluster in agent_fields.get("duplicate_and_lineage", {}).get(
            "clusters", []
        ):
            refs.extend(
                ("Lineage source", ref) for ref in cluster.get("source_refs", [])
            )
            refs.extend(
                ("Lineage evidence", ref)
                for ref in cluster.get("evidence_refs", [])
            )
        for entry in agent_fields.get("evidence_ledger", {}).get("entries", []):
            refs.extend(
                ("Evidence ledger", ref) for ref in entry.get("source_refs", [])
            )
    for label, source_ref in refs:
        _validate_source_ref(source_ref, catalog, label)


def _validate_agent_fields(
    definition: dict, machine_fields: dict, agent_fields: dict
) -> None:
    schema = definition.get("agent_fields_schema")
    if not isinstance(schema, dict):
        raise RuntimeError(
            f"Research template lacks agent_fields_schema: {definition['template_id']}"
        )
    try:
        jsonschema.validate(instance=agent_fields, schema=schema)
    except jsonschema.ValidationError as error:
        raise InvalidArgumentError(
            f"agent_fields schema validation error: {error.message}"
        ) from error

    template_id = definition["template_id"]
    if template_id == "structured-source-v1":
        _validate_complete_content(machine_fields, agent_fields)
    _validate_all_source_refs(template_id, machine_fields, agent_fields)


def save_artifact(
    artifact_id: str,
    expected_revision: int,
    agent_fields: dict,
    author: dict | None,
) -> dict:
    """Append a user/agent-authored revision with optimistic concurrency."""
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision < 1
    ):
        raise InvalidArgumentError("expected_revision must be a positive integer")
    if author is not None and not isinstance(author, dict):
        raise InvalidArgumentError("author must be an object or null")

    with _connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        identity = _get_identity(conn, artifact_id)
        latest = conn.execute(
            "SELECT * FROM artifact_revisions WHERE artifact_id=? "
            "ORDER BY revision DESC LIMIT 1",
            (artifact_id,),
        ).fetchone()
        if latest["revision"] != expected_revision:
            raise InvalidArgumentError(
                f"Artifact revision changed: expected {expected_revision}, "
                f"latest is {latest['revision']}"
            )
        definition = load_template(identity["template_id"])
        current_agent = json.loads(latest["agent_fields_json"])
        merged_agent = _merge_agent_fields(current_agent, agent_fields, definition)
        machine_fields = json.loads(latest["machine_fields_json"])
        _validate_agent_fields(definition, machine_fields, merged_agent)
        try:
            agent_json = _canonical_json(merged_agent)
            author_json = _canonical_json(author) if author is not None else None
        except (TypeError, ValueError) as error:
            raise InvalidArgumentError("agent_fields and author must be JSON serializable") from error
        next_revision = expected_revision + 1
        created_at = time.time()
        conn.execute(
            "INSERT INTO artifact_revisions VALUES (?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                next_revision,
                latest["machine_fields_json"],
                agent_json,
                author_json,
                created_at,
            ),
        )
        conn.commit()
    return get_artifact(artifact_id, revision=next_revision)


def export_artifact(artifact_id: str, format: str = "json") -> dict:
    """Serialize a stored artifact without changing or interpreting it."""
    artifact = get_artifact(artifact_id)
    if format == "json":
        return {
            "artifact_id": artifact_id,
            "revision": artifact["revision"],
            "format": "json",
            "mime_type": "application/json",
            "content": json.dumps(artifact, ensure_ascii=False, indent=2),
        }
    if format != "csv":
        raise InvalidArgumentError("format must be json or csv")
    if artifact["template_id"] != "corpus-study-v1":
        raise InvalidArgumentError("CSV export is defined only for corpus-study-v1")
    rows = artifact["agent_fields"].get("coding_rows", {}).get("rows", [])
    fieldnames = [
        "row_id",
        "video_id",
        "start_ms",
        "end_ms",
        "code_ids",
        "quotation",
        "transcript_version_id",
        "first_segment_id",
        "last_segment_id",
        "context_before",
        "context_after",
        "agent_note",
        "confidence",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        rendered = dict(row)
        rendered["code_ids"] = "|".join(str(value) for value in row.get("code_ids", []))
        writer.writerow(rendered)
    return {
        "artifact_id": artifact_id,
        "revision": artifact["revision"],
        "format": "csv",
        "mime_type": "text/csv",
        "content": output.getvalue(),
    }
