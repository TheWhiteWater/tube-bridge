"""Shared pytest fixtures for tube-bridge deterministic contract tests.

Isolates environment paths and provides reusable test helpers without
live YouTube calls, embedding models, or Data API v3 upstreams.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


def pytest_configure(config):
    """Register custom markers to eliminate unknown-marker warnings."""
    config.addinivalue_line("markers", "slow: marks tests as slow (e.g. wheel build)")


@pytest.fixture
def isolated_cache_dir(monkeypatch):
    """Redirect TUBE_BRIDGE_CACHE to an isolated temp directory per test."""
    with tempfile.TemporaryDirectory(prefix="tube_bridge_test_") as tmp:
        monkeypatch.setenv("TUBE_BRIDGE_CACHE", tmp)
        yield Path(tmp)


@pytest.fixture
def temp_cache_dir():
    """Create an isolated temp directory for SQLite lifecycle tests."""
    with tempfile.TemporaryDirectory(prefix="tube_bridge_sqlite_test_") as tmp:
        yield Path(tmp)


@pytest.fixture
def isolated_sqlite_paths(monkeypatch):
    """Redirect cache and corpus SQLite paths to isolated temp directories.

    Imports tube_bridge.cache and tube_bridge.corpus, then monkeypatches
    their already-imported module globals (cache.CACHE_DIR, cache.DB_PATH,
    corpus.CACHE_DIR, corpus.DB_PATH) so every SQLite operation in the test
    touches only temp databases.  Environment-only mutation is forbidden
    because CACHE_DIR/DB_PATH are computed at import time.

    All four globals point to the same temporary root with separate
    cache.db and corpus.db database files.

    Keep sqlite3.connect proxy patches module-scoped — this fixture only
    handles path isolation.  No operation may touch ~/.tube_bridge.
    """
    with tempfile.TemporaryDirectory(prefix="tb_iso_cache_") as cache_tmp, \
         tempfile.TemporaryDirectory(prefix="tb_iso_corpus_") as corpus_tmp:

        cache_dir = Path(cache_tmp)
        corpus_dir = Path(corpus_tmp)

        import tube_bridge.cache as cache_mod
        import tube_bridge.corpus as corpus_mod

        # Monkeypatch already-imported module globals
        # All four must point to the same temp root with separate dbs
        monkeypatch.setattr(cache_mod, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(cache_mod, "DB_PATH", cache_dir / "cache.db")
        monkeypatch.setattr(corpus_mod, "CACHE_DIR", cache_dir)
        monkeypatch.setattr(corpus_mod, "DB_PATH", corpus_dir / "corpus.db")

        # Belt-and-suspenders: also set env for any late/dynamic imports
        monkeypatch.setenv("TUBE_BRIDGE_CACHE", str(cache_dir))

        yield {
            "cache_dir": cache_dir,
            "corpus_dir": corpus_dir,
        }


@pytest.fixture
def no_api_key(monkeypatch):
    """Ensure no YOUTUBE_API_KEY is set (zero-setup behaviour)."""
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    yield


@pytest.fixture
def with_api_key(monkeypatch):
    """Set a dummy YOUTUBE_API_KEY for Data-API-required tool dispatch."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "-".join(("unit", "test", "value")))
    yield


@pytest.fixture
def no_auth_key(monkeypatch):
    """Ensure no TUBE_BRIDGE_AUTH_KEY is set."""
    monkeypatch.delenv("TUBE_BRIDGE_AUTH_KEY", raising=False)
    yield


@pytest.fixture
def with_auth_key(monkeypatch):
    """Set a test TUBE_BRIDGE_AUTH_KEY."""
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-auth-token")
    yield


# ---------------------------------------------------------------------------
# SQLite Connection Spy (shared by test_sqlite_lifecycle)
# ---------------------------------------------------------------------------

class ConnectionSpy:
    """Wraps a sqlite3.Connection to track open/close lifecycle."""

    def __init__(self, conn, lifecycle_list):
        self._conn = conn
        self._lifecycle = lifecycle_list
        self._lifecycle.append(("open", id(conn)))
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if not self._closed:
            self._lifecycle.append(("close", id(self._conn)))
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


@pytest.fixture
def connection_spy():
    """Return a fresh lifecycle tracker list for ConnectionSpy."""
    return []


# ---------------------------------------------------------------------------
# SqliteProxy — delegating proxy for controlled execute/commit failure injection
# ---------------------------------------------------------------------------

class SqliteProxy:
    """Delegates to a real sqlite3.Connection with failure injection.

    Tracks open/close lifecycle. Can be configured to raise OperationalError
    on specific SQL execute patterns or on a specific commit number (1-indexed).

    Used exclusively by test_sqlite_lifecycle.py to test production-path
    operation-level failures without replacing _get_conn.
    """

    def __init__(self, conn, fail_on_execute_prefix=None,
                 fail_on_commit_number=None, lifecycle=None):
        self._conn = conn          # real sqlite3.Connection
        self._fail_on_execute_prefix = (fail_on_execute_prefix or "").upper()
        self._fail_on_commit_number = fail_on_commit_number
        self._commit_count = 0
        self._lifecycle = lifecycle if lifecycle is not None else []
        self._lifecycle.append(("open", id(self)))
        self._closed = False

    # ---- delegated attributes ----
    def __getattr__(self, name):
        return getattr(self._conn, name)

    # ---- controlled execute ----
    def execute(self, sql, *args, **kwargs):
        normalized = " ".join(str(sql).split()).upper()
        if self._fail_on_execute_prefix and \
           normalized.startswith(self._fail_on_execute_prefix):
            raise sqlite3.OperationalError(
                f"Simulated execute failure for: {str(sql)[:80]}")
        return self._conn.execute(sql, *args, **kwargs)

    # ---- controlled commit ----
    def commit(self):
        self._commit_count += 1
        if self._fail_on_commit_number is not None and \
           self._commit_count == self._fail_on_commit_number:
            raise sqlite3.OperationalError(
                f"Simulated commit failure on commit #{self._commit_count}")
        return self._conn.commit()

    # ---- lifecycle tracking ----
    def close(self):
        if not self._closed:
            self._lifecycle.append(("close", id(self)))
            self._closed = True
        return self._conn.close()


def _proxy_factory(fail_on_execute_prefix=None, fail_on_commit_number=None,
                   lifecycle=None):
    """Return a factory suitable for monkeypatching sqlite3.connect.

    The returned callable accepts (*args, **kwargs), opens a real connection
    via the original sqlite3.connect, wraps it in SqliteProxy, and returns
    the proxy.  The original is captured BEFORE monkeypatch runs so the
    factory never calls its own replacement recursively.

    All proxies created by this factory append to the shared `lifecycle` list.
    """
    _original_connect = sqlite3.connect   # capture before monkeypatch

    def _connect(*args, **kwargs):
        real_conn = _original_connect(*args, **kwargs)
        return SqliteProxy(
            real_conn,
            fail_on_execute_prefix=fail_on_execute_prefix,
            fail_on_commit_number=fail_on_commit_number,
            lifecycle=lifecycle,
        )
    return _connect
