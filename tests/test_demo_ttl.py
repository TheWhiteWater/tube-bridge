"""Frozen RED contracts for demo-only corpus expiry and restart reconciliation."""

import importlib
import sqlite3
import threading
import time

import pytest


def prepare_corpus(monkeypatch, tmp_path, demo_mode):
    corpus = importlib.import_module("tube_bridge.corpus")
    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")
    if demo_mode:
        monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    else:
        monkeypatch.delenv("TUBE_BRIDGE_DEMO_MODE", raising=False)

    class Model:
        def embed(self, texts):
            return [[0.0, 0.0] for _ in texts]

    monkeypatch.setattr(corpus, "_get_embedding_model", lambda: (Model(), 2))
    monkeypatch.setattr(corpus, "_embed", lambda texts: [[0.0, 0.0] for _ in texts])
    return corpus


def table_columns(db_path, table):
    with sqlite3.connect(db_path) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_existing_four_column_database_migrates_idempotently(monkeypatch, tmp_path):
    db_path = tmp_path / "corpus.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE corpora (corpus_id TEXT PRIMARY KEY, label TEXT, embedding_model TEXT, created_at REAL)")
        conn.execute("INSERT INTO corpora VALUES ('legacy', 'Legacy', 'model', 100.0)")
        conn.commit()
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=False)
    for _ in range(2):
        conn = corpus._get_conn()
        conn.close()
    columns = set(table_columns(db_path, "corpora"))
    assert {"corpus_id", "label", "embedding_model", "created_at", "expires_at"} <= columns
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT expires_at FROM corpora WHERE corpus_id='legacy'").fetchone() == (None,)


def test_self_hosted_create_has_null_expiration(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=False)
    monkeypatch.setattr(corpus.time, "time", lambda: 1000.0)
    assert corpus.corpus_create("selfhost")["status"] == "created"
    with sqlite3.connect(corpus.DB_PATH) as conn:
        assert conn.execute("SELECT created_at, expires_at FROM corpora").fetchone() == (1000.0, None)


