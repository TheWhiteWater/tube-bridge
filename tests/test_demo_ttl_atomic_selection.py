"""Frozen RED addendum for atomic expiry selection and deletion."""

import hashlib
import importlib
import json
import sqlite3
import threading
import time
from pathlib import Path


def test_cleanup_cannot_delete_concurrently_recreated_fresh_corpus(monkeypatch, tmp_path):
    corpus = importlib.import_module("tube_bridge.corpus")
    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setattr(corpus, "_get_embedding_model", lambda: (object(), 2))
    monkeypatch.setattr(corpus.time, "time", lambda: 1000.0)
    assert corpus.corpus_create("same_id")["status"] == "created"

    original_get_conn = corpus._get_conn
    delete_reached = threading.Event()
    first_attempt_done = threading.Event()
    recreated = threading.Event()
    first_outcome = {}

    def recreate_after_cleanup_select():
        assert delete_reached.wait(2)
        deadline = time.monotonic() + 3
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            conn = sqlite3.connect(corpus.DB_PATH, timeout=0.02)
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM corpora WHERE corpus_id=?", ("same_id",))
                conn.execute(
                    "INSERT INTO corpora "
                    "(corpus_id,label,embedding_model,created_at,expires_at) "
                    "VALUES (?,?,?,?,?)",
                    ("same_id", "fresh", "BAAI/bge-small-en-v1.5", 1601.0, 2201.0),
                )
                conn.commit()
                if attempt == 1:
                    first_outcome["value"] = "acquired"
                    first_attempt_done.set()
                recreated.set()
                return
            except sqlite3.OperationalError as exc:
                conn.rollback()
                assert "locked" in str(exc).lower()
                if attempt == 1:
                    first_outcome["value"] = "locked"
                    first_attempt_done.set()
                time.sleep(0.01)
            finally:
                conn.close()
        raise AssertionError("concurrent recreate never acquired the database")

    thread = threading.Thread(target=recreate_after_cleanup_select, daemon=True)
    thread.start()

    armed = {"value": True}

    def instrumented_get_conn():
        conn = original_get_conn()

        def authorizer(action, arg1, arg2, database, trigger):
            if armed["value"] and action == sqlite3.SQLITE_DELETE:
                armed["value"] = False
                delete_reached.set()
                # Do not release cleanup until the concurrent transaction has
                # explicitly reported whether it acquired the write reservation
                # (vulnerable source) or observed the expected lock (fixed source).
                if not first_attempt_done.wait(2):
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        conn.set_authorizer(authorizer)
        return conn

    monkeypatch.setattr(corpus, "_get_conn", instrumented_get_conn)
    assert corpus.delete_expired_demo_corpora(now=1601.0) == ["same_id"]
    thread.join(4)
    assert not thread.is_alive()
    assert recreated.is_set()
    assert first_outcome["value"] in {"acquired", "locked"}

    with sqlite3.connect(corpus.DB_PATH) as conn:
        row = conn.execute(
            "SELECT label, expires_at FROM corpora WHERE corpus_id=?", ("same_id",),
        ).fetchone()
    assert row == ("fresh", 2201.0)


def test_all_prior_python_freezes_remain_byte_identical():
    expected = {
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json":
            "c2e2278f3f802abcbca107491f79e3ccd5eac1a71a2ccb970d01b37ba1a60fa9",
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00029-demo-hardening-001-python.json":
            "32456b9c43cbb11b6eebe210ee1d42c4328c6175e79441fe74a15538728baa81",
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00037-ttl-race-addendum-001-python.json":
            "653a9e82e4f4910a069eac0a1ada145b38337fedc072038a14d990c4e5036dac",
    }
    for path, expected_hash in expected.items():
        manifest_path = Path(path)
        assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == expected_hash
        manifest = json.loads(manifest_path.read_text())
        for item in manifest["test_files"]:
            assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() == item["sha256"]
