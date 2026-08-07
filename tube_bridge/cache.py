"""tube-bridge — persistent SQLite cache for transcripts and video metadata."""

import json
import os
import sqlite3
import time
from pathlib import Path


CACHE_DIR = Path(os.environ.get("TUBE_BRIDGE_CACHE", Path.home() / ".tube_bridge"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = CACHE_DIR / "cache.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS transcripts ("
                 "video_id TEXT, lang TEXT, segments TEXT, language TEXT, is_generated INTEGER, cached_at REAL, "
                 "PRIMARY KEY (video_id, lang))")
    conn.execute("CREATE TABLE IF NOT EXISTS video_info ("
                 "video_id TEXT PRIMARY KEY, data TEXT, cached_at REAL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_video ON transcripts(video_id)")
    return conn


def get_transcript(video_id: str, lang: str | None = None) -> dict | None:
    """Get cached transcript. lang=None means 'any language'."""
    conn = _get_conn()
    lang_key = lang or "__any__"
    row = conn.execute("SELECT segments, language, is_generated FROM transcripts WHERE video_id=? AND lang=?",
                       (video_id, lang_key)).fetchone()
    if row:
        return {"segments": json.loads(row[0]), "language": row[1], "is_generated": bool(row[2]), "cached": True}
    return None


def set_transcript(video_id: str, lang: str | None, segments: list, language: str, is_generated: bool):
    """Cache a transcript."""
    conn = _get_conn()
    lang_key = lang or "__any__"
    conn.execute("INSERT OR REPLACE INTO transcripts VALUES (?, ?, ?, ?, ?, ?)",
                 (video_id, lang_key, json.dumps(segments), language, int(is_generated), time.time()))
    conn.commit()


def get_video_info(video_id: str) -> dict | None:
    """Get cached video metadata."""
    conn = _get_conn()
    row = conn.execute("SELECT data FROM video_info WHERE video_id=?", (video_id,)).fetchone()
    if row:
        return {**json.loads(row[0]), "cached": True}
    return None


def set_video_info(video_id: str, data: dict):
    """Cache video metadata."""
    conn = _get_conn()
    # Don't cache the 'cached' flag or source
    clean = {k: v for k, v in data.items() if k not in ("cached", "source", "_ytdlp_stderr")}
    conn.execute("INSERT OR REPLACE INTO video_info VALUES (?, ?, ?)",
                 (video_id, json.dumps(clean), time.time()))
    conn.commit()
