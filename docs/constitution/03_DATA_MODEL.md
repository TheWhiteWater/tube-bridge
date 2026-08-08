# 03 — Data Model

## VideoInfo (internal)

```python
@dataclass
class VideoInfo:
    id: str                       # YouTube video ID (expected 11 chars; not enforced)
    title: str                    # Video title
    url: str                      # Full watch URL
    duration: int | None = None   # Seconds
    view_count: int | None = None
    channel: str | None = None    # Channel name
    channel_url: str | None = None
    upload_date: str | None = None  # YYYYMMDD
    description: str | None = None  # Truncated to 500 chars
    thumbnail: str | None = None
    categories: list[str] | None = None
    tags: list[str] | None = None   # Max 20
```

`to_dict()`: `{k: v for k, v in self.__dict__.items() if v is not None}`.

`extract_video_id()` in `tube_bridge/youtube/client.py` expects 11-char IDs via `[A-Za-z0-9_-]{11}`; the dataclass does not enforce length.

Source authorities: `VideoInfo` in `tube_bridge/youtube/models.py` and `extract_video_id()` in `tube_bridge/youtube/client.py`.

---

## Public Response Envelopes

All tools return JSON via `TextContent`. Schemas are not frozen; breaking changes require an ADR.

### Source field rules
- `"source"` — which upstream provided the data (API or yt-dlp); present on dual-source results.
- `"cached": true` — on `video_info` when from persistent cache (`cache.db` line 52). NOT on transcript results: `cache.get_transcript()` includes `"cached": true` (line 34) but `_get_transcript_cached` discards it before the public envelope (tools.py 264–268).
- `"_warning"` — yt-dlp path when stderr captured and results empty.
- `"_ytdlp_stderr"` — `video_info` when yt-dlp stderr captured. Not stored in cache.db.

### youtube_search

**API path** (`"source": "YouTube Data API v3"`, key + quota):
```json
{"query": "python tutorial", "source": "YouTube Data API v3", "total_results": 10,
 "next_page_token": "CAUQAA",
 "videos": [{"id": "kqtD5dpn9C8", "title": "Python for Beginners",
   "url": "https://youtube.com/watch?v=kqtD5dpn9C8", "channel": "Programming with Mosh",
   "channel_id": "UC...", "published_at": "2019-02-18T15:00:17Z",
   "description": "Learn Python basics...", "thumbnail": "https://i.ytimg.com/..."}]}
```

**yt-dlp fallback** (`"source": "yt-dlp (anonymous)"`):
```json
{"query": "python tutorial", "source": "yt-dlp (anonymous)", "total_results": 10,
 "videos": [{"id": "kqtD5dpn9C8", "title": "Python for Beginners",
   "url": "https://youtube.com/watch?v=kqtD5dpn9C8", "duration": 3662,
   "view_count": 24903766, "channel": "Programming with Mosh",
   "channel_url": "https://youtube.com/@programmingwithmosh", "upload_date": "20190218"}]}
```

| Field provenance | API | yt-dlp |
|-----------------|-----|--------|
| channel_id, published_at, description (≤200c), thumbnail, next_page_token | ✓ | — |
| duration, view_count, channel_url, upload_date | — | ✓ |

API-only filters (`order`, `published_after`, `published_before`, `channel_id`, `video_duration`) apply only to API calls.

### youtube_get_video_info

**API path** (`"source": "YouTube Data API v3"`):
```json
{"id": "jNQXAC9IVRw", "title": "Me at the zoo",
 "url": "https://youtube.com/watch?v=jNQXAC9IVRw", "duration": 19,
 "view_count": 403439184, "channel": "jawed", "channel_id": "UC4QobU6STFB0P71TQx8DzYQ",
 "channel_url": "https://youtube.com/channel/UC4QobU6STFB0P71TQx8DzYQ",
 "upload_date": "20050424", "description": "The first ever YouTube video...",
 "thumbnail": "https://i.ytimg.com/...", "tags": ["elephant", "zoo"],
 "source": "YouTube Data API v3"}
```

**yt-dlp fallback** (or cached):
```json
{"id": "jNQXAC9IVRw", "title": "Me at the zoo",
 "url": "https://youtube.com/watch?v=jNQXAC9IVRw", "duration": 19,
 "view_count": 403439184, "channel": "jawed",
 "channel_url": "https://youtube.com/@jawed", "upload_date": "20050423",
 "description": "The first ever YouTube video...", "thumbnail": "https://i.ytimg.com/...",
 "categories": ["Pets & Animals"], "tags": ["elephant", "zoo"]}
```
When cached, `"cached": true` appears. Cached results strip `source` and `_ytdlp_stderr` before storage (cache.py 59–61).

| Field provenance | API | yt-dlp |
|-----------------|-----|--------|
| channel_id, source | ✓ | — |
| categories | — | ✓ |
| _ytdlp_stderr (when stderr captured) | — | ✓ |
| cached (when from cache.db) | ✓ | ✓ |

### youtube_get_trending

