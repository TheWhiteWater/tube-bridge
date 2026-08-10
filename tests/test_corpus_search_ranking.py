"""Frozen Corpus v1 search-ranking and result-metadata contract.

Accepted policy after the four-video dogfood run:
- retrieve a bounded candidate pool: min(total_chunks, max(top_k * 8, top_k + 32));
- stable candidate order: distance, video_id, start_ts, chunk id;
- greedily suppress same-video intervals with strictly positive overlap;
- for multi-video corpora cap the first pass at ceil(top_k / 2) per video;
- refill from remaining deduplicated candidates when the cap leaves free slots;
- never cap a single-video corpus;
- accept only integer top_k from 1 through 50;
- add title and canonical video/timestamp URLs without changing tool arguments;
- capture titles from the local metadata cache only, never a new network lookup.

The tests preserve the five-tool surface, embedding model, source transcript
storage, and Corpus v2 boundary.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections import Counter
from pathlib import Path

import pytest


@pytest.fixture
def ranking_corpus(tmp_path: Path, monkeypatch):
    import tube_bridge.corpus as corpus

    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")
    monkeypatch.setattr(corpus, "_get_embedding_model", lambda: (object(), 2))
    monkeypatch.setattr(corpus, "_embed", lambda texts: [[1.0, 0.0] for _ in texts])
    return corpus


def _seed_candidates(corpus, corpus_id: str, candidates: list[dict]) -> None:
    created = corpus.corpus_create(corpus_id, corpus_id)
    assert created["status"] == "created"

    with corpus._connection() as conn:
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(corpus_added_videos)"
            ).fetchall()
        }
        if "title" not in columns:
            # Ranking tests need to reach current search behavior during RED.
            # Fresh-schema and legacy-migration tests independently require
            # production to add this nullable column.
            conn.execute("ALTER TABLE corpus_added_videos ADD COLUMN title TEXT")

        vec_table = corpus._vec_table(corpus_id)
        conn.execute(
            f"CREATE VIRTUAL TABLE {vec_table} USING vec0(embedding float[2])"
        )
        seen_videos: dict[str, str | None] = {}
        for candidate in candidates:
            video_id = candidate["video_id"]
            seen_videos.setdefault(video_id, candidate.get("title"))
            conn.execute(
                "INSERT INTO corpus_chunks "
                "(corpus_id,video_id,start_ts,end_ts,text,added_at) "
                "VALUES (?,?,?,?,?,0)",
                (
                    corpus_id,
                    video_id,
                    candidate["start_ts"],
                    candidate["end_ts"],
                    candidate["text"],
                ),
            )
            chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                f"INSERT INTO {vec_table} (rowid, embedding) VALUES (?, ?)",
                (chunk_id, json.dumps(candidate["embedding"])),
            )

        for video_id, title in seen_videos.items():
            conn.execute(
                "INSERT INTO corpus_added_videos "
                "(corpus_id,video_id,added_at,title) VALUES (?,?,0,?)",
                (corpus_id, video_id, title),
            )
        conn.commit()


def _candidate(video_id: str, start: float, similarity: float, *, title=None):
    return {
        "video_id": video_id,
        "title": title,
        "start_ts": start,
        "end_ts": start + 80.0,
        "text": f"{video_id} at {start}",
        "embedding": [similarity, 0.0],
    }


def test_search_suppresses_strictly_overlapping_windows_from_same_video(
    ranking_corpus,
):
    _seed_candidates(
        ranking_corpus,
        "overlap",
        [
            {
                **_candidate("video-a", 150.0, 1.0),
                "end_ts": 160.0,
            },
            {
                **_candidate("video-a", 0.0, 0.99),
                "end_ts": 200.0,
            },
            _candidate("video-b", 0.0, 0.90),
        ],
    )

    result = ranking_corpus.corpus_search("overlap", "context", top_k=3)

    assert [chunk["video_id"] for chunk in result["chunks"]] == [
        "video-a",
        "video-b",
    ]
    assert result["total_results"] == 2


def test_touching_windows_are_not_treated_as_overlapping(ranking_corpus):
    _seed_candidates(
        ranking_corpus,
        "touching",
        [
            {
                **_candidate("video-a", 0.0, 1.0),
                "end_ts": 10.0,
            },
            {
                **_candidate("video-a", 10.0, 0.99),
                "end_ts": 200.0,
            },
        ],
    )

    result = ranking_corpus.corpus_search("touching", "context", top_k=2)

    assert [chunk["start_ts"] for chunk in result["chunks"]] == [0.0, 10.0]


def test_reverse_ranked_touching_and_disjoint_windows_are_preserved(
    ranking_corpus,
):
    _seed_candidates(
        ranking_corpus,
        "reverse-boundaries",
        [
            {
                **_candidate("video-a", 100.0, 1.0),
                "end_ts": 110.0,
            },
            {
                **_candidate("video-a", 0.0, 0.99),
                "end_ts": 100.0,
            },
            {
                **_candidate("video-a", 120.0, 0.98),
                "end_ts": 130.0,
            },
        ],
    )

    result = ranking_corpus.corpus_search(
        "reverse-boundaries", "context", top_k=3
    )

    assert [chunk["start_ts"] for chunk in result["chunks"]] == [
        100.0,
        0.0,
        120.0,
    ]


def test_search_caps_one_video_when_other_sources_have_candidates(ranking_corpus):
    candidates = [
        _candidate("long-video", float(index * 100), 1.0 - index * 0.01)
        for index in range(6)
    ]
    candidates.extend(
        [
            _candidate("short-video-b", 0.0, 0.85),
            _candidate("short-video-c", 0.0, 0.80),
        ]
    )
    _seed_candidates(ranking_corpus, "diverse", candidates)

    result = ranking_corpus.corpus_search("diverse", "compare methods", top_k=4)
    counts = Counter(chunk["video_id"] for chunk in result["chunks"])

    assert [chunk["video_id"] for chunk in result["chunks"]] == [
        "long-video",
        "long-video",
        "short-video-b",
        "short-video-c",
    ]
    assert counts["long-video"] == 2  # ceil(4 / 2)


def test_search_refills_when_diversity_cap_leaves_free_slots(ranking_corpus):
    _seed_candidates(
        ranking_corpus,
        "refill",
        [
            *[
                _candidate("video-a", float(index * 100), 1.0 - index * 0.01)
                for index in range(5)
            ],
            _candidate("video-b", 0.0, 0.70),
        ],
    )

    result = ranking_corpus.corpus_search("refill", "topic", top_k=5)

    assert [
        (chunk["video_id"], chunk["start_ts"])
        for chunk in result["chunks"]
    ] == [
        ("video-a", 0.0),
        ("video-a", 100.0),
        ("video-a", 200.0),
        ("video-b", 0.0),
        ("video-a", 300.0),
    ]


def test_single_video_search_can_still_fill_top_k(ranking_corpus):
    _seed_candidates(
        ranking_corpus,
        "single",
        [
            _candidate("only-video", float(index * 100), 1.0 - index * 0.01)
            for index in range(4)
        ],
    )

    result = ranking_corpus.corpus_search("single", "specific topic", top_k=3)

    assert len(result["chunks"]) == 3
    assert {chunk["video_id"] for chunk in result["chunks"]} == {"only-video"}


def test_equal_scores_have_stable_order_independent_of_insertion(ranking_corpus):
    forward = [
        _candidate("video-c", 20.0, 1.0),
        _candidate("video-a", 100.0, 1.0),
        _candidate("video-a", 10.0, 1.0),
        _candidate("video-b", 10.0, 1.0),
    ]
    _seed_candidates(ranking_corpus, "ties-forward", forward)
    _seed_candidates(ranking_corpus, "ties-reverse", list(reversed(forward)))

    def key(chunk):
        return chunk["video_id"], chunk["start_ts"]

    first = ranking_corpus.corpus_search(
        "ties-forward", "same score", top_k=4
    )["chunks"]
    second = ranking_corpus.corpus_search(
        "ties-reverse", "same score", top_k=4
    )["chunks"]

    assert list(map(key, first)) == list(map(key, second))
    assert list(map(key, first)) == [
        ("video-a", 10.0),
        ("video-a", 100.0),
        ("video-b", 10.0),
        ("video-c", 20.0),
    ]


def test_candidate_pool_is_bounded_and_top_k_is_validated(
    ranking_corpus, monkeypatch
):
    candidate_limit = getattr(ranking_corpus, "_search_candidate_limit", None)
    assert candidate_limit is not None
    assert candidate_limit(top_k=1, total_chunks=10_000) == 33
    assert candidate_limit(top_k=10, total_chunks=10_000) == 80
    assert candidate_limit(top_k=50, total_chunks=10_000) == 400
    assert candidate_limit(top_k=50, total_chunks=17) == 17

    ranking_corpus.corpus_create("bounds")
    for invalid in (True, 0, -1, 51, 1.5):
        with pytest.raises(ValueError, match="top_k"):
            ranking_corpus.corpus_search("bounds", "query", top_k=invalid)

    _seed_candidates(
        ranking_corpus,
        "bounded-query",
        [
            _candidate("only-video", float(index * 100), 1.0 - index * 0.001)
            for index in range(40)
        ],
    )
    match_k: list[int] = []
    original_get_conn = ranking_corpus._get_conn

    class ExecuteSpy:
        def __init__(self, conn):
            self._conn = conn

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def execute(self, sql, params=()):
            if " MATCH " in " ".join(str(sql).split()).upper():
                match_k.append(params[2])
            return self._conn.execute(sql, params)

        def close(self):
            return self._conn.close()

    monkeypatch.setattr(
        ranking_corpus,
        "_get_conn",
        lambda: ExecuteSpy(original_get_conn()),
    )

    _seed_candidates(
        ranking_corpus,
        "bounded-small",
        [
            _candidate("only-video", float(index * 100), 1.0 - index * 0.001)
            for index in range(17)
        ],
    )

    ranking_corpus.corpus_search("bounded-query", "query", top_k=1)
    ranking_corpus.corpus_search("bounded-query", "query", top_k=3)
    ranking_corpus.corpus_search("bounded-small", "query", top_k=10)
    assert match_k == [33, 35, 17]


def test_corpus_tool_surface_and_search_bounds_remain_exact():
    from tube_bridge.server import TOOL_CATALOG

    corpus_tools = {
        tool.name: tool.inputSchema
        for tool in TOOL_CATALOG
        if tool.name.startswith("corpus_")
    }
    expected = {
        "corpus_create": ({"corpus_id", "label"}, {"corpus_id"}),
        "corpus_add": (
            {"corpus_id", "url", "force_reembed"},
            {"corpus_id", "url"},
        ),
        "corpus_search": (
            {"corpus_id", "query", "top_k"},
            {"corpus_id", "query"},
        ),
        "corpus_list": (set(), set()),
        "corpus_delete": ({"corpus_id"}, {"corpus_id"}),
    }

    assert set(corpus_tools) == set(expected)
    for name, (properties, required) in expected.items():
        assert set(corpus_tools[name]["properties"]) == properties
        assert set(corpus_tools[name].get("required", [])) == required

    top_k = corpus_tools["corpus_search"]["properties"]["top_k"]
    assert top_k["default"] == 10
    assert top_k["minimum"] == 1
    assert top_k["maximum"] == 50
    assert (
        corpus_tools["corpus_add"]["properties"]["force_reembed"]["default"]
        is False
    )


def test_search_returns_title_and_canonical_timestamp_urls(ranking_corpus):
    _seed_candidates(
        ranking_corpus,
        "metadata",
        [
            {
                **_candidate("dQw4w9WgXcQ", 12.9, 1.0),
                "title": "Example Video",
            }
        ],
    )

    chunk = ranking_corpus.corpus_search(
        "metadata", "inspect", top_k=1
    )["chunks"][0]

    assert chunk["title"] == "Example Video"
    assert chunk["video_url"] == "https://youtube.com/watch?v=dQw4w9WgXcQ"
    assert chunk["timestamp_url"] == (
        "https://youtube.com/watch?v=dQw4w9WgXcQ&t=12s"
    )


def test_fresh_schema_has_nullable_title_column(ranking_corpus):
    conn = ranking_corpus._get_conn()
    try:
        rows = conn.execute("PRAGMA table_info(corpus_added_videos)").fetchall()
    finally:
        conn.close()

    title = next((row for row in rows if row[1] == "title"), None)
    assert title is not None
    assert title[3] == 0  # SQLite PRAGMA table_info.notnull


def test_populated_legacy_database_migrates_idempotently_and_remains_searchable(
    tmp_path, monkeypatch
):
    import sqlite_vec
    import tube_bridge.corpus as corpus

    db_path = tmp_path / "old-corpus.db"
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
    conn.execute(
        "INSERT INTO corpora VALUES ('legacy','Legacy',"
        "'BAAI/bge-small-en-v1.5',0,NULL)"
    )
    conn.execute(
        "INSERT INTO corpus_chunks "
        "(corpus_id,video_id,start_ts,end_ts,text,added_at) "
        "VALUES ('legacy','legacy-video',7.5,30,'legacy passage',0)"
    )
    chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO corpus_added_videos VALUES "
        "('legacy','legacy-video',123)"
    )
    conn.execute("CREATE VIRTUAL TABLE vec_legacy USING vec0(embedding float[2])")
    conn.execute(
        "INSERT INTO vec_legacy (rowid,embedding) VALUES (?,?)",
        (chunk_id, json.dumps([1.0, 0.0])),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(corpus, "DB_PATH", db_path)
    monkeypatch.setattr(corpus, "_embed", lambda texts: [[1.0, 0.0] for _ in texts])

    for _ in range(2):
        migrated = corpus._get_conn()
        try:
            title = next(
                row
                for row in migrated.execute(
                    "PRAGMA table_info(corpus_added_videos)"
                ).fetchall()
                if row[1] == "title"
            )
            marker = migrated.execute(
                "SELECT added_at,title FROM corpus_added_videos "
                "WHERE corpus_id='legacy' AND video_id='legacy-video'"
            ).fetchone()
        finally:
            migrated.close()
        assert title[3] == 0
        assert marker == (123.0, None)

    chunk = corpus.corpus_search("legacy", "passage", top_k=1)["chunks"][0]
    assert chunk["title"] is None
    assert chunk["timestamp_url"].endswith("&t=7s")


class _CommitFailProxy:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def commit(self):
        raise sqlite3.OperationalError("simulated title transaction failure")

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def test_title_round_trip_and_force_reembed_preserves_known_title(ranking_corpus):
    ranking_corpus.corpus_create("round-trip")
    first = [{"text": "first", "start": 0.0, "duration": 1.0}]
    second = [{"text": "second", "start": 100.0, "duration": 1.0}]

    ranking_corpus.corpus_add(
        "round-trip", "video-id", first, False, "Stored Title"
    )
    assert ranking_corpus.corpus_search(
        "round-trip", "first", top_k=1
    )["chunks"][0]["title"] == "Stored Title"

    ranking_corpus.corpus_add(
        "round-trip", "video-id", second, True, None
    )
    chunk = ranking_corpus.corpus_search(
        "round-trip", "second", top_k=1
    )["chunks"][0]
    assert chunk["title"] == "Stored Title"
    assert chunk["start_ts"] == 100.0


def test_title_and_chunks_roll_back_atomically_on_initial_add_failure(
    ranking_corpus, monkeypatch
):
    ranking_corpus.corpus_create("initial-failure")
    original_get_conn = ranking_corpus._get_conn
    monkeypatch.setattr(
        ranking_corpus,
        "_get_conn",
        lambda: _CommitFailProxy(original_get_conn()),
    )

    with pytest.raises(sqlite3.OperationalError, match="title transaction failure"):
        ranking_corpus.corpus_add(
            "initial-failure",
            "video-id",
            [{"text": "new", "start": 0.0, "duration": 1.0}],
            False,
            "Transactional Title",
        )

    verify = sqlite3.connect(ranking_corpus.DB_PATH)
    try:
        assert verify.execute(
            "SELECT COUNT(*) FROM corpus_chunks WHERE corpus_id='initial-failure'"
        ).fetchone()[0] == 0
        assert verify.execute(
            "SELECT COUNT(*) FROM corpus_added_videos "
            "WHERE corpus_id='initial-failure'"
        ).fetchone()[0] == 0
    finally:
        verify.close()


def test_force_reembed_failure_preserves_old_title_chunks_and_vectors(
    ranking_corpus, monkeypatch
):
    ranking_corpus.corpus_create("force-failure")
    ranking_corpus.corpus_add(
        "force-failure",
        "video-id",
        [{"text": "old", "start": 0.0, "duration": 1.0}],
        False,
        "Old Title",
    )
    original_get_conn = ranking_corpus._get_conn
    monkeypatch.setattr(
        ranking_corpus,
        "_get_conn",
        lambda: _CommitFailProxy(original_get_conn()),
    )

    with pytest.raises(sqlite3.OperationalError, match="title transaction failure"):
        ranking_corpus.corpus_add(
            "force-failure",
            "video-id",
            [{"text": "new", "start": 100.0, "duration": 1.0}],
            True,
            "New Title",
        )

    verify = original_get_conn()
    try:
        assert verify.execute(
            "SELECT title FROM corpus_added_videos "
            "WHERE corpus_id='force-failure' AND video_id='video-id'"
        ).fetchone() == ("Old Title",)
        assert verify.execute(
            "SELECT start_ts,text FROM corpus_chunks "
            "WHERE corpus_id='force-failure' AND video_id='video-id'"
        ).fetchall() == [(0.0, "old")]
        vec_table = ranking_corpus._vec_table("force-failure")
        assert verify.execute(
            f"SELECT COUNT(*) FROM {vec_table}"
        ).fetchone()[0] == 1
    finally:
        verify.close()


@pytest.mark.asyncio
async def test_corpus_add_uses_cache_only_title_lookup_in_worker_thread(monkeypatch):
    import tube_bridge.corpus as corpus
    import tube_bridge.tools as tools

    segments = [{"text": "hello", "start": 0.0, "duration": 1.0}]
    captured: list[tuple] = []
    lookup_threads: list[int] = []
    main_thread = threading.get_ident()
    monkeypatch.setattr(
        tools,
        "_get_transcript_with_meta",
        lambda video_id, lang: {
            "segments": segments,
            "language": "en",
            "is_generated": True,
        },
    )

    def cached_video_info(video_id: str):
        lookup_threads.append(threading.get_ident())
        return {"id": video_id, "title": "Captured Title"}

    network_calls: list[str] = []

    async def forbidden_network_video_info(video_id: str):
        network_calls.append("video_info")
        raise AssertionError("corpus_add must not start a metadata network lookup")

    def fake_corpus_add(*args):
        captured.append(args)
        return {"status": "indexed"}

    monkeypatch.setattr(tools.cache, "get_video_info", cached_video_info)
    monkeypatch.setattr(tools, "video_info", forbidden_network_video_info)
    monkeypatch.setattr(corpus, "corpus_add", fake_corpus_add)

    result = await tools.corpus_add("test", "video-id", False)

    assert result == {"status": "indexed"}
    assert captured == [
        ("test", "video-id", segments, False, "Captured Title")
    ]
    assert lookup_threads and lookup_threads[0] != main_thread
    assert network_calls == []


@pytest.mark.asyncio
async def test_corpus_add_cache_miss_does_not_start_metadata_network_lookup(
    monkeypatch,
):
    import tube_bridge.corpus as corpus
    import tube_bridge.tools as tools

    segments = [{"text": "hello", "start": 0.0, "duration": 1.0}]
    captured: list[tuple] = []
    monkeypatch.setattr(
        tools,
        "_get_transcript_with_meta",
        lambda video_id, lang: {
            "segments": segments,
            "language": "en",
            "is_generated": True,
        },
    )

    network_calls: list[str] = []

    def forbidden_network(*args, **kwargs):
        network_calls.append("sync-network")
        raise AssertionError("cache miss must not start metadata network access")

    async def forbidden_async_network(*args, **kwargs):
        network_calls.append("async-network")
        raise AssertionError("cache miss must not start metadata network access")

    def fake_corpus_add(*args):
        captured.append(args)
        return {"status": "indexed"}

    monkeypatch.setattr(tools.cache, "get_video_info", lambda video_id: None)
    monkeypatch.setattr(tools.api, "get_api_key", lambda: "configured-test-key")
    monkeypatch.setattr(tools, "video_info", forbidden_async_network)
    monkeypatch.setattr(tools, "_video_info_cached", forbidden_network)
    monkeypatch.setattr(tools.api, "get_video_info", forbidden_network)
    monkeypatch.setattr(tools.yt, "run_ytdlp", forbidden_network)
    monkeypatch.setattr(corpus, "corpus_add", fake_corpus_add)

    result = await tools.corpus_add("test", "video-id", False)

    assert result == {"status": "indexed"}
    assert captured == [("test", "video-id", segments, False, None)]
    assert network_calls == []


@pytest.mark.asyncio
async def test_corpus_add_continues_when_optional_cached_title_lookup_fails(
    monkeypatch,
):
    import tube_bridge.corpus as corpus
    import tube_bridge.tools as tools

    segments = [{"text": "hello", "start": 0.0, "duration": 1.0}]
    captured: list[tuple] = []
    monkeypatch.setattr(
        tools,
        "_get_transcript_with_meta",
        lambda video_id, lang: {
            "segments": segments,
            "language": "en",
            "is_generated": True,
        },
    )

    def failing_cached_video_info(video_id: str):
        raise sqlite3.OperationalError("metadata cache unavailable")

    network_calls: list[str] = []

    def forbidden_network(*args, **kwargs):
        network_calls.append("sync-network")
        raise AssertionError("cache failure must not start metadata network access")

    async def forbidden_async_network(*args, **kwargs):
        network_calls.append("async-network")
        raise AssertionError("cache failure must not start metadata network access")

    def fake_corpus_add(*args):
        captured.append(args)
        return {"status": "indexed"}

    monkeypatch.setattr(tools.cache, "get_video_info", failing_cached_video_info)
    monkeypatch.setattr(tools.api, "get_api_key", lambda: "configured-test-key")
    monkeypatch.setattr(tools, "video_info", forbidden_async_network)
    monkeypatch.setattr(tools, "_video_info_cached", forbidden_network)
    monkeypatch.setattr(tools.api, "get_video_info", forbidden_network)
    monkeypatch.setattr(tools.yt, "run_ytdlp", forbidden_network)
    monkeypatch.setattr(corpus, "corpus_add", fake_corpus_add)

    result = await tools.corpus_add("test", "video-id", False)

    assert result == {"status": "indexed"}
    assert captured == [("test", "video-id", segments, False, None)]
    assert network_calls == []
