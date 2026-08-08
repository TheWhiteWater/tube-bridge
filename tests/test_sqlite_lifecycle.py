"""SQLite connection lifecycle contract tests — exact open==close for every public operation.

Pack C Second Remediation: every cache and corpus public operation must close
every opened connection on success, miss, early-return, and exception paths.
Tests use isolated globals with spy-wrapped _get_conn to track lifecycle.
Commit failure tests additionally open a fresh connection after failure and
assert target row absent (rollback/no partial data).

Cache matrix: transcript hit, miss, set; video hit, miss, set.
Corpus matrix: create success, create already_exists, list, delete,
add nonexistent, add already_indexed early, add no_content early,
search nonexistent.

Failure matrix: cache commit failure, corpus commit failure,
representative operation execute failure close.
No model download.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Inline spy / proxy (self-contained, isolate from conftest)
# ---------------------------------------------------------------------------

class ConnectionSpy:
    """Wraps a sqlite3.Connection to track open/close lifecycle."""

    def __init__(self, conn, lifecycle_list):
        self._conn = conn
        self._lifecycle = lifecycle_list
        self._lifecycle.append(("open",))
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if not self._closed:
            self._lifecycle.append(("close",))
            self._closed = True
        return self._conn.close()

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def commit(self, *args, **kwargs):
        return self._conn.commit(*args, **kwargs)

    def rollback(self, *args, **kwargs):
        return self._conn.rollback(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def enable_load_extension(self, *args, **kwargs):
        return self._conn.enable_load_extension(*args, **kwargs)


class SqliteProxy:
    """Delegates to a real sqlite3.Connection with failure injection.

    Tracks open/close lifecycle. Can be configured to raise OperationalError
    on specific SQL execute patterns or on a specific commit number (1-indexed).
    """

    def __init__(self, conn, fail_on_execute_prefix=None,
                 fail_on_commit_number=None, lifecycle=None):
        self._conn = conn
        self._fail_on_execute_prefix = (fail_on_execute_prefix or "").upper()
        self._fail_on_commit_number = fail_on_commit_number
        self._commit_count = 0
        self._lifecycle = lifecycle if lifecycle is not None else []
        self._lifecycle.append(("open",))
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, sql, *args, **kwargs):
        normalized = " ".join(str(sql).split()).upper()
        if self._fail_on_execute_prefix and \
           normalized.startswith(self._fail_on_execute_prefix):
            raise sqlite3.OperationalError(
                f"Simulated execute failure for: {str(sql)[:80]}")
        return self._conn.execute(sql, *args, **kwargs)

    def commit(self):
        self._commit_count += 1
        if self._fail_on_commit_number is not None and \
           self._commit_count == self._fail_on_commit_number:
            raise sqlite3.OperationalError(
                f"Simulated commit failure on commit #{self._commit_count}")
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if not self._closed:
            self._lifecycle.append(("close",))
            self._closed = True
        return self._conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lifecycle():
    """Fresh lifecycle tracker list for ConnectionSpy/SqliteProxy."""
    return []


@pytest.fixture
def isolated_cache(monkeypatch):
    """Isolate tube_bridge.cache module globals to a temp directory."""
    with tempfile.TemporaryDirectory(prefix="tb_cache_test_") as tmp:
        cache_dir = Path(tmp)

        import tube_bridge.cache as cache_mod

        monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(cache_mod, "DB_PATH", cache_dir / "cache.db")
        monkeypatch.setenv("TUBE_BRIDGE_CACHE", str(cache_dir))

        yield {"cache_dir": cache_dir, "module": cache_mod}


@pytest.fixture
def isolated_corpus(monkeypatch):
    """Isolate tube_bridge.corpus module globals to a temp directory."""
    with tempfile.TemporaryDirectory(prefix="tb_corpus_test_") as tmp:
        corpus_dir = Path(tmp)

        import tube_bridge.corpus as corpus_mod

        monkeypatch.setattr(corpus_mod, "CACHE_DIR", corpus_dir)
        monkeypatch.setattr(corpus_mod, "DB_PATH", corpus_dir / "corpus.db")

        # Prevent model download: mock _get_embedding_model and _embed
        class MockEmbeddingModel:
            """Fake embedding model that returns zero vectors of dimension 384."""
            def embed(self, texts):
                import numpy as np
                return [np.zeros(384, dtype=np.float32) for _ in texts]

        mock_model = MockEmbeddingModel()
        monkeypatch.setattr(corpus_mod, "_embedding_model", mock_model)
        monkeypatch.setattr(corpus_mod, "_embedding_dim", 384)
        monkeypatch.setattr(corpus_mod, "_current_model_name",
                            "BAAI/bge-small-en-v1.5")

        def _mock_get_embedding_model():
            return mock_model, 384

        monkeypatch.setattr(corpus_mod, "_get_embedding_model",
                            _mock_get_embedding_model)

        # Also mock _embed to return zero vectors
        def _mock_embed(texts):
            return [[0.0] * 384 for _ in texts]

        monkeypatch.setattr(corpus_mod, "_embed", _mock_embed)

        yield {"corpus_dir": corpus_dir, "module": corpus_mod}


def _spy_get_conn(original_get_conn, lifecycle):
    """Return a wrapper that calls original_get_conn and wraps result in ConnectionSpy."""
    def wrapper():
        conn = original_get_conn()
        return ConnectionSpy(conn, lifecycle)
    return wrapper


# ===========================================================================
# Cache lifecycle tests
# ===========================================================================

class TestCacheTranscriptLifecycle:
    """Cache get_transcript hit/miss/set — every call closes its connection."""

    def test_transcript_miss_closes_connection(self, isolated_cache, lifecycle, monkeypatch):
        """get_transcript with no cached data closes connection."""
        cache_mod = isolated_cache["module"]
        original = cache_mod._get_conn
        monkeypatch.setattr(cache_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = cache_mod.get_transcript("vid_miss", "en")
        assert result is None

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on miss"
        )

    def test_transcript_hit_closes_connection(self, isolated_cache, lifecycle, monkeypatch):
        """get_transcript with cached data closes connection."""
        cache_mod = isolated_cache["module"]
        sample_segments = [{"text": "hello", "start": 0.0, "duration": 1.0}]

        # Seed the cache using a direct connection
        import json, time
        seed_conn = sqlite3.connect(str(isolated_cache["cache_dir"] / "cache.db"))
        seed_conn.execute("PRAGMA journal_mode=WAL")
        seed_conn.execute(
            "CREATE TABLE IF NOT EXISTS transcripts ("
            "video_id TEXT, lang TEXT, segments TEXT, language TEXT, "
            "is_generated INTEGER, cached_at REAL, "
            "PRIMARY KEY (video_id, lang))")
        seed_conn.execute(
            "INSERT INTO transcripts VALUES (?, ?, ?, ?, ?, ?)",
            ("vid_hit", "en", json.dumps(sample_segments), "en", 0, time.time()))
        seed_conn.commit()
        seed_conn.close()

        original = cache_mod._get_conn
        monkeypatch.setattr(cache_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = cache_mod.get_transcript("vid_hit", "en")
        assert result is not None
        assert result["cached"] is True

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on hit"
        )

    def test_transcript_set_closes_connection(self, isolated_cache, lifecycle, monkeypatch):
        """set_transcript closes its connection."""
        cache_mod = isolated_cache["module"]
        sample_segments = [{"text": "world", "start": 1.0, "duration": 2.0}]

        original = cache_mod._get_conn
        monkeypatch.setattr(cache_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        cache_mod.set_transcript("vid_set", "en", sample_segments, "en", False)

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on set"
        )


class TestCacheVideoLifecycle:
    """Cache get_video_info hit/miss/set — every call closes its connection."""

    def test_video_info_miss_closes_connection(self, isolated_cache, lifecycle, monkeypatch):
        """get_video_info with no cached data closes connection."""
        cache_mod = isolated_cache["module"]
        original = cache_mod._get_conn
        monkeypatch.setattr(cache_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = cache_mod.get_video_info("vid_noexist")
        assert result is None

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on video_info miss"
        )

    def test_video_info_hit_closes_connection(self, isolated_cache, lifecycle, monkeypatch):
        """get_video_info with cached data closes connection."""
        cache_mod = isolated_cache["module"]
        import json, time

        seed_conn = sqlite3.connect(str(isolated_cache["cache_dir"] / "cache.db"))
        seed_conn.execute("PRAGMA journal_mode=WAL")
        seed_conn.execute(
            "CREATE TABLE IF NOT EXISTS video_info ("
            "video_id TEXT PRIMARY KEY, data TEXT, cached_at REAL)")
        seed_conn.execute(
            "INSERT INTO video_info VALUES (?, ?, ?)",
            ("vid_hit_v", json.dumps({"title": "Test"}), time.time()))
        seed_conn.commit()
        seed_conn.close()

        original = cache_mod._get_conn
        monkeypatch.setattr(cache_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = cache_mod.get_video_info("vid_hit_v")
        assert result is not None

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on video_info hit"
        )

    def test_video_info_set_closes_connection(self, isolated_cache, lifecycle, monkeypatch):
        """set_video_info closes its connection."""
        cache_mod = isolated_cache["module"]

        original = cache_mod._get_conn
        monkeypatch.setattr(cache_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        cache_mod.set_video_info("vid_set_v", {"title": "Set Test", "views": 100})

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on video_info set"
        )


# ===========================================================================
# Cache failure injection tests
# ===========================================================================

class TestCacheCommitFailure:
    """Cache set operations: commit failure => rollback, no partial data."""

    def test_set_transcript_commit_failure_rolls_back(self, isolated_cache, monkeypatch):
        """set_transcript with commit failure does not leave partial data."""
        cache_mod = isolated_cache["module"]
        lifecycle = []

        original = cache_mod._get_conn
        def failing_get_conn():
            conn = original()
            return SqliteProxy(conn, fail_on_commit_number=1, lifecycle=lifecycle)
        monkeypatch.setattr(cache_mod, "_get_conn", failing_get_conn)

        sample_segments = [{"text": "partial", "start": 0.0, "duration": 1.0}]
        with pytest.raises(sqlite3.OperationalError, match="Simulated commit failure"):
            cache_mod.set_transcript("vid_fail_commit", "en",
                                     sample_segments, "en", False)

        # Verify connection was closed despite failure
        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on commit failure"
        )

        # Open a fresh connection and assert target row absent (rollback)
        verify_conn = sqlite3.connect(
            str(isolated_cache["cache_dir"] / "cache.db"))
        verify_conn.execute("PRAGMA journal_mode=WAL")
        row = verify_conn.execute(
            "SELECT 1 FROM transcripts WHERE video_id=? AND lang=?",
            ("vid_fail_commit", "en")).fetchone()
        verify_conn.close()
        assert row is None, (
            "commit failure must roll back: row should not exist in DB"
        )

    def test_set_video_info_commit_failure_rolls_back(self, isolated_cache, monkeypatch):
        """set_video_info with commit failure does not leave partial data."""
        cache_mod = isolated_cache["module"]
        lifecycle = []

        original = cache_mod._get_conn
        def failing_get_conn():
            conn = original()
            return SqliteProxy(conn, fail_on_commit_number=1, lifecycle=lifecycle)
        monkeypatch.setattr(cache_mod, "_get_conn", failing_get_conn)

        with pytest.raises(sqlite3.OperationalError, match="Simulated commit failure"):
            cache_mod.set_video_info("vid_fail_commit_v",
                                     {"title": "Partial Commit"})

        # Verify connection closed
        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on commit failure"
        )

        # Fresh connection: assert row absent
        verify_conn = sqlite3.connect(
            str(isolated_cache["cache_dir"] / "cache.db"))
        verify_conn.execute("PRAGMA journal_mode=WAL")
        row = verify_conn.execute(
            "SELECT 1 FROM video_info WHERE video_id=?",
            ("vid_fail_commit_v",)).fetchone()
        verify_conn.close()
        assert row is None, (
            "commit failure must roll back: row should not exist in DB"
        )


class TestCacheExecuteFailureClose:
    """Representative operation execute failure: connection must close."""

    def test_get_transcript_execute_failure_closes(self, isolated_cache, monkeypatch):
        """When get_transcript hits an OperationalError on execute, the connection closes."""
        cache_mod = isolated_cache["module"]
        lifecycle = []

        original = cache_mod._get_conn
        def failing_get_conn():
            conn = original()
            return SqliteProxy(conn,
                               fail_on_execute_prefix="SELECT SEGMENTS",
                               lifecycle=lifecycle)
        monkeypatch.setattr(cache_mod, "_get_conn", failing_get_conn)

        with pytest.raises(sqlite3.OperationalError, match="Simulated execute failure"):
            cache_mod.get_transcript("vid_exec_fail", "en")

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on execute failure"
        )


# ===========================================================================
# Corpus lifecycle tests
# ===========================================================================

class TestCorpusCreateLifecycle:
    """Corpus create success and already_exists — each path closes connection."""

    def test_create_success_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_create success closes its connection."""
        corpus_mod = isolated_corpus["module"]
        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = corpus_mod.corpus_create("my-corpus", "My Corpus")
        assert result["status"] == "created"

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on create"
        )

    def test_create_already_exists_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_create when corpus already exists closes connection."""
        corpus_mod = isolated_corpus["module"]

        # First create (no spy)
        corpus_mod.corpus_create("dup-corpus")

        # Second create (with spy)
        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = corpus_mod.corpus_create("dup-corpus")
        assert result["status"] == "already_exists"

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on already_exists"
        )


class TestCorpusListDeleteLifecycle:
    """Corpus list and delete — each closes connection."""

    def test_list_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_list closes its connection."""
        corpus_mod = isolated_corpus["module"]
        corpus_mod.corpus_create("list-corpus")

        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = corpus_mod.corpus_list()
        assert result["total"] >= 1

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on list"
        )

    def test_delete_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_delete closes its connection."""
        corpus_mod = isolated_corpus["module"]
        corpus_mod.corpus_create("del-corpus")

        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = corpus_mod.corpus_delete("del-corpus")
        assert result["status"] == "deleted"

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on delete"
        )


class TestCorpusAddLifecycle:
    """Corpus add success and early-return paths close every connection."""

    def test_add_success_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        corpus_mod = isolated_corpus["module"]
        corpus_mod.corpus_create("add-corpus")
        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn", _spy_get_conn(original, lifecycle))
        segments = [{"text": "hello world", "start": 0.0, "duration": 1.0}]
        result = corpus_mod.corpus_add("add-corpus", "vid_ok", segments)
        assert result["status"] == "indexed"
        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, f"open={opens} close={closes} — connection leak on add success"

    def test_add_nonexistent_corpus_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_add with nonexistent corpus raises RuntimeError and closes connection."""
        corpus_mod = isolated_corpus["module"]
        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        with pytest.raises(RuntimeError, match="not found"):
            corpus_mod.corpus_add("no-such-corpus", "vid1", [])

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on add nonexistent"
        )

    def test_add_already_indexed_early_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_add returns already_indexed early and closes connection."""
        corpus_mod = isolated_corpus["module"]
        corpus_mod.corpus_create("idx-corpus")

        # First add seeds the video
        sample_segments = [{"text": "hello", "start": 0.0, "duration": 1.0}]
        corpus_mod.corpus_add("idx-corpus", "vid_dup", sample_segments)

        # Second add with spy — should return already_indexed
        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = corpus_mod.corpus_add("idx-corpus", "vid_dup", sample_segments)
        assert result["status"] == "already_indexed"

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on already_indexed"
        )

    def test_add_no_content_early_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_add with empty segments returns no_content early and closes connection."""
        corpus_mod = isolated_corpus["module"]
        corpus_mod.corpus_create("empty-corpus")

        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        result = corpus_mod.corpus_add("empty-corpus", "vid_empty", [])
        assert result["status"] == "no_content"

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on no_content"
        )


