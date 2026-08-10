"""Frozen pre-implementation contract for the Corpus v2 persisted format."""

from __future__ import annotations

import hashlib
import importlib.metadata
import re
import json
import math
import sqlite3
import struct
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest
import sqlite_vec


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = PROJECT_ROOT / "skills" / "tube-bridge-research"
CONTRACT_PATH = SKILL_ROOT / "references" / "30-corpus-storage.md"
SCHEMA_PATH = SKILL_ROOT / "assets" / "contracts" / "corpus-v2-schema.sql"

REQUIRED_TABLES = {
    "corpus_schema_meta",
    "corpus_runtime_state",
    "corpora",
    "transcript_versions",
    "transcript_fetches",
    "source_segments",
    "projection_versions",
    "projection_nodes",
    "projection_relations",
    "corpus_generations",
    "corpus_generation_members",
    "index_versions",
    "index_projection_members",
    "search_documents",
    "search_documents_fts",
    "migration_runs",
    "migration_items",
    "v2_mutations",
}

HEX = {
    "fetch": "1" * 32,
    "projection": "2" * 32,
    "root": "3" * 32,
    "passage": "4" * 32,
    "generation": "5" * 32,
    "lexical": "6" * 32,
    "dense": "7" * 32,
    "migration": "8" * 32,
}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _ms(seconds: str) -> int:
    return int(
        (Decimal(seconds) * Decimal(1000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


_VEC_TABLE_RE = re.compile(r"^vec_[0-9a-f]{32}(?:_.*)?$")
_VEC_WRITE_SCOPE: dict[int, bool] = {}


@contextmanager
def _vec_write_scope(connection: sqlite3.Connection):
    key = id(connection)
    previous = _VEC_WRITE_SCOPE.get(key, False)
    _VEC_WRITE_SCOPE[key] = True
    try:
        yield
    finally:
        _VEC_WRITE_SCOPE[key] = previous


def _install_vec_authorizer(connection: sqlite3.Connection) -> None:
    protected_actions = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_CREATE_VTABLE,
        sqlite3.SQLITE_DROP_VTABLE,
    }

    def authorize(action: int, arg1: str | None, _arg2, _db, _source) -> int:
        target = arg1 or ""
        if (
            action in protected_actions
            and _VEC_TABLE_RE.fullmatch(target)
            and not _VEC_WRITE_SCOPE.get(id(connection), False)
        ):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorize)


def _apply_schema(*, with_vec: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    if with_vec:
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.enable_load_extension(False)
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.create_function(
        "tube_validate_source", 1, lambda transcript_id: _validate_source(connection, transcript_id)
    )
    connection.create_function(
        "tube_validate_projection", 1,
        lambda projection_id: _validate_projection_snapshot(connection, projection_id),
    )
    connection.create_function(
        "tube_validate_index", 1,
        lambda index_id: _validate_index_snapshot(connection, index_id),
    )
    connection.create_function(
        "tube_validate_generation", 2,
        lambda corpus_id, generation_id: _validate_generation_snapshot(
            connection, corpus_id, generation_id
        ),
    )
    _install_vec_authorizer(connection)
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _validate_source(connection: sqlite3.Connection, transcript_id: str) -> str:
    row = connection.execute(
        "SELECT source_sha256,video_id,selected_language,track_kind,segment_count,start_ms,end_ms "
        "FROM transcript_versions WHERE transcript_version_id=?",
        (transcript_id,),
    ).fetchone()
    _require(row is not None, "source row missing")
    source_hash, video_id, language, track_kind, count, start_ms, end_ms = row
    segments = [
        {
            "ordinal": item[0],
            "start_ms": item[1],
            "end_ms": item[2],
            "text": item[3],
        }
        for item in connection.execute(
            "SELECT segment_ordinal,start_ms,end_ms,text_original FROM source_segments "
            "WHERE transcript_version_id=? ORDER BY segment_ordinal",
            (transcript_id,),
        )
    ]
    _require(len(segments) == count, "source segment count mismatch")
    _require(
        [item["ordinal"] for item in segments] == list(range(count)),
        "source ordinals are not dense",
    )
    _require(segments[0]["start_ms"] == start_ms, "source start mismatch")
    _require(segments[-1]["end_ms"] == end_ms, "source end mismatch")
    _require(
        all(
            following["start_ms"] >= current["start_ms"]
            for current, following in zip(segments, segments[1:])
        ),
        "source starts are not monotonic",
    )
    envelope = {
        "schema": "tube-bridge.transcript-source.v2",
        "video_id": video_id,
        "selected_language": language,
        "track_kind": track_kind,
        "segments": segments,
    }
    _require(_sha(envelope) == source_hash, "source hash mismatch")
    _require(transcript_id == f"trv_{source_hash}", "source ID mismatch")
    return _sha(
        {
            "schema": "tube-bridge.source-validation.v2",
            "transcript_version_id": transcript_id,
            "source_sha256": source_hash,
            "checks": "pass",
        }
    )


def _insert_source(connection: sqlite3.Connection) -> tuple[str, str, str]:
    segments = [
        {"ordinal": 0, "start_ms": 0, "end_ms": 500, "text": "frozen source"},
        {"ordinal": 1, "start_ms": 500, "end_ms": 1000, "text": "words"},
    ]
    envelope = {
        "schema": "tube-bridge.transcript-source.v2",
        "video_id": "video123",
        "selected_language": "en",
        "track_kind": "generated",
        "segments": segments,
    }
    source_hash = _sha(envelope)
    transcript_id = f"trv_{source_hash}"
    fetch_id = f"fetch_{HEX['fetch']}"
    connection.execute(
        "INSERT INTO transcript_versions "
        "(transcript_version_id,source_sha256,source_schema_version,video_id,"
        "selected_language,track_kind,segment_count,start_ms,end_ms,status,created_at_ms) "
        "VALUES (?, ?, 2, ?, ?, ?, ?, ?, ?, 'building', ?)",
        (
            transcript_id,
            source_hash,
            "video123",
            "en",
            "generated",
            len(segments),
            0,
            1000,
            1,
        ),
    )
    connection.execute(
        "INSERT INTO transcript_fetches "
        "(fetch_id, transcript_version_id, provider, requested_language, "
        "selection_policy_version, selection_reason, retrieval_mode, fetched_at_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, 'live', ?)",
        (
            fetch_id,
            transcript_id,
            "youtube-transcript-api",
            "en",
            "track-selection-v2",
            "explicit-language",
            1,
        ),
    )
    for segment in segments:
        connection.execute(
            "INSERT INTO source_segments VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                transcript_id,
                source_hash,
                segment["ordinal"],
                f"seg_{source_hash}_{segment['ordinal']:08d}",
                segment["start_ms"],
                segment["end_ms"],
                segment["text"],
            ),
        )
    validation_hash = _validate_source(connection, transcript_id)
    connection.execute(
        "UPDATE transcript_versions SET status='ready',validated_at_ms=2,"
        "validation_sha256=? WHERE transcript_version_id=?",
        (validation_hash, transcript_id),
    )
    return transcript_id, source_hash, fetch_id


def _insert_ready_projection(
    connection: sqlite3.Connection, transcript_id: str, source_hash: str
) -> str:
    projection_id = f"prj_{HEX['projection']}"
    config = {"passage_policy": "contiguous-source-v1"}
    build_key = _sha(
        {
            "schema": "tube-bridge.projection-build.v2",
            "source_sha256": source_hash,
            "processor_name": "test-processor",
            "processor_version": "1",
            "model_name": None,
            "model_version": None,
            "processing_config_sha256": _sha(config),
        }
    )
    connection.execute(
        "INSERT INTO projection_versions "
        "(projection_version_id, corpus_id, video_id, transcript_version_id, "
        "source_sha256, projection_schema_version, build_key_sha256, "
        "processor_name, processor_version, processing_config_json, "
        "processing_config_sha256, status, created_at_ms) "
        "VALUES (?, 'demo', 'video123', ?, ?, 2, ?, 'test-processor', '1', ?, ?, 'building', 2)",
        (
            projection_id,
            transcript_id,
            source_hash,
            build_key,
            _canonical_json(config).decode(),
            _sha(config),
        ),
    )
    root_id = f"node_{HEX['root']}"
    passage_id = f"node_{HEX['passage']}"
    connection.execute(
        "INSERT INTO projection_nodes "
        "(projection_version_id, node_id, node_kind, parent_node_id, ordinal, "
        "start_segment_ordinal, end_segment_ordinal, start_ms, end_ms, "
        "summary_text, confidence_label, provenance_json) "
        "VALUES (?, ?, 'video', NULL, 0, 0, 1, 0, 1000, ?, 'observed', '{}')",
        (projection_id, root_id, "frozen source words"),
    )
    connection.execute(
        "INSERT INTO projection_nodes "
        "(projection_version_id, node_id, node_kind, parent_node_id, ordinal, "
        "start_segment_ordinal, end_segment_ordinal, start_ms, end_ms, "
        "normalized_text, confidence_label, provenance_json) "
        "VALUES (?, ?, 'passage', ?, 0, 0, 1, 0, 1000, ?, 'observed', '{}')",
        (projection_id, passage_id, root_id, "frozen source\nwords"),
    )
    connection.execute(
        "UPDATE projection_versions SET status='ready', completed_at_ms=3 "
        "WHERE projection_version_id=?",
        (projection_id,),
    )
    return projection_id


def _expected_documents(
    connection: sqlite3.Connection, projection_id: str, index_kind: str
) -> list[dict]:
    documents: list[dict] = []
    nodes = connection.execute(
        "SELECT node_id,node_kind,start_segment_ordinal,end_segment_ordinal,"
        "start_ms,end_ms,title,normalized_text,summary_text "
        "FROM projection_nodes WHERE projection_version_id=? ORDER BY start_ms,node_kind,node_id",
        (projection_id,),
    ).fetchall()
    transcript_id = connection.execute(
        "SELECT transcript_version_id FROM projection_versions WHERE projection_version_id=?",
        (projection_id,),
    ).fetchone()[0]
    for node_id, kind, first, last, start_ms, end_ms, title, normalized, summary in nodes:
        source_span = "\n".join(
            row[0]
            for row in connection.execute(
                "SELECT text_original FROM source_segments "
                "WHERE transcript_version_id=? AND segment_ordinal BETWEEN ? AND ? "
                "ORDER BY segment_ordinal",
                (transcript_id, first, last),
            )
        )

        def add(role: str, text: str) -> None:
            documents.append(
                {
                    "document_id": f"doc_{node_id[5:]}_{role}",
                    "projection_version_id": projection_id,
                    "node_id": node_id,
                    "text_role": role,
                    "text": text,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                }
            )

        if index_kind == "lexical":
            if kind == "passage":
                add("source_span", source_span)
                if normalized is not None and normalized.encode() != source_span.encode():
                    add("normalized", normalized)
            if title:
                add("title", title)
            if kind in {"video", "chapter", "topic"} and summary:
                add("summary", summary)
        else:
            if kind == "passage":
                if normalized is not None and normalized.encode() != source_span.encode():
                    add("normalized", normalized)
                else:
                    add("source_span", source_span)
            if kind in {"video", "chapter", "topic"} and summary:
                add("summary", summary)
    return sorted(documents, key=lambda item: item["document_id"])


def _document_manifest(documents: list[dict]) -> list[dict]:
    return [
        {
            "document_id": item["document_id"],
            "projection_version_id": item["projection_version_id"],
            "node_id": item["node_id"],
            "text_role": item["text_role"],
            "start_ms": item["start_ms"],
            "end_ms": item["end_ms"],
            "text_sha256": hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
        }
        for item in sorted(documents, key=lambda item: item["document_id"])
    ]


def _normalize_vector(values: list[float], dimension: int) -> list[float]:
    _require(len(values) == dimension, "embedding dimension mismatch")
    _require(all(math.isfinite(value) for value in values), "non-finite embedding")
    norm = math.sqrt(sum(float(value) * float(value) for value in values))
    _require(norm > 0.0, "zero-norm embedding")
    normalized64 = [float(value) / norm for value in values]
    packed = struct.pack(f"<{dimension}f", *normalized64)
    normalized32 = list(struct.unpack(f"<{dimension}f", packed))
    _require(
        abs(math.sqrt(sum(value * value for value in normalized32)) - 1.0) <= 1e-5,
        "float32 normalized embedding is outside tolerance",
    )
    return normalized32


def _vector_bytes(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _vector_manifest(documents: list[dict], vector: list[float]) -> list[dict]:
    digest = hashlib.sha256(_vector_bytes(vector)).hexdigest()
    return [
        {"document_id": item["document_id"], "vector_sha256": digest}
        for item in sorted(documents, key=lambda item: item["document_id"])
    ]


def _validate_index_snapshot(connection: sqlite3.Connection, index_id: str) -> str:
    row = connection.execute(
        "SELECT index_kind,generation_id,build_key_sha256,config_json,config_sha256,"
        "document_manifest_sha256,vector_manifest_sha256,embedding_model,"
        "embedding_model_version,embedding_dimension,distance_metric,vector_dtype,"
        "l2_normalized,sqlite_vec_version,vector_table_name FROM index_versions "
        "WHERE index_version_id=?",
        (index_id,),
    ).fetchone()
    _require(row is not None, "index row missing")
    (
        kind,
        generation_id,
        build_key,
        config_json,
        config_hash,
        document_hash,
        vector_hash,
        model,
        model_version,
        dimension,
        metric,
        dtype,
        l2_normalized,
        vec_version,
        vector_table,
    ) = row
    config = json.loads(config_json)
    _require(_sha(config) == config_hash, "index config hash mismatch")
    _require(
        build_key == _sha(
            {
                "schema": "tube-bridge.index-build.v2",
                "generation_id": generation_id,
                "index_kind": kind,
                "config_sha256": config_hash,
            }
        ),
        "index build key mismatch",
    )
    if kind == "dense":
        _require(
            config == {
                "model": model,
                "model_version": model_version,
                "dimension": dimension,
                "dtype": dtype,
                "distance_metric": metric,
                "l2_normalized": bool(l2_normalized),
                "sqlite_vec_version": vec_version,
            },
            "dense typed metadata differs from config",
        )
    else:
        _require(config == {"tokenizer": "unicode61"}, "lexical config mismatch")
    projection_ids = [
        item[0]
        for item in connection.execute(
            "SELECT projection_version_id FROM index_projection_members "
            "WHERE index_version_id=? ORDER BY projection_version_id",
            (index_id,),
        )
    ]
    expected = sorted(
        [
            document
            for projection_id in projection_ids
            for document in _expected_documents(connection, projection_id, kind)
        ],
        key=lambda item: item["document_id"],
    )
    actual = [
        {
            "document_id": item[0],
            "projection_version_id": item[1],
            "node_id": item[2],
            "text_role": item[3],
            "text": item[4],
            "start_ms": item[5],
            "end_ms": item[6],
        }
        for item in connection.execute(
            "SELECT document_id,projection_version_id,node_id,text_role,text,start_ms,end_ms "
            "FROM search_documents WHERE index_version_id=? ORDER BY document_id",
            (index_id,),
        )
    ]
    _require(actual == expected, "search document set mismatch")
    _require(
        _sha(_document_manifest(actual)) == document_hash,
        "document manifest mismatch",
    )

    if kind == "dense":
        _require(
            vector_table is not None and dimension is not None,
            "dense table metadata missing",
        )
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (vector_table,)
        ).fetchone()[0]
        _require(
            " ".join(sql.lower().split())
            == (
                f"create virtual table {vector_table} "
                f"using vec0(embedding float[{dimension}] distance_metric=cosine)"
            ),
            "vec0 DDL mismatch",
        )
        rows = connection.execute(
            f"SELECT rowid,embedding FROM {vector_table} ORDER BY rowid"
        ).fetchall()
        document_rows = connection.execute(
            "SELECT row_id,document_id FROM search_documents "
            "WHERE index_version_id=? ORDER BY row_id",
            (index_id,),
        ).fetchall()
        _require(
            [row[0] for row in rows] == [row[0] for row in document_rows],
            "vector row IDs differ from dense documents",
        )
        vector_manifest = []
        for (_, blob), (_, document_id) in zip(rows, document_rows):
            vector = struct.unpack(f"<{dimension}f", blob)
            _require(all(math.isfinite(value) for value in vector), "non-finite vector")
            _require(
                abs(math.sqrt(sum(value * value for value in vector)) - 1.0) <= 1e-5,
                "stored vector is not unit norm",
            )
            vector_manifest.append(
                {
                    "document_id": document_id,
                    "vector_sha256": hashlib.sha256(blob).hexdigest(),
                }
            )
        _require(
            _sha(sorted(vector_manifest, key=lambda item: item["document_id"]))
            == vector_hash,
            "vector manifest mismatch",
        )
    else:
        fts_rows = {
            item[0]
            for item in connection.execute(
                "SELECT rowid FROM search_documents_fts"
            )
        }
        expected_rows = {
            item[0]
            for item in connection.execute(
                "SELECT row_id FROM search_documents WHERE index_version_id=?",
                (index_id,),
            )
        }
        _require(expected_rows <= fts_rows, "FTS rows missing")

    return _sha(
        {
            "schema": "tube-bridge.index-validation.v2",
            "index_version_id": index_id,
            "document_manifest_sha256": document_hash,
            "vector_manifest_sha256": vector_hash,
            "checks": "pass",
        }
    )


def _validate_projection_snapshot(
    connection: sqlite3.Connection, projection_id: str
) -> int:
    row = connection.execute(
        "SELECT source_sha256,processor_name,processor_version,model_name,model_version,"
        "processing_config_json,processing_config_sha256,build_key_sha256,transcript_version_id "
        "FROM projection_versions WHERE projection_version_id=?",
        (projection_id,),
    ).fetchone()
    _require(row is not None, "projection row missing")
    (
        source_hash,
        processor_name,
        processor_version,
        model_name,
        model_version,
        config_json,
        config_hash,
        build_key,
        transcript_id,
    ) = row
    _require(
        _sha(json.loads(config_json)) == config_hash,
        "projection config hash mismatch",
    )
    _require(
        connection.execute(
            "SELECT status FROM transcript_versions WHERE transcript_version_id=?",
            (transcript_id,),
        ).fetchone()
        == ("ready",),
        "projection source is not READY",
    )
    _require(
        build_key
        == _sha(
            {
                "schema": "tube-bridge.projection-build.v2",
                "source_sha256": source_hash,
                "processor_name": processor_name,
                "processor_version": processor_version,
                "model_name": model_name,
                "model_version": model_version,
                "processing_config_sha256": config_hash,
            }
        ),
        "projection build key mismatch",
    )
    return 1


def _validate_generation_snapshot(
    connection: sqlite3.Connection, corpus_id: str, generation_id: str
) -> int:
    row = connection.execute(
        "SELECT source_manifest_sha256,force_run_id,build_key_sha256 "
        "FROM corpus_generations WHERE corpus_id=? AND generation_id=?",
        (corpus_id, generation_id),
    ).fetchone()
    _require(row is not None, "generation row missing")
    source_manifest_hash, force_run_id, build_key = row
    manifest = [
        {
            "video_id": item[0],
            "transcript_version_id": item[1],
            "source_sha256": item[2],
            "projection_version_id": item[3],
        }
        for item in connection.execute(
            "SELECT video_id,transcript_version_id,source_sha256,projection_version_id "
            "FROM corpus_generation_members WHERE corpus_id=? AND generation_id=? "
            "ORDER BY CAST(video_id AS BLOB)",
            (corpus_id, generation_id),
        )
    ]
    _require(
        bool(manifest) and _sha(manifest) == source_manifest_hash,
        "generation source manifest mismatch",
    )
    configs = {
        kind: config_hash
        for kind, config_hash, status in connection.execute(
            "SELECT index_kind,config_sha256,status FROM index_versions "
            "WHERE corpus_id=? AND generation_id=?",
            (corpus_id, generation_id),
        )
        if status == "ready"
    }
    _require(set(configs) == {"lexical", "dense"}, "generation indexes incomplete")
    _require(
        build_key
        == _sha(
            {
                "schema": "tube-bridge.corpus-generation.v2",
                "source_manifest_sha256": source_manifest_hash,
                "lexical_config_sha256": configs["lexical"],
                "dense_config_sha256": configs["dense"],
                "force_run_id": force_run_id,
            }
        ),
        "generation build key mismatch",
    )
    return 1


def _insert_generation_and_indexes(
    connection: sqlite3.Connection,
    transcript_id: str,
    source_hash: str,
    fetch_id: str,
    projection_id: str,
) -> tuple[str, str, str]:
    generation_id = f"gen_{HEX['generation']}"
    lexical_id = f"idx_{HEX['lexical']}"
    dense_id = f"idx_{HEX['dense']}"
    manifest = [
        {
            "video_id": "video123",
            "transcript_version_id": transcript_id,
            "source_sha256": source_hash,
            "projection_version_id": projection_id,
        }
    ]
    source_manifest_hash = _sha(manifest)
    lexical_config = {"tokenizer": "unicode61"}
    dense_config = {
        "model": "test-model",
        "model_version": "1",
        "dimension": 3,
        "dtype": "float32",
        "distance_metric": "cosine",
        "l2_normalized": True,
        "sqlite_vec_version": "0.1.9",
    }
    generation_key = _sha(
        {
            "schema": "tube-bridge.corpus-generation.v2",
            "source_manifest_sha256": source_manifest_hash,
            "lexical_config_sha256": _sha(lexical_config),
            "dense_config_sha256": _sha(dense_config),
            "force_run_id": None,
        }
    )
    connection.execute(
        "INSERT INTO corpus_generations "
        "(generation_id,corpus_id,build_key_sha256,source_manifest_sha256,"
        "force_run_id,status,created_at_ms) "
        "VALUES (?,'demo',?,?,NULL,'building',4)",
        (generation_id, generation_key, source_manifest_hash),
    )
    connection.execute(
        "INSERT INTO corpus_generation_members VALUES "
        "('demo', ?, 'video123', ?, ?, ?, ?)",
        (generation_id, transcript_id, source_hash, fetch_id, projection_id),
    )

    for index_id, kind, config in (
        (lexical_id, "lexical", lexical_config),
        (dense_id, "dense", dense_config),
    ):
        documents = _expected_documents(connection, projection_id, kind)
        document_hash = _sha(_document_manifest(documents))
        vector = _normalize_vector([3.0, 0.0, 0.0], 3)
        vector_hash = _sha(_vector_manifest(documents, vector)) if kind == "dense" else None
        build_key = _sha(
            {
                "schema": "tube-bridge.index-build.v2",
                "generation_id": generation_id,
                "index_kind": kind,
                "config_sha256": _sha(config),
            }
        )
        if kind == "lexical":
            connection.execute(
                "INSERT INTO index_versions "
                "(index_version_id,corpus_id,generation_id,index_kind,build_key_sha256,"
                "status,config_json,config_sha256,document_manifest_sha256,created_at_ms) "
                "VALUES (?,'demo',?,'lexical',?,'building',?,?,?,5)",
                (
                    index_id,
                    generation_id,
                    build_key,
                    _canonical_json(config).decode(),
                    _sha(config),
                    document_hash,
                ),
            )
        else:
            connection.execute(
                "INSERT INTO index_versions "
                "(index_version_id,corpus_id,generation_id,index_kind,build_key_sha256,"
                "status,config_json,config_sha256,document_manifest_sha256,"
                "vector_manifest_sha256,embedding_model,embedding_model_version,"
                "embedding_dimension,distance_metric,vector_dtype,l2_normalized,"
                "sqlite_vec_version,vector_table_name,created_at_ms) "
                "VALUES (?,'demo',?,'dense',?,'building',?,?,?,?,"
                "'test-model','1',3,'cosine','float32',1,'0.1.9',?,5)",
                (
                    index_id,
                    generation_id,
                    build_key,
                    _canonical_json(config).decode(),
                    _sha(config),
                    document_hash,
                    vector_hash,
                    f"vec_{HEX['dense']}",
                ),
            )
        connection.execute(
            "INSERT INTO index_projection_members VALUES ('demo', ?, ?, 'video123', ?)",
            (generation_id, index_id, projection_id),
        )
        row_ids: list[int] = []
        for document in documents:
            cursor = connection.execute(
                "INSERT INTO search_documents "
                "(corpus_id,generation_id,index_version_id,video_id,projection_version_id,"
                "document_id,node_id,text_role,text,start_ms,end_ms) "
                "VALUES ('demo',?,?,'video123',?,?,?,?,?,?,?)",
                (
                    generation_id,
                    index_id,
                    projection_id,
                    document["document_id"],
                    document["node_id"],
                    document["text_role"],
                    document["text"],
                    document["start_ms"],
                    document["end_ms"],
                ),
            )
            row_ids.append(cursor.lastrowid)
        if kind == "dense":
            vector_table = f"vec_{HEX['dense']}"
            with _vec_write_scope(connection):
                connection.execute(
                    f"CREATE VIRTUAL TABLE {vector_table} "
                    "USING vec0(embedding float[3] distance_metric=cosine)"
                )
                for row_id in row_ids:
                    connection.execute(
                        f"INSERT INTO {vector_table}(rowid, embedding) VALUES (?, ?)",
                        (row_id, json.dumps(vector)),
                    )
        validation_hash = _validate_index_snapshot(connection, index_id)
        connection.execute(
            "UPDATE index_versions SET status='ready',validated_at_ms=6,"
            "validation_sha256=?,completed_at_ms=6 WHERE index_version_id=?",
            (validation_hash, index_id),
        )

    connection.execute(
        "UPDATE corpus_generations SET status='ready', completed_at_ms=7 "
        "WHERE corpus_id='demo' AND generation_id=?",
        (generation_id,),
    )
    return generation_id, lexical_id, dense_id


def test_v2_schema_is_executable_versioned_sqlite() -> None:
    connection = _apply_schema()
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        assert REQUIRED_TABLES <= tables
        assert connection.execute(
            "SELECT value FROM corpus_schema_meta WHERE key='storage_format'"
        ).fetchone() == ("tube-bridge-corpus-v2",)
        assert connection.execute(
            "SELECT read_authority FROM corpus_runtime_state WHERE singleton=1"
        ).fetchone() == ("v1",)
    finally:
        connection.close()


def test_source_projection_generation_and_indexes_link_end_to_end() -> None:
    connection = _apply_schema(with_vec=True)
    try:
        connection.execute(
            "INSERT INTO corpora VALUES ('demo', 'Demo', NULL, 1, 1)"
        )
        transcript_id, source_hash, fetch_id = _insert_source(connection)
        projection_id = _insert_ready_projection(connection, transcript_id, source_hash)
        generation_id, lexical_id, dense_id = _insert_generation_and_indexes(
            connection, transcript_id, source_hash, fetch_id, projection_id
        )
        connection.execute(
            "UPDATE corpora SET active_generation_id=?, updated_at_ms=8 WHERE corpus_id='demo'",
            (generation_id,),
        )
        connection.commit()

        assert connection.execute(
            "SELECT active_generation_id FROM corpora WHERE corpus_id='demo'"
        ).fetchone() == (generation_id,)
        assert len(connection.execute(
            "SELECT d.document_id FROM search_documents_fts f "
            "JOIN search_documents d ON d.row_id=f.rowid "
            "WHERE search_documents_fts MATCH 'frozen'"
        ).fetchall()) == 2
        dense_row_ids = {
            row[0]
            for row in connection.execute(
                "SELECT row_id FROM search_documents WHERE index_version_id=?",
                (dense_id,),
            )
        }
        vector_table = f"vec_{HEX['dense']}"
        assert connection.execute(
            f"SELECT rowid FROM {vector_table} WHERE embedding MATCH ? AND k=1",
            (json.dumps(_normalize_vector([5.0, 0.0, 0.0], 3)),),
        ).fetchone()[0] in dense_row_ids
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert {lexical_id, dense_id} == {
            row[0]
            for row in connection.execute(
                "SELECT index_version_id FROM index_versions "
                "WHERE corpus_id='demo' AND generation_id=? AND status='ready'",
                (generation_id,),
            )
        }
    finally:
        connection.close()


def test_composite_identity_and_ready_guards_fail_closed() -> None:
    connection = _apply_schema()
    try:
        connection.execute("INSERT INTO corpora VALUES ('demo', 'Demo', NULL, 1, 1)")
        transcript_id, source_hash, _ = _insert_source(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO projection_versions "
                "(projection_version_id, corpus_id, video_id, transcript_version_id, "
                "source_sha256, projection_schema_version, build_key_sha256, processor_name, "
                "processor_version, processing_config_json, processing_config_sha256, "
                "status, created_at_ms) VALUES (?, 'demo', 'wrong-video', ?, ?, 2, ?, "
                "'p', '1', '{}', ?, 'building', 1)",
                (
                    f"prj_{'9' * 32}",
                    transcript_id,
                    source_hash,
                    "a" * 64,
                    "b" * 64,
                ),
            )
        projection_id = _insert_ready_projection(connection, transcript_id, source_hash)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE source_segments SET text_original='mutated' "
                "WHERE transcript_version_id=?",
                (transcript_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="whole transcript version"):
            connection.execute(
                "DELETE FROM source_segments WHERE transcript_version_id=? AND segment_ordinal=0",
                (transcript_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="BUILDING transcript"):
            connection.execute(
                "INSERT INTO source_segments VALUES (?, ?, 2, ?, 1000, 1100, 'late')",
                (transcript_id, source_hash, f"seg_{source_hash}_00000002"),
            )
        with pytest.raises(sqlite3.IntegrityError, match="projection nodes are immutable"):
            connection.execute(
                "UPDATE projection_nodes SET title='mutated' WHERE projection_version_id=?",
                (projection_id,),
            )
        connection.execute(
            "INSERT INTO corpus_generations "
            "(generation_id,corpus_id,build_key_sha256,source_manifest_sha256,"
            "force_run_id,status,created_at_ms) "
            "VALUES (?,'demo',?,?,NULL,'building',2)",
            (f"gen_{'a' * 32}", "c" * 64, "d" * 64),
        )
        with pytest.raises(sqlite3.IntegrityError, match="generation requires members"):
            connection.execute(
                "UPDATE corpus_generations SET status='ready', completed_at_ms=3 "
                "WHERE generation_id=?",
                (f"gen_{'a' * 32}",),
            )
    finally:
        connection.close()


def test_ready_source_requires_registered_canonical_validator_result() -> None:
    connection = _apply_schema()
    envelope = {
        "schema": "tube-bridge.transcript-source.v2",
        "video_id": "single",
        "selected_language": "en",
        "track_kind": "manual",
        "segments": [
            {"ordinal": 0, "start_ms": 0, "end_ms": 100, "text": "exact"}
        ],
    }
    source_hash = _sha(envelope)
    transcript_id = f"trv_{source_hash}"
    try:
        with pytest.raises(sqlite3.IntegrityError, match="inserted BUILDING"):
            connection.execute(
                "INSERT INTO transcript_versions "
                "(transcript_version_id,source_sha256,source_schema_version,video_id,"
                "selected_language,track_kind,segment_count,start_ms,end_ms,status,"
                "validated_at_ms,validation_sha256,created_at_ms) "
                "VALUES (?,?,2,'single','en','manual',1,0,100,'ready',1,?,1)",
                (transcript_id, source_hash, "0" * 64),
            )
        connection.execute(
            "INSERT INTO transcript_versions "
            "(transcript_version_id,source_sha256,source_schema_version,video_id,"
            "selected_language,track_kind,segment_count,start_ms,end_ms,status,created_at_ms) "
            "VALUES (?,?,2,'single','en','manual',1,0,100,'building',1)",
            (transcript_id, source_hash),
        )
        connection.execute(
            "INSERT INTO source_segments VALUES (?,?,0,?,0,100,'exact')",
            (transcript_id, source_hash, f"seg_{source_hash}_00000000"),
        )
        with pytest.raises(sqlite3.IntegrityError, match="validation hash mismatch"):
            connection.execute(
                "UPDATE transcript_versions SET status='ready',validated_at_ms=2,"
                "validation_sha256=? WHERE transcript_version_id=?",
                ("0" * 64, transcript_id),
            )
    finally:
        connection.close()


def test_cache_provenance_requires_same_transcript_live_origin() -> None:
    connection = _apply_schema()
    try:
        transcript_id, _, live_fetch_id = _insert_source(connection)
        cache_fetch_id = f"fetch_{'a' * 32}"
        connection.execute(
            "INSERT INTO transcript_fetches "
            "(fetch_id,transcript_version_id,provider,requested_language,"
            "selection_policy_version,selection_reason,retrieval_mode,origin_fetch_id,fetched_at_ms) "
            "VALUES (?,?,'cache','en','track-selection-v2','cache-hit','cache',?,2)",
            (cache_fetch_id, transcript_id, live_fetch_id),
        )
        with pytest.raises(sqlite3.IntegrityError, match="origin must be LIVE"):
            connection.execute(
                "INSERT INTO transcript_fetches "
                "(fetch_id,transcript_version_id,provider,requested_language,"
                "selection_policy_version,selection_reason,retrieval_mode,origin_fetch_id,fetched_at_ms) "
                "VALUES (?,?,'cache','en','track-selection-v2','cache-chain','cache',?,3)",
                (f"fetch_{'b' * 32}", transcript_id, cache_fetch_id),
            )
    finally:
        connection.close()


def test_ready_cohort_rows_are_immutable_and_vector_manifest_detects_corruption() -> None:
    connection = _apply_schema(with_vec=True)
    try:
        connection.execute("INSERT INTO corpora VALUES ('demo', 'Demo', NULL, 1, 1)")
        transcript_id, source_hash, fetch_id = _insert_source(connection)
        projection_id = _insert_ready_projection(connection, transcript_id, source_hash)
        generation_id, lexical_id, dense_id = _insert_generation_and_indexes(
            connection, transcript_id, source_hash, fetch_id, projection_id
        )
        connection.execute(
            "UPDATE corpora SET active_generation_id=?,updated_at_ms=8 WHERE corpus_id='demo'",
            (generation_id,),
        )
        with pytest.raises(sqlite3.IntegrityError, match="generation, not individual"):
            connection.execute(
                "DELETE FROM corpus_generation_members "
                "WHERE corpus_id='demo' AND generation_id=?",
                (generation_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="search documents are immutable"):
            connection.execute(
                "UPDATE search_documents SET text='tampered' WHERE index_version_id=?",
                (lexical_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="index, not individual"):
            connection.execute(
                "DELETE FROM index_projection_members WHERE index_version_id=?",
                (dense_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="whole generation"):
            connection.execute(
                "DELETE FROM index_versions WHERE index_version_id=?", (dense_id,)
            )

        vector_table = f"vec_{HEX['dense']}"
        row_id = connection.execute(
            "SELECT row_id FROM search_documents WHERE index_version_id=? LIMIT 1",
            (dense_id,),
        ).fetchone()[0]
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            connection.execute(
                f"UPDATE {vector_table} SET embedding=? WHERE rowid=?",
                (json.dumps([0.0, 1.0, 0.0]), row_id),
            )
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            connection.execute(f"DELETE FROM {vector_table}_rowids")
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            connection.execute(f"DROP TABLE {vector_table}_chunks")
        with _vec_write_scope(connection):
            connection.execute(
                f"UPDATE {vector_table} SET embedding=? WHERE rowid=?",
                (json.dumps([0.0, 1.0, 0.0]), row_id),
            )
        with pytest.raises(ValueError):
            _validate_index_snapshot(connection, dense_id)
    finally:
        connection.close()


def test_invalid_projection_partition_cannot_become_ready() -> None:
    connection = _apply_schema()
    try:
        connection.execute("INSERT INTO corpora VALUES ('demo', 'Demo', NULL, 1, 1)")
        transcript_id, source_hash, _ = _insert_source(connection)
        projection_id = f"prj_{'a' * 32}"
        connection.execute(
            "INSERT INTO projection_versions "
            "(projection_version_id, corpus_id, video_id, transcript_version_id, source_sha256, "
            "projection_schema_version, build_key_sha256, processor_name, processor_version, "
            "processing_config_json, processing_config_sha256, status, created_at_ms) "
            "VALUES (?, 'demo', 'video123', ?, ?, 2, ?, 'p', '1', '{}', ?, 'building', 1)",
            (projection_id, transcript_id, source_hash, "e" * 64, "f" * 64),
        )
        root = f"node_{'b' * 32}"
        connection.execute(
            "INSERT INTO projection_nodes "
            "(projection_version_id,node_id,node_kind,parent_node_id,ordinal,"
            "start_segment_ordinal,end_segment_ordinal,start_ms,end_ms,confidence_label,provenance_json) "
            "VALUES (?,?,'video',NULL,0,0,1,0,1000,'observed','{}')",
            (projection_id, root),
        )
        connection.execute(
            "INSERT INTO projection_nodes "
            "(projection_version_id,node_id,node_kind,parent_node_id,ordinal,"
            "start_segment_ordinal,end_segment_ordinal,start_ms,end_ms,confidence_label,provenance_json) "
            "VALUES (?,?,'passage',?,0,0,0,0,500,'observed','{}')",
            (projection_id, f"node_{'c' * 32}", root),
        )
        with pytest.raises(sqlite3.IntegrityError, match="whole projection"):
            connection.execute(
                "DELETE FROM projection_nodes WHERE projection_version_id=? AND node_kind='passage'",
                (projection_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="partition source"):
            connection.execute(
                "UPDATE projection_versions SET status='ready', completed_at_ms=2 "
                "WHERE projection_version_id=?",
                (projection_id,),
            )
    finally:
        connection.close()


def test_migration_cutover_is_persisted_resumable_and_fail_closed() -> None:
    connection = _apply_schema()
    migration_id = f"mig_{HEX['migration']}"
    try:
        connection.execute(
            "INSERT INTO migration_runs VALUES (?, 'v1-snapshot.db', ?, 'running', 1, NULL, NULL)",
            (migration_id, "a" * 64),
        )
        connection.execute(
            "INSERT INTO migration_items VALUES (?, 'old', 'video123', 'blocked', NULL, 1, ?, 2)",
            (migration_id, "source unavailable"),
        )
        with pytest.raises(sqlite3.IntegrityError, match="prevent READY"):
            connection.execute(
                "UPDATE migration_runs SET status='ready', completed_at_ms=3 "
                "WHERE migration_run_id=?",
                (migration_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="READY migration run"):
            connection.execute(
                "UPDATE corpus_runtime_state SET read_authority='v2', "
                "active_migration_run_id=?, cutover_at_ms=4 WHERE singleton=1",
                (migration_id,),
            )
        connection.execute(
            "UPDATE migration_items SET status='skipped', status_reason='operator accepted' "
            "WHERE migration_run_id=?",
            (migration_id,),
        )
        connection.execute(
            "UPDATE migration_runs SET status='ready', completed_at_ms=4 "
            "WHERE migration_run_id=?",
            (migration_id,),
        )
        connection.execute(
            "UPDATE corpus_runtime_state SET read_authority='v2', "
            "active_migration_run_id=?, cutover_at_ms=5 WHERE singleton=1",
            (migration_id,),
        )
        assert connection.execute(
            "SELECT read_authority, active_migration_run_id FROM corpus_runtime_state"
        ).fetchone() == ("v2", migration_id)
        assert connection.execute(
            "SELECT status FROM migration_runs WHERE migration_run_id=?", (migration_id,)
        ).fetchone() == ("cutover",)
        connection.execute(
            "INSERT INTO corpora VALUES ('post-cutover', 'Post cutover', NULL, 6, 6)"
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM v2_mutations WHERE migration_run_id=?", (migration_id,)
        ).fetchone() == (1,)
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM v2_mutations")
        clean_run_id = f"mig_{'a' * 32}"
        connection.execute(
            "INSERT INTO migration_runs VALUES (?, 'clean.db', ?, 'running', 7, NULL, NULL)",
            (clean_run_id, "d" * 64),
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable in v2"):
            connection.execute(
                "UPDATE corpus_runtime_state SET active_migration_run_id=? WHERE singleton=1",
                (clean_run_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="singleton cannot be deleted"):
            connection.execute("DELETE FROM corpus_runtime_state")
        with pytest.raises(sqlite3.IntegrityError, match="items are immutable"):
            connection.execute(
                "UPDATE migration_items SET status_reason='rewritten' WHERE migration_run_id=?",
                (migration_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="irreversible"):
            connection.execute(
                "UPDATE corpus_runtime_state SET read_authority='v1' WHERE singleton=1"
            )
    finally:
        connection.close()


def test_migrated_item_requires_exact_video_in_active_ready_target() -> None:
    connection = _apply_schema(with_vec=True)
    migration_id = f"mig_{'9' * 32}"
    try:
        connection.execute("INSERT INTO corpora VALUES ('demo', 'Demo', NULL, 1, 1)")
        transcript_id, source_hash, fetch_id = _insert_source(connection)
        projection_id = _insert_ready_projection(connection, transcript_id, source_hash)
        generation_id, _, _ = _insert_generation_and_indexes(
            connection, transcript_id, source_hash, fetch_id, projection_id
        )
        connection.execute(
            "UPDATE corpora SET active_generation_id=?,updated_at_ms=8 WHERE corpus_id='demo'",
            (generation_id,),
        )
        connection.execute(
            "INSERT INTO migration_runs VALUES (?, 'v1-snapshot.db', ?, 'running', 1, NULL, NULL)",
            (migration_id, "c" * 64),
        )
        connection.execute(
            "INSERT INTO migration_items VALUES "
            "(?,'demo','absent-video','migrated',?,1,NULL,9)",
            (migration_id, generation_id),
        )
        connection.execute(
            "UPDATE migration_runs SET status='ready',completed_at_ms=9 "
            "WHERE migration_run_id=?",
            (migration_id,),
        )
        with pytest.raises(sqlite3.IntegrityError, match="active READY target"):
            connection.execute(
                "UPDATE corpus_runtime_state SET read_authority='v2',"
                "active_migration_run_id=?,cutover_at_ms=10 WHERE singleton=1",
                (migration_id,),
            )
    finally:
        connection.close()


def test_explicit_corpus_and_source_gc_has_deterministic_order() -> None:
    connection = _apply_schema(with_vec=True)
    try:
        connection.execute("INSERT INTO corpora VALUES ('demo', 'Demo', NULL, 1, 1)")
        transcript_id, source_hash, fetch_id = _insert_source(connection)
        projection_id = _insert_ready_projection(connection, transcript_id, source_hash)
        generation_id, _, _ = _insert_generation_and_indexes(
            connection, transcript_id, source_hash, fetch_id, projection_id
        )
        connection.execute(
            "UPDATE corpora SET active_generation_id=?, updated_at_ms=8 WHERE corpus_id='demo'",
            (generation_id,),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="generation"):
            connection.execute(
                "DELETE FROM corpus_generations WHERE corpus_id='demo' AND generation_id=?",
                (generation_id,),
            )
        connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        with _vec_write_scope(connection):
            connection.execute(f"DROP TABLE vec_{HEX['dense']}")
        with pytest.raises(sqlite3.IntegrityError, match="active generation"):
            connection.execute(
                "DELETE FROM corpus_generations WHERE corpus_id='demo' AND generation_id=?",
                (generation_id,),
            )
        connection.rollback()

        connection.execute("BEGIN IMMEDIATE")
        vector_tables = [
            row[0]
            for row in connection.execute(
                "SELECT vector_table_name FROM index_versions "
                "WHERE corpus_id='demo' AND vector_table_name IS NOT NULL"
            )
        ]
        assert vector_tables == [f"vec_{HEX['dense']}"]
        connection.execute(
            "UPDATE corpora SET active_generation_id=NULL, updated_at_ms=9 WHERE corpus_id='demo'"
        )
        with pytest.raises(sqlite3.IntegrityError, match="drop generation vector"):
            connection.execute(
                "DELETE FROM corpus_generations WHERE corpus_id='demo' AND generation_id=?",
                (generation_id,),
            )
        for table in vector_tables:
            assert table.startswith("vec_") and len(table) == 36
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                connection.execute(f"DROP TABLE {table}")
            with _vec_write_scope(connection):
                connection.execute(f"DROP TABLE {table}")
        connection.execute(
            "DELETE FROM corpus_generations WHERE corpus_id='demo' AND generation_id=?",
            (generation_id,),
        )
        connection.execute(
            "INSERT INTO search_documents_fts(search_documents_fts) VALUES('rebuild')"
        )
        connection.execute("DELETE FROM corpora WHERE corpus_id='demo'")
        connection.execute(
            "INSERT INTO search_documents_fts(search_documents_fts) VALUES('rebuild')"
        )
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM search_documents").fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM search_documents_fts WHERE search_documents_fts MATCH 'frozen'"
        ).fetchone() == (0,)

        connection.execute(
            "DELETE FROM transcript_versions WHERE transcript_version_id=?", (transcript_id,)
        )
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM source_segments").fetchone() == (0,)
        assert connection.execute("SELECT COUNT(*) FROM transcript_fetches").fetchone() == (0,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_hash_and_time_contract_has_fixed_vectors() -> None:
    assert _ms("0.0004") == 0
    assert _ms("0.0005") == 1
    assert _ms("1.2344") == 1234
    assert _ms("1.2345") == 1235
    assert _sha({"é": "same", "a": 1}) == (
        "d9bab79380dbb5cfd853c7a7b6d0774e5de5c0c506a31a03ec342122f511da42"
    )


def test_dense_normalization_rejects_invalid_model_outputs() -> None:
    assert _normalize_vector([3.0, 4.0], 2) == pytest.approx([0.6, 0.8])
    for values, dimension in (
        ([1.0], 2),
        ([0.0, 0.0], 2),
        ([float("nan"), 1.0], 2),
        ([float("inf"), 1.0], 2),
    ):
        with pytest.raises(ValueError):
            _normalize_vector(values, dimension)


def test_build_key_envelopes_have_independent_fixed_digest_vectors() -> None:
    projection = {
        "schema": "tube-bridge.projection-build.v2",
        "source_sha256": "a" * 64,
        "processor_name": "processor",
        "processor_version": "1.2.3",
        "model_name": "model",
        "model_version": "rev-1",
        "processing_config_sha256": "b" * 64,
    }
    generation = {
        "schema": "tube-bridge.corpus-generation.v2",
        "source_manifest_sha256": "c" * 64,
        "lexical_config_sha256": "d" * 64,
        "dense_config_sha256": "e" * 64,
        "force_run_id": None,
    }
    forced_generation = {**generation, "force_run_id": "f" * 32}
    index = {
        "schema": "tube-bridge.index-build.v2",
        "generation_id": f"gen_{'1' * 32}",
        "index_kind": "dense",
        "config_sha256": "2" * 64,
    }
    assert _sha(projection) == "00f4634765f82eeba88eb132c29c1166d8dbb3a4b9694124b4c595a7260e97a3"
    assert _sha(generation) == "a833257623a7b68708b2730b03f3e45807d460333657b893b952add13b22efe6"
    assert _sha(forced_generation) == "5742e629ecd4f6f9aad89e9a32f46a9cd1b3e02911b874b9983a2ce59b1f69f9"
    assert _sha(index) == "d702ef3f772231e1c6994bfde68ab88f81a3264cb6824376aca465f2c729bf19"
    assert importlib.metadata.version("sqlite-vec") == "0.1.9"


def test_contract_freezes_authority_vector_gc_and_migration_semantics() -> None:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    required = {
        "corpus-v2.db",
        "PRAGMA user_version = 2",
        "source of truth",
        "SHA-256",
        "canonical JSON",
        "integer milliseconds",
        "corpus generation",
        "source manifest",
        "video / chapter / topic / passage",
        "sqlite-vec 0.1.9",
        "float32",
        "cosine",
        "L2-normalized",
        "atomic",
        "failed rebuild",
        "cache.db",
        "cannot reconstruct",
        "refetch",
        "side-by-side",
        "migration_items",
        "read_authority",
        "80/20",
    }
    lowered = text.lower()
    for marker in required:
        assert marker.lower() in lowered, f"storage contract is missing {marker!r}"


def test_schema_exposes_exact_typed_linkage() -> None:
    connection = _apply_schema()
    try:
        assert {
            "transcript_version_id",
            "source_sha256",
            "video_id",
            "selected_language",
            "track_kind",
            "segment_count",
        } <= _columns(connection, "transcript_versions")
        assert {
            "provider",
            "requested_language",
            "selection_policy_version",
            "retrieval_mode",
            "origin_fetch_id",
        } <= _columns(connection, "transcript_fetches")
        assert {
            "generation_id",
            "source_manifest_sha256",
            "build_key_sha256",
            "status",
        } <= _columns(connection, "corpus_generations")
        assert {
            "corpus_id",
            "generation_id",
            "index_version_id",
            "projection_version_id",
            "node_id",
            "text_role",
        } <= _columns(connection, "search_documents")
    finally:
        connection.close()
