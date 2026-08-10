"""tube-bridge — scoped semantic search over YouTube transcripts (sqlite-vec + fastembed)."""

from contextlib import contextmanager

import hashlib
import json
import math
import os
import re
import sqlite3
import time
from typing import Any

import sqlite_vec

from .cache import CACHE_DIR

DB_PATH = CACHE_DIR / "corpus.db"

_CORPUS_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _validate_corpus_id(corpus_id: str) -> None:
    """corpus_id ends up interpolated into SQL identifiers (vec table names) —
    it must be restricted to a safe charset before it ever reaches a query string."""
    if not _CORPUS_ID_RE.match(corpus_id or ""):
        raise ValueError(
            f"Invalid corpus_id {corpus_id!r}: must match ^[A-Za-z0-9_-]{{1,128}}$"
        )


def _vec_table(corpus_id: str) -> str:
    """Return a collision-resistant SQL identifier for one corpus vector table."""
    _validate_corpus_id(corpus_id)
    digest = hashlib.sha256(corpus_id.encode("utf-8")).hexdigest()[:32]
    return f"vec_{digest}"


def _legacy_vec_table(corpus_id: str) -> str:
    """Return the pre-hash v1 table name used by released databases."""
    _validate_corpus_id(corpus_id)
    return f"vec_{corpus_id.replace('-', '_')}"


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _legacy_vec_dimension(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row or not row[0]:
        raise RuntimeError(f"Could not inspect legacy vector table {table}")
    match = re.search(
        r"vec0\s*\(\s*embedding\s+float\[(\d+)\]\s*\)",
        row[0],
        flags=re.IGNORECASE,
    )
    if not match:
        raise RuntimeError(f"Could not determine vector dimension for {table}")
    dimension = int(match.group(1))
    if dimension < 1:
        raise RuntimeError(f"Invalid vector dimension for {table}")
    return dimension


def _migrate_legacy_vec_tables(conn: sqlite3.Connection) -> None:
    """Split legacy dash/underscore tables into collision-free per-corpus tables."""
    groups: dict[str, list[str]] = {}
    for (corpus_id,) in conn.execute(
        "SELECT corpus_id FROM corpora ORDER BY corpus_id"
    ).fetchall():
        groups.setdefault(_legacy_vec_table(corpus_id), []).append(corpus_id)

    for legacy_table, corpus_ids in groups.items():
        if not _table_exists(conn, legacy_table):
            continue
        dimension = _legacy_vec_dimension(conn, legacy_table)
        for corpus_id in corpus_ids:
            target_table = _vec_table(corpus_id)
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {target_table} "
                f"USING vec0(embedding float[{dimension}])"
            )
            conn.execute(
                f"INSERT OR REPLACE INTO {target_table} (rowid, embedding) "
                f"SELECT v.rowid, v.embedding FROM {legacy_table} v "
                "JOIN corpus_chunks c ON c.id = v.rowid "
                "WHERE c.corpus_id = ?",
                (corpus_id,),
            )
        conn.execute(f"DROP TABLE {legacy_table}")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS corpora ("
            "corpus_id TEXT PRIMARY KEY, label TEXT, embedding_model TEXT, "
            "created_at REAL, expires_at REAL)"
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(corpora)").fetchall()
        }
        if "expires_at" not in columns:
            conn.execute("ALTER TABLE corpora ADD COLUMN expires_at REAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS corpus_chunks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, corpus_id TEXT NOT NULL, video_id TEXT NOT NULL, "
            "start_ts REAL, end_ts REAL, text TEXT, added_at REAL, "
            "UNIQUE(corpus_id, video_id, start_ts))"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS corpus_added_videos ("
            "corpus_id TEXT, video_id TEXT, added_at REAL, title TEXT, "
            "PRIMARY KEY(corpus_id, video_id))"
        )
        added_video_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(corpus_added_videos)"
            ).fetchall()
        }
        if "title" not in added_video_columns:
            conn.execute("ALTER TABLE corpus_added_videos ADD COLUMN title TEXT")
        _migrate_legacy_vec_tables(conn)
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


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

_embedding_model: Any = None
_embedding_dim: int = 0
_current_model_name = ""