class TestCorpusSearchLifecycle:
    """Corpus search success and missing-corpus paths close connections."""

    def test_search_success_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        corpus_mod = isolated_corpus["module"]
        corpus_mod.corpus_create("search-corpus")
        corpus_mod.corpus_add(
            "search-corpus", "vid_search",
            [{"text": "searchable text", "start": 0.0, "duration": 1.0}],
        )
        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn", _spy_get_conn(original, lifecycle))
        result = corpus_mod.corpus_search("search-corpus", "searchable", top_k=1)
        assert "chunks" in result
        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, f"open={opens} close={closes} — connection leak on search success"

    def test_search_nonexistent_corpus_closes_connection(self, isolated_corpus, lifecycle, monkeypatch):
        """corpus_search with nonexistent corpus raises RuntimeError and closes connection."""
        corpus_mod = isolated_corpus["module"]
        original = corpus_mod._get_conn
        monkeypatch.setattr(corpus_mod, "_get_conn",
                            _spy_get_conn(original, lifecycle))

        with pytest.raises(RuntimeError, match="not found"):
            corpus_mod.corpus_search("no-such-corpus", "test query")

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on search nonexistent"
        )


# ===========================================================================
# Corpus failure injection tests
# ===========================================================================

class TestCorpusCommitFailure:
    """Corpus commit failure => rollback, no partial data."""

    def test_corpus_add_commit_failure_rolls_back(self, isolated_corpus, monkeypatch):
        """corpus_add: commit failure during chunk insertion leaves no partial data."""
        corpus_mod = isolated_corpus["module"]
        lifecycle = []

        corpus_mod.corpus_create("commit-fail-corpus")

        original = corpus_mod._get_conn
        def failing_get_conn():
            conn = original()
            return SqliteProxy(conn, fail_on_commit_number=1, lifecycle=lifecycle)
        monkeypatch.setattr(corpus_mod, "_get_conn", failing_get_conn)

        sample_segments = [{"text": "partial chunk", "start": 0.0, "duration": 2.0}]
        with pytest.raises(sqlite3.OperationalError, match="Simulated commit failure"):
            corpus_mod.corpus_add("commit-fail-corpus", "vid_cfail", sample_segments)

        # Verify connection closed
        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on commit failure"
        )

        # Open a fresh connection and verify every relational/vector write rolled back.
        verify_conn = sqlite3.connect(str(isolated_corpus["corpus_dir"] / "corpus.db"))
        try:
            for table in ("corpus_chunks", "corpus_added_videos"):
                row = verify_conn.execute(
                    f"SELECT 1 FROM {table} WHERE corpus_id=? AND video_id=?",
                    ("commit-fail-corpus", "vid_cfail"),
                ).fetchone()
                assert row is None, f"commit failure left partial row in {table}"
            vec_name = "vec_commit_fail_corpus"
            exists = verify_conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (vec_name,)
            ).fetchone()
            if exists:
                assert verify_conn.execute(f"SELECT count(*) FROM {vec_name}").fetchone()[0] == 0
        finally:
            verify_conn.close()


class TestCorpusExecuteFailureClose:
    """Representative corpus operation execute failure: connection closes."""

    def test_corpus_list_execute_failure_closes(self, isolated_corpus, monkeypatch):
        """When corpus_list hits an OperationalError on execute, the connection closes."""
        corpus_mod = isolated_corpus["module"]
        lifecycle = []

        corpus_mod.corpus_create("exec-fail-corpus")

        original = corpus_mod._get_conn
        def failing_get_conn():
            conn = original()
            return SqliteProxy(conn,
                               fail_on_execute_prefix="SELECT C.CORPUS_ID",
                               lifecycle=lifecycle)
        monkeypatch.setattr(corpus_mod, "_get_conn", failing_get_conn)

        with pytest.raises(sqlite3.OperationalError, match="Simulated execute failure"):
            corpus_mod.corpus_list()

        opens = sum(1 for e in lifecycle if e[0] == "open")
        closes = sum(1 for e in lifecycle if e[0] == "close")
        assert opens == closes, (
            f"open={opens} close={closes} — connection leak on execute failure"
        )
