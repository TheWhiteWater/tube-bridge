"""tube-bridge — scoped semantic search over YouTube transcripts (sqlite-vec + fastembed)."""

from contextlib import contextmanager

import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

import sqlite_vec

from .cache import CACHE_DIR
from . import demo_policy

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
    return f"vec_{corpus_id.replace('-', '_')}"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS corpora ("
                     "corpus_id TEXT PRIMARY KEY, label TEXT, embedding_model TEXT, "
                     "created_at REAL, expires_at REAL)")
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(corpora)").fetchall()
        }
        if "expires_at" not in columns:
            conn.execute("ALTER TABLE corpora ADD COLUMN expires_at REAL")
        conn.execute("CREATE TABLE IF NOT EXISTS corpus_chunks ("
                     "id INTEGER PRIMARY KEY AUTOINCREMENT, corpus_id TEXT NOT NULL, video_id TEXT NOT NULL, "
                     "start_ts REAL, end_ts REAL, text TEXT, added_at REAL, "
                     "UNIQUE(corpus_id, video_id, start_ts))")
        conn.execute("CREATE TABLE IF NOT EXISTS corpus_added_videos ("
                     "corpus_id TEXT, video_id TEXT, added_at REAL, PRIMARY KEY(corpus_id, video_id))")
        conn.commit()
        return conn
    except Exception:
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

def _chunk_transcript(segments: list[dict], window_sec: int = 80, overlap_sec: int = 20) -> list[dict]:
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
                chunks.append({"start_ts": buffer[0]["start"], "end_ts": buffer[-1]["start"] + buffer[-1].get("duration", 0), "text": text})
                # Overlap: move window back by overlap
                cutoff = buffer[-1]["start"] - overlap_sec
                buffer = [s for s in buffer if s["start"] >= cutoff]
            window_end = buffer[0]["start"] + window_sec if buffer else seg["start"] + window_sec
            # Guarantee forward progress: a caption gap larger than window_sec can leave
            # window_end short of seg's start even after the buffer trim above, which would
            # never admit seg and spin forever re-emitting the same chunk. Force the window
            # to at least cover the segment we're stuck on.
            if window_end < seg["start"]:
                buffer = []
                window_end = seg["start"] + window_sec
    if buffer:
        text = " ".join(s["text"] for s in buffer)
        chunks.append({"start_ts": buffer[0]["start"], "end_ts": buffer[-1]["start"] + buffer[-1].get("duration", 0), "text": text})
    return chunks


# ---------------------------------------------------------------------------
# Demo expiry helpers
# ---------------------------------------------------------------------------


def _delete_corpus_rows(conn: sqlite3.Connection, corpus_id: str) -> None:
    _validate_corpus_id(corpus_id)
    vec_table = _vec_table(corpus_id)
    # Keep virtual-table DDL last. If an earlier relational delete fails, no
    # vector table has been dropped; if DROP itself fails, the row deletes roll
    # back with the surrounding transaction.
    conn.execute("DELETE FROM corpus_chunks WHERE corpus_id=?", (corpus_id,))
    conn.execute("DELETE FROM corpus_added_videos WHERE corpus_id=?", (corpus_id,))
    conn.execute("DELETE FROM corpora WHERE corpus_id=?", (corpus_id,))
    conn.execute(f"DROP TABLE IF EXISTS {vec_table}")


def delete_expired_demo_corpora(now: float | None = None) -> list[str]:
    """Transactionally delete every demo corpus whose persisted deadline passed."""
    if not demo_policy.is_demo_mode():
        return []
    deadline = time.time() if now is None else now
    with _connection() as conn:
        # Reserve the writer before selecting IDs. Otherwise another connection
        # can recreate the same corpus_id with a fresh deadline between SELECT
        # and DELETE, and stale cleanup would remove the fresh corpus.
        conn.execute("BEGIN IMMEDIATE")
        corpus_ids = [
            row[0] for row in conn.execute(
                "SELECT corpus_id FROM corpora "
                "WHERE expires_at IS NOT NULL AND expires_at <= ? "
                "ORDER BY corpus_id",
                (deadline,),
            ).fetchall()
        ]
        for corpus_id in corpus_ids:
            _delete_corpus_rows(conn, corpus_id)
        conn.commit()
        return corpus_ids


def next_demo_expiry() -> float | None:
    if not demo_policy.is_demo_mode():
        return None
    with _connection() as conn:
        row = conn.execute(
            "SELECT MIN(expires_at) FROM corpora WHERE expires_at IS NOT NULL"
        ).fetchone()
        return None if row is None or row[0] is None else float(row[0])