def _get_embedding_model():
    """Lazy-load the embedding model (fastembed, offline, zero API keys)."""
    global _embedding_model, _embedding_dim, _current_model_name

    model_name = os.environ.get("TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    if _embedding_model is not None and _current_model_name == model_name:
        return _embedding_model, _embedding_dim

    from fastembed import TextEmbedding

    _embedding_model = TextEmbedding(model_name=model_name)
    _embedding_dim = len(list(_embedding_model.embed(["test"]))[0])
    _current_model_name = model_name
    return _embedding_model, _embedding_dim


def _embed(texts: list[str]) -> list[list[float]]:
    model, _ = _get_embedding_model()
    return [v.tolist() for v in model.embed(texts)]


# ---------------------------------------------------------------------------
# Chunking — by transcript segments, 60-90s windows
# ---------------------------------------------------------------------------


def _chunk_transcript(
    segments: list[dict], window_sec: int = 80, overlap_sec: int = 20
) -> list[dict]:
    """Chunk transcript segments into overlapping windows. Returns [{start_ts, end_ts, text}]."""
    if not segments:
        return []
    chunks = []
    window_end = segments[0]["start"] + window_sec
    buffer: list[dict] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if seg["start"] <= window_end:
            buffer.append(seg)
            i += 1
        else:
            if buffer:
                text = " ".join(s["text"] for s in buffer)
                chunks.append(
                    {
                        "start_ts": buffer[0]["start"],
                        "end_ts": buffer[-1]["start"] + buffer[-1].get("duration", 0),
                        "text": text,
                    }
                )
                # Overlap: move window back by overlap
                cutoff = buffer[-1]["start"] - overlap_sec
                buffer = [s for s in buffer if s["start"] >= cutoff]
            window_end = (
                buffer[0]["start"] + window_sec if buffer else seg["start"] + window_sec
            )
            # Guarantee forward progress: a caption gap larger than window_sec can leave
            # window_end short of seg's start even after the buffer trim above, which would
            # never admit seg and spin forever re-emitting the same chunk. Force the window
            # to at least cover the segment we're stuck on.
            if window_end < seg["start"]:
                buffer = []
                window_end = seg["start"] + window_sec
    if buffer:
        text = " ".join(s["text"] for s in buffer)
        chunks.append(
            {
                "start_ts": buffer[0]["start"],
                "end_ts": buffer[-1]["start"] + buffer[-1].get("duration", 0),
                "text": text,
            }
        )
    return chunks


# ---------------------------------------------------------------------------
# Corpus row helpers
# ---------------------------------------------------------------------------


def _delete_corpus_rows(conn: sqlite3.Connection, corpus_id: str) -> None:
    """Delete one corpus transactionally, including its vector table."""
    _validate_corpus_id(corpus_id)
    vec_table = _vec_table(corpus_id)
    conn.execute("DELETE FROM corpus_chunks WHERE corpus_id=?", (corpus_id,))
    conn.execute("DELETE FROM corpus_added_videos WHERE corpus_id=?", (corpus_id,))
    conn.execute("DELETE FROM corpora WHERE corpus_id=?", (corpus_id,))
    conn.execute(f"DROP TABLE IF EXISTS {vec_table}")


# ---------------------------------------------------------------------------
# Corpus operations
# ---------------------------------------------------------------------------


def corpus_create(corpus_id: str, label: str | None = None) -> dict:
    """Create a named, user-managed corpus with no forced expiry."""
    _validate_corpus_id(corpus_id)
    created_at = time.time()
    with _connection() as conn:
        _get_embedding_model()
        model_name = os.environ.get(
            "TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
        )
        try:
            conn.execute(
                "INSERT INTO corpora "
                "(corpus_id,label,embedding_model,created_at,expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (corpus_id, label or corpus_id, model_name, created_at, None),
            )
            conn.commit()
            return {
                "corpus_id": corpus_id,
                "status": "created",
                "embedding_model": model_name,
            }
        except sqlite3.IntegrityError:
            return {"corpus_id": corpus_id, "status": "already_exists"}


def corpus_add(
    corpus_id: str,
    video_id: str,
    segments: list[dict],
    force_reembed: bool = False,
    title: str | None = None,
) -> dict:
    """Add a transcript to a user-managed corpus. Idempotent."""
    _validate_corpus_id(corpus_id)
    current_model = os.environ.get(
        "TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
    )
    normalized_title = title.strip() if isinstance(title, str) and title.strip() else None

    # Validate before CPU-heavy embedding without holding a database lock.
    with _connection() as conn:
        row = conn.execute(
            "SELECT embedding_model FROM corpora WHERE corpus_id=?", (corpus_id,)
        ).fetchone()
        if not row:
            raise RuntimeError(
                f"Corpus '{corpus_id}' not found. Use corpus_create first."
            )
        if row[0] != current_model:
            raise RuntimeError(
                f"Corpus was created with '{row[0]}' but current model is "
                f"'{current_model}'. All chunks in a corpus must use the same "
                "embedding model."
            )
        existing = conn.execute(
            "SELECT 1 FROM corpus_added_videos WHERE corpus_id=? AND video_id=?",
            (corpus_id, video_id),
        ).fetchone()
        if existing and not force_reembed:
            return {
                "corpus_id": corpus_id,
                "video_id": video_id,
                "status": "already_indexed",
            }

    chunks = _chunk_transcript(segments)
    if not chunks:
        return {"corpus_id": corpus_id, "video_id": video_id, "status": "no_content"}
    embeddings = _embed([chunk["text"] for chunk in chunks])

    with _connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT embedding_model FROM corpora WHERE corpus_id=?", (corpus_id,)
        ).fetchone()
        if not row:
            raise RuntimeError(
                f"Corpus '{corpus_id}' not found. Use corpus_create first."
            )
        if row[0] != current_model:
            raise RuntimeError(
                f"Corpus was created with '{row[0]}' but current model is "
                f"'{current_model}'. All chunks in a corpus must use the same "
                "embedding model."
            )
        existing = conn.execute(
            "SELECT title FROM corpus_added_videos "
            "WHERE corpus_id=? AND video_id=?",
            (corpus_id, video_id),
        ).fetchone()
        if existing and not force_reembed:
            conn.rollback()
            return {
                "corpus_id": corpus_id,
                "video_id": video_id,
                "status": "already_indexed",
            }
        stored_title = normalized_title or (existing[0] if existing else None)
        vec_table = _vec_table(corpus_id)
        if force_reembed:
            old_chunk_ids = [
                old_row[0]
                for old_row in conn.execute(
                    "SELECT id FROM corpus_chunks "
                    "WHERE corpus_id=? AND video_id=?",
                    (corpus_id, video_id),
                ).fetchall()
            ]
            if old_chunk_ids and _table_exists(conn, vec_table):
                for chunk_id in old_chunk_ids:
                    conn.execute(
                        f"DELETE FROM {vec_table} WHERE rowid=?", (chunk_id,)
                    )
            conn.execute(
                "DELETE FROM corpus_chunks WHERE corpus_id=? AND video_id=?",
                (corpus_id, video_id),
            )
            conn.execute(
                "DELETE FROM corpus_added_videos WHERE corpus_id=? AND video_id=?",
                (corpus_id, video_id),
            )

        for chunk, embedding in zip(chunks, embeddings):
            conn.execute(
                "INSERT INTO corpus_chunks "
                "(corpus_id,video_id,start_ts,end_ts,text,added_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    corpus_id,
                    video_id,
                    chunk["start_ts"],
                    chunk["end_ts"],
                    chunk["text"],
                    time.time(),
                ),
            )
            chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table} "
                f"USING vec0(embedding float[{len(embedding)}])"
            )
            conn.execute(
                f"INSERT INTO {vec_table} (rowid, embedding) VALUES (?, ?)",
                (chunk_id, json.dumps(embedding)),
            )
        conn.execute(
            "INSERT OR REPLACE INTO corpus_added_videos "
            "(corpus_id,video_id,added_at,title) VALUES (?, ?, ?, ?)",
            (corpus_id, video_id, time.time(), stored_title),
        )
        conn.commit()

    return {
        "corpus_id": corpus_id,
        "video_id": video_id,
        "status": "indexed",
        "chunks": len(chunks),
    }