def test_demo_create_sets_exact_600_second_deadline(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    importlib.import_module("tube_bridge.demo_policy")
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    monkeypatch.setattr(ttl, "wake_demo_ttl_worker", lambda: None)
    monkeypatch.setattr(corpus.time, "time", lambda: 2000.0)
    result = corpus.corpus_create("demo")
    assert result["status"] == "created"
    with sqlite3.connect(corpus.DB_PATH) as conn:
        assert conn.execute("SELECT created_at, expires_at FROM corpora").fetchone() == (2000.0, 2600.0)


def seed_demo_corpus(corpus, corpus_id, created_at, expires_at, with_vector=False):
    conn = corpus._get_conn()
    try:
        conn.execute(
            "INSERT INTO corpora (corpus_id,label,embedding_model,created_at,expires_at) VALUES (?,?,?,?,?)",
            (corpus_id, corpus_id, "BAAI/bge-small-en-v1.5", created_at, expires_at),
        )
        conn.execute(
            "INSERT INTO corpus_chunks (corpus_id,video_id,start_ts,end_ts,text,added_at) VALUES (?,?,?,?,?,?)",
            (corpus_id, "vid", 0.0, 1.0, "text", created_at),
        )
        chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO corpus_added_videos VALUES (?,?,?)", (corpus_id, "vid", created_at))
        if with_vector:
            table = corpus._vec_table(corpus_id)
            conn.execute(f"CREATE VIRTUAL TABLE {table} USING vec0(embedding float[2])")
            conn.execute(f"INSERT INTO {table} (rowid, embedding) VALUES (?, ?)", (chunk_id, "[0.0,0.0]"))
        conn.commit()
    finally:
        conn.close()


def test_purge_before_deadline_keeps_everything(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    seed_demo_corpus(corpus, "keep", 1000.0, 1600.0, with_vector=True)
    assert corpus.delete_expired_demo_corpora(now=1599.999) == []
    with sqlite3.connect(corpus.DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) FROM corpora").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM corpus_added_videos").fetchone()[0] == 1
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='vec_keep'").fetchone() is not None


def test_purge_at_deadline_removes_all_rows_and_vector_table(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    seed_demo_corpus(corpus, "expire", 1000.0, 1600.0, with_vector=True)
    assert corpus.delete_expired_demo_corpora(now=1600.0) == ["expire"]
    with sqlite3.connect(corpus.DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) FROM corpora").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM corpus_added_videos").fetchone()[0] == 0
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='vec_expire'").fetchone() is None


def test_self_hosted_null_deadline_is_never_purged(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=False)
    seed_demo_corpus(corpus, "persistent", 1000.0, None)
    assert corpus.delete_expired_demo_corpora(now=10**9) == []
    with sqlite3.connect(corpus.DB_PATH) as conn:
        assert conn.execute("SELECT corpus_id FROM corpora").fetchone() == ("persistent",)


def test_next_demo_expiry_returns_nearest_non_null_deadline(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    seed_demo_corpus(corpus, "later", 1000.0, 1700.0)
    seed_demo_corpus(corpus, "first", 1000.0, 1600.0)
    seed_demo_corpus(corpus, "selfhost", 1000.0, None)
    assert corpus.next_demo_expiry() == 1600.0


def test_restart_reconciliation_assigns_legacy_deadlines_and_deletes_expired(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    conn = corpus._get_conn()
    try:
        conn.execute(
            "INSERT INTO corpora (corpus_id,label,embedding_model,created_at,expires_at) VALUES (?,?,?,?,NULL)",
            ("legacy_expired", "x", "model", 100.0),
        )
        conn.execute(
            "INSERT INTO corpora (corpus_id,label,embedding_model,created_at,expires_at) VALUES (?,?,?,?,NULL)",
            ("legacy_live", "x", "model", 900.0),
        )
        conn.commit()
    finally:
        conn.close()
    result = corpus.reconcile_demo_corpora(now=1200.0)
    assert result == ["legacy_expired"]
    with sqlite3.connect(corpus.DB_PATH) as conn:
        assert conn.execute(
            "SELECT corpus_id, expires_at FROM corpora ORDER BY corpus_id"
        ).fetchall() == [("legacy_live", 1500.0)]


def test_corpus_list_never_exposes_expired_demo_row(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    seed_demo_corpus(corpus, "gone", 1000.0, 1600.0)
    monkeypatch.setattr(corpus.time, "time", lambda: 1600.0)
    assert corpus.corpus_list() == {"corpora": [], "total": 0}


def test_corpus_add_treats_expired_corpus_as_not_found(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    seed_demo_corpus(corpus, "gone_add", 1000.0, 1600.0)
    monkeypatch.setattr(corpus.time, "time", lambda: 1600.0)
    with pytest.raises(RuntimeError, match="not found"):
        corpus.corpus_add(
            "gone_add", "vid", [{"text": "x", "start": 0.0, "duration": 1.0}],
        )


def test_corpus_search_treats_expired_corpus_as_not_found(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    seed_demo_corpus(corpus, "gone_search", 1000.0, 1600.0)
    monkeypatch.setattr(corpus.time, "time", lambda: 1600.0)
    with pytest.raises(RuntimeError, match="not found"):
        corpus.corpus_search("gone_search", "query", 1)


def test_worker_wakes_for_new_nearest_deadline(monkeypatch):
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    corpus = importlib.import_module("tube_bridge.corpus")
    deadline = {"value": None}
    purged = threading.Event()
    monkeypatch.setattr(corpus, "next_demo_expiry", lambda: deadline["value"])

    def purge(now=None):
        deadline["value"] = None
        purged.set()
        return ["expired"]

    monkeypatch.setattr(corpus, "delete_expired_demo_corpora", purge)
    worker = ttl.DemoTTLWorker(clock=lambda: 1000.0)
    worker.start()
    try:
        deadline["value"] = 1000.0
        worker.wake()
        assert purged.wait(2), "worker did not wake and purge nearest deadline"
    finally:
        assert worker.stop(timeout=2) is True


def test_worker_stop_is_bounded_when_no_deadlines(monkeypatch):
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    corpus = importlib.import_module("tube_bridge.corpus")
    monkeypatch.setattr(corpus, "next_demo_expiry", lambda: None)
    worker = ttl.DemoTTLWorker(clock=lambda: 1000.0)
    worker.start()
    started = time.monotonic()
    assert worker.stop(timeout=2) is True
    assert time.monotonic() - started < 2


def test_worker_waits_for_nearest_persisted_deadline_not_poll_interval(monkeypatch):
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    corpus = importlib.import_module("tube_bridge.corpus")
    deadline = time.time() + 0.20
    active = {"deadline": deadline}
    purged = threading.Event()
    monkeypatch.setattr(corpus, "next_demo_expiry", lambda: active["deadline"])

    def purge(now=None):
        active["deadline"] = None
        purged.set()
        return ["deadline"]

    monkeypatch.setattr(corpus, "delete_expired_demo_corpora", purge)
    worker = ttl.DemoTTLWorker(clock=time.time)
    started = time.monotonic()
    worker.start()
    try:
        assert purged.wait(1), "nearest persisted deadline was not executed"
        elapsed = time.monotonic() - started
        assert elapsed >= 0.10
        assert elapsed < 0.75
    finally:
        assert worker.stop(timeout=2) is True


def test_startup_entrypoint_reconciles_before_worker_start(monkeypatch):
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    corpus = importlib.import_module("tube_bridge.corpus")
    events = []
    monkeypatch.setattr(corpus, "reconcile_demo_corpora", lambda now=None: events.append("reconcile") or [])

    class FakeWorker:
        def start(self):
            events.append("start")

        def stop(self, timeout=2):
            events.append("stop")
            return True

        def wake(self):
            events.append("wake")

    monkeypatch.setattr(ttl, "_worker", FakeWorker())
    ttl.start_demo_ttl_worker()
    ttl.stop_demo_ttl_worker()
    assert events == ["reconcile", "start", "stop"]


def test_expiry_deletion_rolls_back_as_one_transaction_on_mid_delete_failure(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    seed_demo_corpus(corpus, "atomic", 1000.0, 1600.0, with_vector=True)
    original_get_conn = corpus._get_conn

    class FailingConnection:
        def __init__(self, conn):
            self._conn = conn

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def execute(self, sql, *args, **kwargs):
            normalized = " ".join(str(sql).split()).upper()
            if normalized.startswith("DELETE FROM CORPUS_ADDED_VIDEOS"):
                raise sqlite3.OperationalError("deterministic mid-delete failure")
            return self._conn.execute(sql, *args, **kwargs)

        def close(self):
            return self._conn.close()

        def commit(self):
            return self._conn.commit()

        def rollback(self):
            return self._conn.rollback()

    monkeypatch.setattr(corpus, "_get_conn", lambda: FailingConnection(original_get_conn()))
    with pytest.raises(sqlite3.OperationalError, match="mid-delete failure"):
        corpus.delete_expired_demo_corpora(now=1600.0)
    monkeypatch.setattr(corpus, "_get_conn", original_get_conn)

    with sqlite3.connect(corpus.DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) FROM corpora WHERE corpus_id='atomic'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM corpus_chunks WHERE corpus_id='atomic'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM corpus_added_videos WHERE corpus_id='atomic'").fetchone()[0] == 1
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='vec_atomic'").fetchone() is not None


def test_manual_delete_wakes_worker_and_moves_nearest_deadline(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path, demo_mode=True)
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    seed_demo_corpus(corpus, "first", 1000.0, 1600.0)
    seed_demo_corpus(corpus, "second", 1000.0, 1700.0)
    wakes = []
    monkeypatch.setattr(ttl, "wake_demo_ttl_worker", lambda: wakes.append("wake"))
    assert corpus.next_demo_expiry() == 1600.0
    corpus.corpus_delete("first")
    assert wakes == ["wake"]
    assert corpus.next_demo_expiry() == 1700.0
