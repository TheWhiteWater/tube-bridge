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
                     "corpus_id TEXT PRIMARY KEY, label TEXT, embedding_model TEXT, created_at REAL)")
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
# Corpus operations
# ---------------------------------------------------------------------------

def corpus_create(corpus_id: str, label: str | None = None) -> dict:
    """Create a named corpus."""
    _validate_corpus_id(corpus_id)
    with _connection() as conn:
        model, _ = _get_embedding_model()
        model_name = os.environ.get("TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        try:
            conn.execute("INSERT INTO corpora VALUES (?, ?, ?, ?)",
                         (corpus_id, label or corpus_id, model_name, time.time()))
            conn.commit()
            return {"corpus_id": corpus_id, "status": "created", "embedding_model": model_name}
        except sqlite3.IntegrityError:
            return {"corpus_id": corpus_id, "status": "already_exists"}


def corpus_add(corpus_id: str, video_id: str, segments: list[dict], force_reembed: bool = False) -> dict:
    """Add a video's transcript to a corpus. Chunks and embeds automatically. Idempotent."""
    _validate_corpus_id(corpus_id)
    with _connection() as conn:

        # Check corpus exists
        row = conn.execute("SELECT embedding_model FROM corpora WHERE corpus_id=?", (corpus_id,)).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found. Use corpus_create first.")
        corpus_model = row[0]

        # Check current model matches
        current_model = os.environ.get("TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        if corpus_model != current_model:
            raise RuntimeError(f"Corpus was created with '{corpus_model}' but current model is '{current_model}'. "
                               f"All chunks in a corpus must use the same embedding model.")

        # Check if already added (idempotent)
        existing = conn.execute("SELECT 1 FROM corpus_added_videos WHERE corpus_id=? AND video_id=?",
                                (corpus_id, video_id)).fetchone()
        if existing and not force_reembed:
            return {"corpus_id": corpus_id, "video_id": video_id, "status": "already_indexed"}

        # Remove old chunks if re-embedding
        if force_reembed:
            conn.execute("DELETE FROM corpus_chunks WHERE corpus_id=? AND video_id=?", (corpus_id, video_id))
            conn.execute("DELETE FROM corpus_added_videos WHERE corpus_id=? AND video_id=?", (corpus_id, video_id))

        # Chunk and embed
        chunks = _chunk_transcript(segments)
        if not chunks:
            return {"corpus_id": corpus_id, "video_id": video_id, "status": "no_content"}

        texts = [c["text"] for c in chunks]
        embeddings = _embed(texts)

        # Store chunks
        vec_table = _vec_table(corpus_id)
        for chunk, emb in zip(chunks, embeddings):
            conn.execute("INSERT INTO corpus_chunks (corpus_id, video_id, start_ts, end_ts, text, added_at) VALUES (?,?,?,?,?,?)",
                         (corpus_id, video_id, chunk["start_ts"], chunk["end_ts"], chunk["text"], time.time()))
            chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Store vector in sqlite-vec virtual table — one per corpus.
            # vec_table is safe to interpolate here: _validate_corpus_id() above
            # restricts corpus_id (and therefore vec_table) to [A-Za-z0-9_-]+.
            conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table} USING vec0(embedding float[{len(emb)}])")
            conn.execute(f"INSERT INTO {vec_table} (rowid, embedding) VALUES (?, ?)",
                         (chunk_id, json.dumps(emb)))

        conn.execute("INSERT OR REPLACE INTO corpus_added_videos VALUES (?, ?, ?)",
                     (corpus_id, video_id, time.time()))
        conn.commit()

        return {"corpus_id": corpus_id, "video_id": video_id, "status": "indexed", "chunks": len(chunks)}


def corpus_search(corpus_id: str, query: str, top_k: int = 10) -> dict:
    """Semantic search within a corpus. Returns chunks with scores, timestamps, video IDs."""
    _validate_corpus_id(corpus_id)
    with _connection() as conn:

        # Check corpus exists
        row = conn.execute("SELECT 1 FROM corpora WHERE corpus_id=?", (corpus_id,)).fetchone()
        if not row:
            raise RuntimeError(f"Corpus '{corpus_id}' not found.")

        # Check model match
        current_model = os.environ.get("TUBE_BRIDGE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        corpus_model = conn.execute("SELECT embedding_model FROM corpora WHERE corpus_id=?", (corpus_id,)).fetchone()[0]
        if corpus_model != current_model:
            raise RuntimeError(f"Corpus '{corpus_id}' uses '{corpus_model}' but current model is '{current_model}'. "
                               f"Delete and recreate the corpus with the new model.")

        # Embed query
        emb = _embed([query])[0]
        vec_table = _vec_table(corpus_id)  # safe: corpus_id validated above
        dim = len(emb)

        # Ensure vec table exists
        conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {vec_table} USING vec0(embedding float[{dim}])")

        # Search with metadata filtering — corpus_id filter BEFORE vector comparison
        # sqlite-vec supports WHERE clause on vec0 results via JOIN
        embedding_json = json.dumps(emb)
        results = conn.execute(f"""
            SELECT c.id, c.video_id, c.start_ts, c.end_ts, c.text, v.distance
            FROM {vec_table} v
            JOIN corpus_chunks c ON c.id = v.rowid
            WHERE v.embedding MATCH ? AND c.corpus_id = ? AND k = ?
            ORDER BY v.distance
        """, (embedding_json, corpus_id, top_k)).fetchall()

        chunks = []
        for r in results:
            chunks.append({
                "video_id": r[1],
                "start_ts": r[2],
                "end_ts": r[3],
                "text": r[4],
                "score": round(1.0 - r[5], 4) if r[5] is not None else 0.0,  # distance → similarity
            })

        return {
            "corpus_id": corpus_id,
            "query": query,
            "total_results": len(chunks),
            "chunks": chunks,
        }


def corpus_list() -> dict:
    """List all available corpora with chunk counts."""
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
        vec_table = _vec_table(corpus_id)  # safe: corpus_id validated above
        conn.execute(f"DROP TABLE IF EXISTS {vec_table}")
        conn.execute("DELETE FROM corpus_chunks WHERE corpus_id=?", (corpus_id,))
        conn.execute("DELETE FROM corpus_added_videos WHERE corpus_id=?", (corpus_id,))
        conn.execute("DELETE FROM corpora WHERE corpus_id=?", (corpus_id,))
        conn.commit()
        return {"corpus_id": corpus_id, "status": "deleted"}