def _search_candidate_limit(*, top_k: int, total_chunks: int) -> int:
    """Bound ranking work while over-fetching enough candidates for diversity."""
    return min(total_chunks, max(top_k * 8, top_k + 32))


def _intervals_overlap(left: dict, right: dict) -> bool:
    """Return true only when two same-video timestamp intervals overlap."""
    if left["video_id"] != right["video_id"]:
        return False
    if None in (left["start_ts"], left["end_ts"], right["start_ts"], right["end_ts"]):
        return False
    return max(left["start_ts"], right["start_ts"]) < min(
        left["end_ts"], right["end_ts"]
    )


def _rank_search_candidates(candidates: list[dict], top_k: int) -> list[dict]:
    """Deduplicate overlaps, cap dominant videos, then deterministically refill."""
    deduplicated: list[dict] = []
    for candidate in candidates:
        if any(_intervals_overlap(candidate, kept) for kept in deduplicated):
            continue
        deduplicated.append(candidate)

    if len({candidate["video_id"] for candidate in deduplicated}) <= 1:
        return deduplicated[:top_k]

    max_per_video = math.ceil(top_k / 2)
    selected: list[dict] = []
    deferred: list[dict] = []
    source_counts: dict[str, int] = {}
    for candidate in deduplicated:
        video_id = candidate["video_id"]
        if source_counts.get(video_id, 0) < max_per_video and len(selected) < top_k:
            selected.append(candidate)
            source_counts[video_id] = source_counts.get(video_id, 0) + 1
        else:
            deferred.append(candidate)

    if len(selected) < top_k:
        selected.extend(deferred[: top_k - len(selected)])
    return selected