def reconcile_demo_corpora(now: float | None = None) -> list[str]:
    """Restore deadlines after restart and purge anything already expired."""
    if not demo_policy.is_demo_mode():
        return []
    current = time.time() if now is None else now
    with _connection() as conn:
        conn.execute(
            "UPDATE corpora SET expires_at = created_at + ? "
            "WHERE expires_at IS NULL",
            (demo_policy.DEMO_CORPUS_TTL_SECONDS,),
        )
        corpus_ids = [
            row[0] for row in conn.execute(
                "SELECT corpus_id FROM corpora WHERE expires_at <= ? ORDER BY corpus_id",
                (current,),
            ).fetchall()
        ]
        for corpus_id in corpus_ids:
            _delete_corpus_rows(conn, corpus_id)
        conn.commit()
        return corpus_ids


def _purge_expired_if_demo() -> None:
    if demo_policy.is_demo_mode():
        delete_expired_demo_corpora(now=time.time())


# ---------------------------------------------------------------------------
# Corpus operations
# ---------------------------------------------------------------------------

def corpus_create(corpus_id: str, label: str | None = None) -> dict:
    """Create a named corpus, with a persisted deadline in demo mode."""
    _purge_expired_if_demo()
    _validate_corpus_id(corpus_id)
    created_at = time.time()
    expires_at = (
        created_at + demo_policy.DEMO_CORPUS_TTL_SECONDS
        if demo_policy.is_demo_mode() else None
    )
    created = False
    with _connection() as conn:
        _get_embedding_model()
        model_name = os.environ.get("TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        try:
            conn.execute(
                "INSERT INTO corpora "
                "(corpus_id,label,embedding_model,created_at,expires_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (corpus_id, label or corpus_id, model_name, created_at, expires_at),
            )
            conn.commit()
            created = True
            result = {"corpus_id": corpus_id, "status": "created", "embedding_model": model_name}
        except sqlite3.IntegrityError:
            result = {"corpus_id": corpus_id, "status": "already_exists"}
    if created and demo_policy.is_demo_mode():
        from . import demo_ttl
        demo_ttl.wake_demo_ttl_worker()
    return result


def corpus_add(corpus_id: str, video_id: str, segments: list[dict], force_reembed: bool = False) -> dict:
    """Add a video's transcript to a corpus. Chunks and embeds automatically. Idempotent.

    Embedding is intentionally outside the write transaction. A fresh
    BEGIN IMMEDIATE plus deadline re-check prevents the expiry worker from
    deleting the corpus between validation and inserts, which would otherwise
    leave orphan chunks after a long embedding operation.
    """
    _purge_expired_if_demo()
    _validate_corpus_id(corpus_id)
    current_model = os.environ.get("TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    # Cheap preflight before CPU-heavy embedding.
    with _connection() as conn:
        row = conn.execute(
            "SELECT embedding_model FROM corpora WHERE corpus_id=?",
            (corpus_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found. Use corpus_create first.")
        if row[0] != current_model:
            raise RuntimeError(
                f"Corpus was created with '{row[0]}' but current model is '{current_model}'. "
                "All chunks in a corpus must use the same embedding model."
            )
        existing = conn.execute(
            "SELECT 1 FROM corpus_added_videos WHERE corpus_id=? AND video_id=?",
            (corpus_id, video_id),
        ).fetchone()
        if existing and not force_reembed:
            return {"corpus_id": corpus_id, "video_id": video_id, "status": "already_indexed"}

    chunks = _chunk_transcript(segments)
    if not chunks:
        return {"corpus_id": corpus_id, "video_id": video_id, "status": "no_content"}
    embeddings = _embed([chunk["text"] for chunk in chunks])

    expired = False
    with _connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT embedding_model, expires_at FROM corpora WHERE corpus_id=?",
            (corpus_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found. Use corpus_create first.")
        if (
            demo_policy.is_demo_mode()
            and row[1] is not None
            and float(row[1]) <= time.time()
        ):
            _delete_corpus_rows(conn, corpus_id)
            conn.commit()
            expired = True
        else:
            if row[0] != current_model:
                raise RuntimeError(
                    f"Corpus was created with '{row[0]}' but current model is '{current_model}'. "
                    "All chunks in a corpus must use the same embedding model."
                )
            existing = conn.execute(
                "SELECT 1 FROM corpus_added_videos WHERE corpus_id=? AND video_id=?",
                (corpus_id, video_id),
            ).fetchone()
            if existing and not force_reembed:
                return {"corpus_id": corpus_id, "video_id": video_id, "status": "already_indexed"}
            if force_reembed:
                conn.execute(
                    "DELETE FROM corpus_chunks WHERE corpus_id=? AND video_id=?",
                    (corpus_id, video_id),
                )
                conn.execute(
                    "DELETE FROM corpus_added_videos WHERE corpus_id=? AND video_id=?",
                    (corpus_id, video_id),
                )

            vec_table = _vec_table(corpus_id)
            for chunk, emb in zip(chunks, embeddings):
                conn.execute(
                    "INSERT INTO corpus_chunks "
                    "(corpus_id,video_id,start_ts,end_ts,text,added_at) VALUES (?,?,?,?,?,?)",
                    (corpus_id, video_id, chunk["start_ts"], chunk["end_ts"], chunk["text"], time.time()),
                )
                chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table} "
                    f"USING vec0(embedding float[{len(emb)}])"
                )
                conn.execute(
                    f"INSERT INTO {vec_table} (rowid, embedding) VALUES (?, ?)",
                    (chunk_id, json.dumps(emb)),
                )

            conn.execute(
                "INSERT OR REPLACE INTO corpus_added_videos VALUES (?, ?, ?)",
                (corpus_id, video_id, time.time()),
            )
            if (
                demo_policy.is_demo_mode()
                and row[1] is not None
                and float(row[1]) <= time.time()
            ):
                _delete_corpus_rows(conn, corpus_id)
                expired = True
            conn.commit()
    if expired:
        raise RuntimeError(f"Corpus '{corpus_id}' not found. Use corpus_create first.")
    return {"corpus_id": corpus_id, "video_id": video_id, "status": "indexed", "chunks": len(chunks)}


def corpus_search(corpus_id: str, query: str, top_k: int = 10) -> dict:
    """Semantic search within a corpus. Returns chunks with scores, timestamps, video IDs."""
    _purge_expired_if_demo()
    _validate_corpus_id(corpus_id)
    current_model = os.environ.get("TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    # Validate before CPU-heavy embedding without holding a database lock.
    with _connection() as conn:
        row = conn.execute(
            "SELECT embedding_model FROM corpora WHERE corpus_id=?",
            (corpus_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found.")
        if row[0] != current_model:
            raise RuntimeError(
                f"Corpus '{corpus_id}' uses '{row[0]}' but current model is '{current_model}'. "
                "Delete and recreate the corpus with the new model."
            )

    emb = _embed([query])[0]
    vec_table = _vec_table(corpus_id)
    expired = False
    chunks = []
    with _connection() as conn:
        # Revalidate under a short write lock so expiry deletion cannot race the
        # vector query or its final deadline check.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT embedding_model, expires_at FROM corpora WHERE corpus_id=?",
            (corpus_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found.")
        if (
            demo_policy.is_demo_mode()
            and row[1] is not None
            and float(row[1]) <= time.time()
        ):
            _delete_corpus_rows(conn, corpus_id)
            conn.commit()
            expired = True
        else:
            if row[0] != current_model:
                raise RuntimeError(
                    f"Corpus '{corpus_id}' uses '{row[0]}' but current model is '{current_model}'. "
                    "Delete and recreate the corpus with the new model."
                )
            conn.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table} "
                f"USING vec0(embedding float[{len(emb)}])"
            )
            results = conn.execute(f"""
                SELECT c.id, c.video_id, c.start_ts, c.end_ts, c.text, v.distance
                FROM {vec_table} v
                JOIN corpus_chunks c ON c.id = v.rowid
                WHERE v.embedding MATCH ? AND c.corpus_id = ? AND k = ?
                ORDER BY v.distance
            """, (json.dumps(emb), corpus_id, top_k)).fetchall()
            chunks = [{
                "video_id": row[1],
                "start_ts": row[2],
                "end_ts": row[3],
                "text": row[4],
                "score": round(1.0 - row[5], 4) if row[5] is not None else 0.0,
            } for row in results]
            if (
                demo_policy.is_demo_mode()
                and row[1] is not None
                and float(row[1]) <= time.time()
            ):
                _delete_corpus_rows(conn, corpus_id)
                chunks = []
                expired = True
            conn.commit()
    if expired:
        raise RuntimeError(f"Corpus '{corpus_id}' not found.")
    return {
        "corpus_id": corpus_id,
        "query": query,
        "total_results": len(chunks),
        "chunks": chunks,
    }


def corpus_list() -> dict:
    """List all available corpora with chunk counts."""
    _purge_expired_if_demo()
    with _connection() as conn:
        rows = conn.execute("""
            SELECT c.corpus_id, c.label, c.embedding_model, c.created_at, COUNT(ch.id) as chunk_count,
                   COUNT(DISTINCT ch.video_id) as video_count
            FROM corpora c
            LEFT JOIN corpus_chunks ch ON ch.corpus_id = c.corpus_id
            GROUP BY c.corpus_id
            ORDER BY c.created_at DESC
        """).fetchall()
        corpora = []
        for r in rows:
            corpora.append({
                "corpus_id": r[0],
                "label": r[1],
                "embedding_model": r[2],
                "created_at": r[3],
                "chunk_count": r[4],
                "video_count": r[5],
            })
        return {"corpora": corpora, "total": len(corpora)}


def corpus_delete(corpus_id: str) -> dict:
    """Delete a corpus and all its chunks/vectors."""
    _validate_corpus_id(corpus_id)
    with _connection() as conn:
        _delete_corpus_rows(conn, corpus_id)
        conn.commit()
    if demo_policy.is_demo_mode():
        from . import demo_ttl
        demo_ttl.wake_demo_ttl_worker()
    return {"corpus_id": corpus_id, "status": "deleted"}