**API path** (`"source": "YouTube Data API v3 (mostPopular, US)"`):
```json
{"source": "YouTube Data API v3 (mostPopular, US)", "total_results": 10,
 "videos": [{"id": "abc123...", "title": "...", "url": "https://youtube.com/watch?v=abc123...",
   "channel": "...", "channel_id": "UC...", "published_at": "...",
   "thumbnail": "https://i.ytimg.com/..."}]}
```

**yt-dlp fallback** (`"source": "yt-dlp (trending page)"`):
```json
{"source": "yt-dlp (trending page)", "total_results": 10,
 "videos": [{"id": "abc123...", "title": "...", "url": "https://youtube.com/watch?v=abc123...",
   "duration": 120, "view_count": 1500000, "channel": "..."}]}
```

| Field provenance | API | yt-dlp |
|-----------------|-----|--------|
| channel_id, published_at, thumbnail | ✓ | — |
| duration, view_count | — | ✓ |

`_warning` may appear on yt-dlp when empty.

### youtube_get_channel_videos
```json
{"channel": "Programming with Mosh",
 "channel_url": "https://youtube.com/@programmingwithmosh", "total_videos": 10,
 "videos": [{"id": "abc123...", "title": "...", "url": "https://youtube.com/watch?v=abc123...",
   "duration": 3600, "view_count": 500000, "upload_date": "20240115"}]}
```
yt-dlp only. Channel name from first video's metadata. `_warning` on empty.

### youtube_get_playlist
```json
{"playlist_title": "Learn Python",
 "playlist_url": "https://youtube.com/playlist?list=PL...", "total_videos": 20,
 "videos": [{"id": "abc123...", "title": "...", "url": "https://youtube.com/watch?v=abc123...",
   "duration": 1200, "channel": "..."}]}
```
yt-dlp only (`--flat-playlist`). `_warning` on empty.

### youtube_get_transcript
```json
{"video_id": "jNQXAC9IVRw", "language": "en", "is_generated": false,
 "segment_count": 6, "with_timestamps": false,
 "text": "All right, so here we are, in front of the elephants..."}
```
With `with_timestamps: true`, `text` becomes:
```
[00:01] All right, so here we are, in front of the elephants
[00:05] the cool thing about these guys is that they have really...
```
No `cached` flag on public envelope. Persistent cache used internally (`_get_transcript_cached` at tools.py 263–272), but `cache.get_transcript()`'s `"cached": true` (cache.py 34) is discarded before output. Manual > ASR priority.

Source: `tube_bridge/tools.py` 264–304, `tube_bridge/cache.py` 27–35.

### youtube_get_available_languages
```json
{"video_id": "jNQXAC9IVRw", "total_languages": 5,
 "languages": [{"language": "English", "language_code": "en", "is_generated": false},
   {"language": "English (auto-generated)", "language_code": "en", "is_generated": true}]}
```
`is_generated: true` = ASR; `false` = manual.

### youtube_get_comments
```json
{"video_id": "jNQXAC9IVRw", "total_comments": 3,
 "comments": [{"author": "User123", "text": "Great video!", "likes": 42,
   "published_at": "2024-01-15T12:00:00Z", "reply_count": 2}]}
```
API-only. Top-level, relevance-ordered. Max 100/call.

### youtube_get_channel_info
```json
{"channel_id": "UC...", "title": "Programming with Mosh", "description": "Learn to code...",
 "custom_url": "@programmingwithmosh", "published_at": "2014-01-01T...", "country": "US",
 "thumbnail": "https://yt3.ggpht.com/...", "subscriber_count": 4000000,
 "video_count": 200, "view_count": 200000000,
 "keywords": "python, javascript, coding"}
```
API-only. Requires channel ID (`UC...`).

### youtube_search_channels
```json
{"query": "programming", "source": "YouTube Data API v3", "total_results": 5,
 "channels": [{"channel_id": "UC...", "title": "Programming with Mosh",
   "description": "Learn to code...", "published_at": "...",
   "thumbnail": "https://yt3.ggpht.com/...", "subscriber_count": 4000000,
   "video_count": 200, "view_count": 200000000, "country": "US"}]}
```
API-only. Subscriber enrichment via separate `channels.list` call. Client-side `min_subscribers`/`max_subscribers` filtering.

### tube_bridge_help

Returns `HELP_TEXT`, derived from the same 16-entry `TOOL_CATALOG` used by MCP registration (10 YouTube interaction + 5 corpus + 1 help). Dispatch is separate and frozen tests enforce the same 16-name set. The response includes an authoritative numeric count and complete tool metadata without duplicate keys.

Source authority: `TOOL_CATALOG`, `HELP_TEXT`, `list_tools()` and `_handle_tool()` in `tube_bridge/server.py`.

### corpus_create
```json
{"corpus_id": "iran-hormuz-2026", "status": "created",
 "embedding_model": "BAAI/bge-small-en-v1.5"}
```
Status: `"created"` or `"already_exists"`. ID validated against `^[A-Za-z0-9_-]{1,128}$`.

### corpus_add
```json
{"corpus_id": "iran-hormuz-2026", "video_id": "dQw4w9WgXcQ",
 "status": "indexed", "chunks": 5}
```
Status: `"indexed"`, `"already_indexed"`, or `"no_content"`. Idempotent via `corpus_added_videos`. Transcript fetched over network (cache-aware), chunked, embedded locally.

