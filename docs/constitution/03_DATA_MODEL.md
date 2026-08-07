# 03 — Data Model

## VideoInfo (internal)

```python
@dataclass
class VideoInfo:
    id: str              # YouTube video ID (11 chars)
    title: str           # Video title
    url: str             # Full watch URL
    duration: int | None # Seconds
    view_count: int | None
    channel: str | None  # Channel name
    channel_url: str | None
    upload_date: str | None  # YYYYMMDD
    description: str | None  # Truncated to 500 chars
    thumbnail: str | None
    categories: list[str] | None
    tags: list[str] | None   # Max 20
```

## Search Result (external, per tool)

```json
{
  "query": "python tutorial",
  "total_results": 10,
  "videos": [
    {
      "id": "kqtD5dpn9C8",
      "title": "Python for Beginners",
      "url": "https://youtube.com/watch?v=kqtD5dpn9C8",
      "duration": 3662,
      "view_count": 24903766,
      "channel": "Programming with Mosh",
      "channel_url": "https://youtube.com/@programmingwithmosh",
      "upload_date": "20190218"
    }
  ]
}
```

## Transcript Result

```json
{
  "video_id": "jNQXAC9IVRw",
  "language": "en",
  "is_generated": false,
  "segment_count": 6,
  "with_timestamps": false,
  "text": "All right, so here we are, in front of the elephants..."
}
```

With `with_timestamps: true`, `text` becomes:
```
[00:01] All right, so here we are, in front of the elephants
[00:05] the cool thing about these guys is that they have really...
```

## Video Info (full)

```json
{
  "id": "jNQXAC9IVRw",
  "title": "Me at the zoo",
  "url": "https://youtube.com/watch?v=jNQXAC9IVRw",
  "duration": 19,
  "view_count": 403439184,
  "channel": "jawed",
  "description": "The first ever YouTube video...",
  "categories": ["Pets & Animals"],
  "tags": ["elephant", "zoo"]
}
```
