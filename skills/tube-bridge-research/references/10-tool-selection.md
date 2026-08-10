# Tool selection

Choose the smallest tool sequence that can answer the research question.

## Discovery

- `youtube_search`: general video search; Data API when configured, otherwise yt-dlp fallback.
- `youtube_search_channels`: channel discovery with subscriber filters; Data API required.
- `youtube_get_trending`: current trending candidates.
- `youtube_get_channel_videos`: recent uploads from a channel URL or handle.
- `youtube_get_playlist`: enumerate a selected playlist.

## Source inspection

- `youtube_get_video_info`: title, duration, channel, description, tags, and other metadata.
- `youtube_get_channel_info`: detailed channel metadata; Data API required.
- `youtube_get_comments`: audience comments; Data API required. Comments are reactions, not verification of video claims.

## Transcript evidence

1. `youtube_get_available_languages`
2. `youtube_get_transcript` with explicit `lang`
3. Set `with_timestamps=true` when evidence will support a claim

When `lang` is omitted, the runtime stays in the inferred original/default language cohort. Use explicit `lang` when the research contract requires a particular wording lineage.

## Visual evidence

- `youtube_get_frame`: extract one ephemeral JPEG at integer `timestamp_ms`; returns metadata and MCP `ImageContent`.
- Use a transcript span to choose the timestamp, then inspect the frame as visual evidence. A frame does not verify audio wording, off-screen events, authorship, or wider context.
- Public bounds: one image, width 64–1280, raw JPEG ≤1.5 MB, base64 image data ≤2 MB, no persistence or batch.

## Local corpus operations

- `corpus_create`: create a named local corpus with one embedding model.
- `corpus_add`: fetch, chunk, and embed a selected video transcript; idempotent unless forced.
- `corpus_search`: return flat semantic candidates with video IDs, time spans, text, and scores.
- `corpus_list`: inspect available local corpora and counts.
- `corpus_delete`: permanently delete one corpus and its vectors; confirm the target before calling it.

Use `tube_bridge_help` for the live catalog, architecture summary, known limitations, and key requirements.

## Common routes

### One-video analysis

`youtube_get_video_info` → `youtube_get_available_languages` → timestamped `youtube_get_transcript` → optional `youtube_get_frame` at a material timestamp

Read the full transcript when it fits the available context. Do not create a corpus solely because a corpus tool exists.

### Multi-video investigation

`youtube_search` → inspect candidates → capture track provenance → `corpus_create` → `corpus_add` selected videos → `corpus_search` → verify source spans

### Channel study

`youtube_search_channels` or known channel → `youtube_get_channel_info` → `youtube_get_channel_videos` → inspect selected videos → capture transcripts

## Operational boundaries

- Search, transcript retrieval, channel uploads, playlists, trending, and local corpus tools have keyless paths.
- Channel search, channel details, and comments require a YouTube Data API key.
- Search and selected metadata tools improve when a key is configured but retain fallbacks.
- Preserve source and warning fields. Do not represent yt-dlp fallback output as Data API output.
- YouTube controls subtitle availability and can rate-limit or block operator IP addresses.
