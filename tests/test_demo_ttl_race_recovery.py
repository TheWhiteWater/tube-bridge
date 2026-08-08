"""Frozen RED addendum for deadline crossing and TTL worker recovery."""

import hashlib
import importlib
import json
import sqlite3
import threading

import pytest


def prepare_corpus(monkeypatch, tmp_path):
    corpus = importlib.import_module("tube_bridge.corpus")
    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setattr(corpus, "_get_embedding_model", lambda: (object(), 2))
    monkeypatch.setattr(corpus, "_embed", lambda texts: [[0.0, 0.0] for _ in texts])
    return corpus


def create_public_corpus(monkeypatch, corpus, corpus_id, with_content=False):
    """Seed through public corpus operations rather than private SQL helpers."""
    monkeypatch.setattr(corpus.time, "time", lambda: 1000.0)
    assert corpus.corpus_create(corpus_id)["status"] == "created"
    if with_content:
        result = corpus.corpus_add(
            corpus_id,
            "seed-video",
            [{"text": "seed text", "start": 0.0, "duration": 1.0}],
        )
        assert result["status"] == "indexed"


def assert_corpus_fully_absent(corpus, corpus_id):
    """Verify documented storage entities contain no orphaned demo data."""
    with sqlite3.connect(corpus.DB_PATH) as conn:
        for table in ("corpora", "corpus_chunks", "corpus_added_videos"):
            assert conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE corpus_id=?", (corpus_id,),
            ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name LIKE 'vec_%'",
        ).fetchone()[0] == 0


def test_corpus_add_crossing_deadline_cannot_commit_orphan_data(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path)
    create_public_corpus(monkeypatch, corpus, "add_race")
    calls = {"count": 0}

    def crossing_clock():
        calls["count"] += 1
        # Lazy pre-purge and post-embedding write-lock check occur before the
        # deadline. Insert timestamps/final commit check occur after it.
        return 1599.0 if calls["count"] <= 2 else 1601.0

    monkeypatch.setattr(corpus.time, "time", crossing_clock)
    with pytest.raises(RuntimeError, match="not found"):
        corpus.corpus_add(
            "add_race",
            "new-video",
            [{"text": "new", "start": 0.0, "duration": 1.0}],
        )
    assert_corpus_fully_absent(corpus, "add_race")


def test_corpus_search_crossing_deadline_cannot_return_results(monkeypatch, tmp_path):
    corpus = prepare_corpus(monkeypatch, tmp_path)
    create_public_corpus(monkeypatch, corpus, "search_race", with_content=True)
    crossed = {"value": False}
    monkeypatch.setattr(
        corpus.time, "time", lambda: 1601.0 if crossed["value"] else 1599.0,
    )

    def slow_embed(texts):
        crossed["value"] = True
        return [[0.0, 0.0] for _ in texts]

    monkeypatch.setattr(corpus, "_embed", slow_embed)
    with pytest.raises(RuntimeError, match="not found"):
        corpus.corpus_search("search_race", "query", 1)
    assert_corpus_fully_absent(corpus, "search_race")


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_worker_recovers_after_transient_deadline_lookup_error(monkeypatch):
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    corpus = importlib.import_module("tube_bridge.corpus")
    attempts = {"lookup": 0}
    purged = threading.Event()

    def next_expiry():
        attempts["lookup"] += 1
        if attempts["lookup"] == 1:
            raise sqlite3.OperationalError("transient lookup lock")
        return None if purged.is_set() else 0.0

    monkeypatch.setattr(corpus, "next_demo_expiry", next_expiry)
    monkeypatch.setattr(
        corpus,
        "delete_expired_demo_corpora",
        lambda now=None: purged.set() or ["recovered"],
    )
    worker = ttl.DemoTTLWorker(clock=lambda: 0.0)
    worker.start()
    try:
        assert purged.wait(2), "worker died instead of recovering from lookup error"
        assert attempts["lookup"] >= 2
    finally:
        assert worker.stop(timeout=2) is True


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_worker_recovers_after_transient_purge_error(monkeypatch):
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    corpus = importlib.import_module("tube_bridge.corpus")
    attempts = {"purge": 0}
    purged = threading.Event()
    monkeypatch.setattr(corpus, "next_demo_expiry", lambda: None if purged.is_set() else 0.0)

    def purge(now=None):
        attempts["purge"] += 1
        if attempts["purge"] == 1:
            raise sqlite3.OperationalError("transient purge lock")
        purged.set()
        return ["recovered"]

    monkeypatch.setattr(corpus, "delete_expired_demo_corpora", purge)
    worker = ttl.DemoTTLWorker(clock=lambda: 0.0)
    worker.start()
    try:
        assert purged.wait(2), "worker died instead of retrying purge"
        assert attempts["purge"] >= 2
    finally:
        assert worker.stop(timeout=2) is True


def test_prior_frozen_manifests_and_listed_files_remain_byte_identical():
    from pathlib import Path
    expected_manifests = {
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json":
            "c2e2278f3f802abcbca107491f79e3ccd5eac1a71a2ccb970d01b37ba1a60fa9",
        ".brainops/methodology/frozen-tests/frozen-tdd-wi-00029-demo-hardening-001-python.json":
            "32456b9c43cbb11b6eebe210ee1d42c4328c6175e79441fe74a15538728baa81",
    }
    for path, expected_hash in expected_manifests.items():
        manifest_path = Path(path)
        assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == expected_hash
        manifest = json.loads(manifest_path.read_text())
        mismatches = [
            item["path"] for item in manifest["test_files"]
            if hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest() != item["sha256"]
        ]
        assert mismatches == []