### corpus_search
```json
{"corpus_id": "iran-hormuz-2026", "query": "memory systems", "total_results": 3,
 "chunks": [{"video_id": "dQw4w9WgXcQ", "start_ts": 120.5, "end_ts": 200.0,
   "text": "The memory system in this architecture...", "score": 0.8734}]}
```
`score = round(1.0 - distance, 4)` without clamping (`corpus.py` 237). sqlite-vec cosine distance can exceed 1.0, producing negative scores; consumers must not assume [0,1]. Sorted by ascending distance.

### corpus_list
```json
{"corpora": [{"corpus_id": "iran-hormuz-2026", "label": "Iran Hormuz 2026",
   "embedding_model": "BAAI/bge-small-en-v1.5", "created_at": 1754611200.0,
   "chunk_count": 120, "video_count": 15}], "total": 1}
```
Ordered by `created_at` descending.

### corpus_delete
```json
{"corpus_id": "iran-hormuz-2026", "status": "deleted"}
```
Deletes per-corpus vector table, all chunks, added-video records, and the corpus row.

---

## Storage Schema

### cache.db
WAL mode. `$TUBE_BRIDGE_CACHE/cache.db` (default `~/.tube_bridge/cache.db`).

| Table | Columns | Notes |
|-------|---------|-------|
| transcripts | video_id TEXT, lang TEXT, segments TEXT (JSON), language TEXT, is_generated INTEGER, cached_at REAL | PK: (video_id, lang) |
| video_info | video_id TEXT PK, data TEXT (JSON), cached_at REAL | `cached`,`source`,`_ytdlp_stderr` stripped before storage (cache.py 59–61) |

### corpus.db
WAL mode. `$TUBE_BRIDGE_CACHE/corpus.db`.

| Table | Columns | Notes |
|-------|---------|-------|
| corpora | corpus_id TEXT PK, label TEXT, embedding_model TEXT, created_at REAL, expires_at REAL nullable | ID validated: `^[A-Za-z0-9_-]{1,128}$`; demo stores `created_at + 600`, self-hosted stores NULL |
| corpus_chunks | id INTEGER PK, corpus_id TEXT, video_id TEXT, start_ts REAL, end_ts REAL, text TEXT, added_at REAL | UNIQUE(corpus_id, video_id, start_ts) |
| corpus_added_videos | corpus_id TEXT, video_id TEXT, added_at REAL | Composite PK |
| vec_{corpus_id} | VIRTUAL (sqlite-vec: `vec0(embedding float[dim])`) | Joined via rowid=id. Dim=384 (BGE-small) |

ID validation protects SQL identifiers; dashes replaced with underscores for table names.

---

## Transcript Segment / Chunk Fields

**Segment** (youtube-transcript-api → cache.db segments JSON):
```json
{"text": "All right, so here we are", "start": 1.0, "duration": 4.0}
```

**Chunk** (`_chunk_transcript()` → corpus_chunks):
```json
{"start_ts": 1.0, "end_ts": 85.0, "text": "All right, so here we are ..."}
```
80s windows, 20s overlap. Respects segment boundaries; large caption gaps force new windows. Guarantees forward progress.

---

## Embedding-Model Invariant

- Each corpus records its model at creation. Add/search validate match; mismatch → `RuntimeError` + recreate instructions.
- Default: `BAAI/bge-small-en-v1.5` (configurable via `TUBE_BRIDGE_EMBEDDING_MODEL`).
- Inference local via `fastembed`; initial model acquisition may require network. No external embedding service/API key.

---

## Corpus ID Validation

Regex: `^[A-Za-z0-9_-]{1,128}$`. Rejected IDs raise `ValueError`. Protects SQL identifiers in per-corpus vector table names.

---

## Boundary: cache.db vs corpus.db

- Separate files in `$TUBE_BRIDGE_CACHE`. Distinct schemas/lifecycles.
- cache.db: transient cache (safe to delete/regenerate).
- corpus.db in self-hosted mode: user-managed; deletion is permanent and user-initiated.
- corpus.db in explicit demo mode: each corpus has a persisted 600-second deadline; relational rows and its `vec_{id}` table are transactionally deleted by the worker/lazy defense. No raw client identity or allowance bucket is stored in either database.
- Both use WAL journal mode. Railway attaches no persistent volume, so a process/deployment replacement may remove demo data earlier.

---

## Network Boundaries

- YouTube tools: require connectivity to TimedText, InnerTube, or Data API v3.
- `corpus_create`: may need network on first call for model assets; inference local thereafter.
- `corpus_add`: fetches transcript over network + may need network for model assets.
- `corpus_search`: may need network on first call for model assets; inference/search local.
- `corpus_list`, `corpus_delete`: purely local (corpus.db only).
- No external database, vector store, or embedding API required.

---

## Schema Stability

- Field additions may occur without ADR.
- Field removal or semantic changes (type, meaning, nullability) require an ADR.
- Consumers should tolerate unknown fields (forward-compatible parsing).