def corpus_search(corpus_id: str, query: str, top_k: int = 10) -> dict:
    """Semantic search with overlap deduplication and source-aware ranking."""
    _validate_corpus_id(corpus_id)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 50:
        raise ValueError("top_k must be an integer between 1 and 50")
    current_model = os.environ.get(
        "TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
    )
    with _connection() as conn:
        row = conn.execute(
            "SELECT embedding_model FROM corpora WHERE corpus_id=?", (corpus_id,)
        ).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found.")
        if row[0] != current_model:
            raise RuntimeError(
                f"Corpus '{corpus_id}' uses '{row[0]}' but current model is "
                f"'{current_model}'. Delete and recreate the corpus with the new model."
            )
        total_chunks = conn.execute(
            "SELECT COUNT(*) FROM corpus_chunks WHERE corpus_id=?", (corpus_id,)
        ).fetchone()[0]

    if total_chunks == 0:
        return {
            "corpus_id": corpus_id,
            "query": query,
            "total_results": 0,
            "chunks": [],
        }

    embedding = _embed([query])[0]
    vec_table = _vec_table(corpus_id)
    candidate_k = _search_candidate_limit(top_k=top_k, total_chunks=total_chunks)
    with _connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT embedding_model FROM corpora WHERE corpus_id=?", (corpus_id,)
        ).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found.")
        if row[0] != current_model:
            raise RuntimeError(
                f"Corpus '{corpus_id}' uses '{row[0]}' but current model is "
                f"'{current_model}'. Delete and recreate the corpus with the new model."
            )
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table} "
            f"USING vec0(embedding float[{len(embedding)}])"
        )
        serialized_embedding = json.dumps(embedding)
        results = conn.execute(
            f"""
            SELECT c.id, c.video_id, c.start_ts, c.end_ts, c.text,
                   av.title, v.distance
            FROM {vec_table} v
            JOIN corpus_chunks c ON c.id = v.rowid
            LEFT JOIN corpus_added_videos av
              ON av.corpus_id = c.corpus_id AND av.video_id = c.video_id
            WHERE v.embedding MATCH ? AND c.corpus_id = ? AND k = ?
            ORDER BY v.distance, c.video_id, c.start_ts, c.id
            """,
            (serialized_embedding, corpus_id, candidate_k),
        ).fetchall()
        if (
            candidate_k < total_chunks
            and len(results) == candidate_k
            and len(results) > 1
            and results[-1][6] == results[-2][6]
        ):
            # sqlite-vec chooses the KNN set before outer ORDER BY tie-breaks.
            # Only for a saturated observed boundary tie, rescore locally stored
            # vectors with the equivalent L2 scalar and apply stable SQL ordering.
            results = conn.execute(
                f"""
                SELECT c.id, c.video_id, c.start_ts, c.end_ts, c.text,
                       av.title, vec_distance_l2(v.embedding, ?) AS distance
                FROM {vec_table} v
                JOIN corpus_chunks c ON c.id = v.rowid
                LEFT JOIN corpus_added_videos av
                  ON av.corpus_id = c.corpus_id AND av.video_id = c.video_id
                WHERE c.corpus_id = ?
                ORDER BY distance, c.video_id, c.start_ts, c.id
                LIMIT ?
                """,
                (serialized_embedding, corpus_id, candidate_k),
            ).fetchall()
        conn.commit()

    candidates = []
    for row in results:
        video_url = f"https://youtube.com/watch?v={row[1]}"
        start_seconds = max(0, int(row[2] or 0))
        candidates.append(
            {
                "video_id": row[1],
                "title": row[5],
                "video_url": video_url,
                "timestamp_url": f"{video_url}&t={start_seconds}s",
                "start_ts": row[2],
                "end_ts": row[3],
                "text": row[4],
                "score": round(1.0 - row[6], 4) if row[6] is not None else 0.0,
            }
        )
    chunks = _rank_search_candidates(candidates, top_k)
    return {
        "corpus_id": corpus_id,
        "query": query,
        "total_results": len(chunks),
        "chunks": chunks,
    }


def corpus_list() -> dict:
    """List all available corpora with chunk counts."""
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT c.corpus_id, c.label, c.embedding_model, c.created_at,
                   COUNT(ch.id) as chunk_count,
                   COUNT(DISTINCT ch.video_id) as video_count
            FROM corpora c
            LEFT JOIN corpus_chunks ch ON ch.corpus_id = c.corpus_id
            GROUP BY c.corpus_id
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    corpora = [
        {
            "corpus_id": row[0],
            "label": row[1],
            "embedding_model": row[2],
            "created_at": row[3],
            "chunk_count": row[4],
            "video_count": row[5],
        }
        for row in rows
    ]
    return {"corpora": corpora, "total": len(corpora)}


def corpus_delete(corpus_id: str) -> dict:
    """Delete a corpus and all its chunks/vectors."""
    _validate_corpus_id(corpus_id)
    with _connection() as conn:
        _delete_corpus_rows(conn, corpus_id)
        conn.commit()
    return {"corpus_id": corpus_id, "status": "deleted"}
