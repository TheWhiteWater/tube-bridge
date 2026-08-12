"""Frozen P1 remediation addendum for bounded Corpus v1 ranking.

Covers three defects found by the independent source audit:
- successful force_reembed removes only replaced vector rows atomically;
- dash/underscore corpus IDs never share a vec table, including legacy migration;
- a saturated equal-distance KNN boundary resolves to stable candidates.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
import sqlite_vec


@pytest.fixture
def corpus_module(tmp_path: Path, monkeypatch):
    import tube_bridge.corpus as corpus

    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")
    monkeypatch.setattr(corpus, "_get_embedding_model", lambda: (object(), 2))
    monkeypatch.setattr(corpus, "_embed", lambda texts: [[1.0, 0.0] for _ in texts])
    return corpus


def test_repeated_force_reembed_removes_only_replaced_vectors(corpus_module):
    corpus = corpus_module
    corpus.corpus_create("force-clean")
    corpus.corpus_add(
        "force-clean",
        "target-video",
        [{"text": "version 0", "start": 0.0, "duration": 1.0}],
        False,
        "Target",
    )
    corpus.corpus_add(
        "force-clean",
        "untouched-video",
        [{"text": "untouched", "start": 50.0, "duration": 1.0}],
        False,
        "Untouched",
    )

    for version in range(1, 41):
        corpus.corpus_add(
            "force-clean",
            "target-video",
            [
                {
                    "text": f"version {version}",
                    "start": float(version * 100),
                    "duration": 1.0,
                }
            ],
            True,
            None,
        )

    conn = corpus._get_conn()
    try:
        vec_table = corpus._vec_table("force-clean")
        relational_ids = {
            row[0]
            for row in conn.execute(
                "SELECT id FROM corpus_chunks WHERE corpus_id='force-clean'"
            ).fetchall()
        }
        vector_ids = {
            row[0]
            for row in conn.execute(
                f"SELECT rowid FROM {vec_table}"
            ).fetchall()
        }
        assert len(relational_ids) == 2
        assert vector_ids == relational_ids
        assert conn.execute(
            "SELECT start_ts,text FROM corpus_chunks "
            "WHERE corpus_id='force-clean' AND video_id='untouched-video'"
        ).fetchall() == [(50.0, "untouched")]
    finally:
        conn.close()

    hits = corpus.corpus_search("force-clean", "latest", top_k=2)["chunks"]
    assert {hit["video_id"] for hit in hits} == {
        "target-video",
        "untouched-video",
    }
    target = next(hit for hit in hits if hit["video_id"] == "target-video")
    assert target["start_ts"] == 4000.0
    assert target["text"] == "version 40"
    assert target["title"] == "Target"


def _create_legacy_collision_db(db_path: Path) -> dict[str, tuple[int, list[float]]]:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute(
        "CREATE TABLE corpora (corpus_id TEXT PRIMARY KEY, label TEXT, "
        "embedding_model TEXT, created_at REAL, expires_at REAL)"
    )
    conn.execute(
        "CREATE TABLE corpus_chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "corpus_id TEXT NOT NULL, video_id TEXT NOT NULL, start_ts REAL, "
        "end_ts REAL, text TEXT, added_at REAL, "
        "UNIQUE(corpus_id, video_id, start_ts))"
    )
    conn.execute(
        "CREATE TABLE corpus_added_videos (corpus_id TEXT, video_id TEXT, "
        "added_at REAL, PRIMARY KEY(corpus_id, video_id))"
    )
    expected: dict[str, tuple[int, list[float]]] = {}
    for corpus_id, video_id, text, vector in (
        ("a-b", "video-dash", "dash corpus", [1.0, 0.0]),
        ("a_b", "video-underscore", "underscore corpus", [0.0, 1.0]),
    ):
        conn.execute(
            "INSERT INTO corpora VALUES (?,?,?,0,NULL)",
            (corpus_id, corpus_id, "BAAI/bge-small-en-v1.5"),
        )
        conn.execute(
            "INSERT INTO corpus_chunks "
            "(corpus_id,video_id,start_ts,end_ts,text,added_at) "
            "VALUES (?,?,0,10,?,0)",
            (corpus_id, video_id, text),
        )
        chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        expected[corpus_id] = (chunk_id, vector)
        conn.execute(
            "INSERT INTO corpus_added_videos VALUES (?,?,0)",
            (corpus_id, video_id),
        )
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='vec_a_b'"
        ).fetchone():
            conn.execute(
                "CREATE VIRTUAL TABLE vec_a_b USING vec0(embedding float[2])"
            )
        conn.execute(
            "INSERT INTO vec_a_b (rowid,embedding) VALUES (?,?)",
            (chunk_id, json.dumps(vector)),
        )
    conn.commit()
    conn.close()
    return expected


def _stored_vectors(conn, table: str) -> list[tuple[int, list[float]]]:
    return [
        (rowid, json.loads(vector_json))
        for rowid, vector_json in conn.execute(
            f"SELECT rowid,vec_to_json(embedding) FROM {table} ORDER BY rowid"
        ).fetchall()
    ]


def test_legacy_colliding_vec_table_is_split_without_cross_corpus_loss(
    tmp_path, monkeypatch
):
    import tube_bridge.corpus as corpus

    db_path = tmp_path / "legacy-collision.db"
    expected = _create_legacy_collision_db(db_path)
    monkeypatch.setattr(corpus, "DB_PATH", db_path)
    monkeypatch.setattr(
        corpus,
        "_embed",
        lambda texts: [[1.0, 0.0]] if texts[0] == "dash" else [[0.0, 1.0]],
    )

    migrated = corpus._get_conn()
    try:
        dash_table = corpus._vec_table("a-b")
        underscore_table = corpus._vec_table("a_b")
        assert dash_table != underscore_table
        assert migrated.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vec_a_b'"
        ).fetchone() is None
        assert _stored_vectors(migrated, dash_table) == [expected["a-b"]]
        assert _stored_vectors(migrated, underscore_table) == [expected["a_b"]]
    finally:
        migrated.close()

    dash_hit = corpus.corpus_search("a-b", "dash", top_k=1)["chunks"][0]
    underscore_hit = corpus.corpus_search("a_b", "underscore", top_k=1)["chunks"][0]
    assert dash_hit["video_id"] == "video-dash"
    assert underscore_hit["video_id"] == "video-underscore"

    corpus.corpus_delete("a-b")
    still_available = corpus.corpus_search("a_b", "underscore", top_k=1)["chunks"]
    assert still_available[0]["video_id"] == "video-underscore"


def test_legacy_vec_split_rolls_back_on_mid_migration_failure(tmp_path, monkeypatch):
    import tube_bridge.corpus as corpus

    db_path = tmp_path / "legacy-rollback.db"
    expected = _create_legacy_collision_db(db_path)
    monkeypatch.setattr(corpus, "DB_PATH", db_path)
    original_connect = corpus.sqlite3.connect
    targets = sorted({corpus._vec_table("a-b"), corpus._vec_table("a_b")})
    assert len(targets) == 2
    denied_target = targets[1]

    baseline = original_connect(db_path)
    try:
        baseline_rows = {
            "corpora": baseline.execute(
                "SELECT * FROM corpora ORDER BY corpus_id"
            ).fetchall(),
            "chunks": baseline.execute(
                "SELECT * FROM corpus_chunks ORDER BY id"
            ).fetchall(),
            "markers": baseline.execute(
                "SELECT * FROM corpus_added_videos ORDER BY corpus_id"
            ).fetchall(),
        }
    finally:
        baseline.close()

    def guarded_connect(*args, **kwargs):
        conn = original_connect(*args, **kwargs)

        def authorizer(action, arg1, arg2, db_name, trigger):
            if action == sqlite3.SQLITE_INSERT and arg1 == denied_target:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        conn.set_authorizer(authorizer)
        return conn

    monkeypatch.setattr(corpus.sqlite3, "connect", guarded_connect)
    with pytest.raises(sqlite3.DatabaseError):
        corpus._get_conn()

    raw = original_connect(db_path)
    raw.enable_load_extension(True)
    sqlite_vec.load(raw)
    raw.enable_load_extension(False)
    try:
        assert _stored_vectors(raw, "vec_a_b") == sorted(
            expected.values(), key=lambda item: item[0]
        )
        assert raw.execute(
            "SELECT * FROM corpora ORDER BY corpus_id"
        ).fetchall() == baseline_rows["corpora"]
        assert raw.execute(
            "SELECT * FROM corpus_chunks ORDER BY id"
        ).fetchall() == baseline_rows["chunks"]
        assert raw.execute(
            "SELECT * FROM corpus_added_videos ORDER BY corpus_id"
        ).fetchall() == baseline_rows["markers"]
        for target in targets:
            assert raw.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (target,),
            ).fetchone() is None
    finally:
        raw.close()

    monkeypatch.setattr(corpus.sqlite3, "connect", original_connect)
    migrated = corpus._get_conn()
    try:
        assert migrated.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vec_a_b'"
        ).fetchone() is None
        assert _stored_vectors(migrated, corpus._vec_table("a-b")) == [
            expected["a-b"]
        ]
        assert _stored_vectors(migrated, corpus._vec_table("a_b")) == [
            expected["a_b"]
        ]
    finally:
        migrated.close()


class _CommitFailureProxy:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def commit(self):
        raise sqlite3.OperationalError("simulated force commit failure")

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def test_force_reembed_failure_preserves_exact_chunks_titles_and_vectors(
    corpus_module, monkeypatch
):
    corpus = corpus_module

    def embeddings(texts):
        vectors = {
            "old target": [1.0, 0.0],
            "untouched": [0.0, 1.0],
            "new target": [0.5, 0.5],
        }
        return [vectors[text] for text in texts]

    monkeypatch.setattr(corpus, "_embed", embeddings)
    corpus.corpus_create("force-rollback")
    corpus.corpus_add(
        "force-rollback",
        "target-video",
        [{"text": "old target", "start": 0.0, "duration": 1.0}],
        False,
        "Old Target",
    )
    corpus.corpus_add(
        "force-rollback",
        "untouched-video",
        [{"text": "untouched", "start": 50.0, "duration": 1.0}],
        False,
        "Untouched",
    )
    original_get_conn = corpus._get_conn
    before = original_get_conn()
    try:
        before_chunks = before.execute(
            "SELECT id,video_id,start_ts,end_ts,text FROM corpus_chunks "
            "WHERE corpus_id='force-rollback' ORDER BY id"
        ).fetchall()
        before_titles = before.execute(
            "SELECT video_id,title FROM corpus_added_videos "
            "WHERE corpus_id='force-rollback' ORDER BY video_id"
        ).fetchall()
        before_vectors = _stored_vectors(
            before, corpus._vec_table("force-rollback")
        )
    finally:
        before.close()

    monkeypatch.setattr(
        corpus,
        "_get_conn",
        lambda: _CommitFailureProxy(original_get_conn()),
    )
    with pytest.raises(sqlite3.OperationalError, match="force commit failure"):
        corpus.corpus_add(
            "force-rollback",
            "target-video",
            [{"text": "new target", "start": 100.0, "duration": 1.0}],
            True,
            "New Target",
        )

    verify = original_get_conn()
    try:
        assert verify.execute(
            "SELECT id,video_id,start_ts,end_ts,text FROM corpus_chunks "
            "WHERE corpus_id='force-rollback' ORDER BY id"
        ).fetchall() == before_chunks
        assert verify.execute(
            "SELECT video_id,title FROM corpus_added_videos "
            "WHERE corpus_id='force-rollback' ORDER BY video_id"
        ).fetchall() == before_titles
        assert _stored_vectors(
            verify, corpus._vec_table("force-rollback")
        ) == before_vectors
    finally:
        verify.close()


def _seed_equal_distance_candidates(corpus, corpus_id: str, reverse: bool) -> None:
    corpus.corpus_create(corpus_id)
    rows = [
        (f"video-{index:02d}", float(index * 100), [1.0, 0.0])
        for index in range(40)
    ]
    rows.extend(
        (f"aaa-worse-{index:02d}", float(10_000 + index * 100), [0.0, 0.0])
        for index in range(5)
    )
    if reverse:
        rows.reverse()

    conn = corpus._get_conn()
    try:
        vec_table = corpus._vec_table(corpus_id)
        conn.execute(
            f"CREATE VIRTUAL TABLE {vec_table} USING vec0(embedding float[2])"
        )
        for video_id, start_ts, vector in rows:
            conn.execute(
                "INSERT INTO corpus_chunks "
                "(corpus_id,video_id,start_ts,end_ts,text,added_at) "
                "VALUES (?,?,?,?,?,0)",
                (corpus_id, video_id, start_ts, start_ts + 10, video_id),
            )
            chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                f"INSERT INTO {vec_table} (rowid,embedding) VALUES (?,?)",
                (chunk_id, json.dumps(vector)),
            )
            conn.execute(
                "INSERT INTO corpus_added_videos "
                "(corpus_id,video_id,added_at,title) VALUES (?,?,0,?)",
                (corpus_id, video_id, video_id),
            )
        conn.commit()
    finally:
        conn.close()


def test_saturated_equal_distance_boundary_is_stable_across_insertion_order(
    corpus_module,
):
    corpus = corpus_module
    _seed_equal_distance_candidates(corpus, "ties-forward", reverse=False)
    _seed_equal_distance_candidates(corpus, "ties-reverse", reverse=True)

    first = corpus.corpus_search("ties-forward", "query", top_k=1)["chunks"]
    second = corpus.corpus_search("ties-reverse", "query", top_k=1)["chunks"]

    assert [(hit["video_id"], hit["start_ts"]) for hit in first] == [
        ("video-00", 0.0)
    ]
    assert [(hit["video_id"], hit["start_ts"]) for hit in second] == [
        ("video-00", 0.0)
    ]
