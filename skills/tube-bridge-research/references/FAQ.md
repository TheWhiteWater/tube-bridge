# FAQ

## Why does the plugin install but the MCP fail to start?

Agent Plugins v1 does not define dependency installation. Confirm Python 3.12+ and the dependencies declared by the adjacent `pyproject.toml` or hash-locked `requirements-release.txt` are available in the process environment.

## Is a YouTube Data API key mandatory?

No. Search, video metadata, trending, transcripts, channel uploads, playlists, and corpus operations have keyless paths, though fallback quality and availability vary. Channel search, detailed channel metadata, and comments require the Data API. The live `tube_bridge_help` result is authoritative for tool requirements.

## How does omitted-language transcript selection work?

In v1.1.0 the default selector stays in the first ASR/default language family and cannot be captured by an unrelated foreign manual track. For evidence work, still call `youtube_get_available_languages`, pass the intended language explicitly when known, and verify the returned language before use.

## What if no transcript is available?

The uploader may have disabled subtitles, the video may be restricted, or YouTube may block the operator IP. Record the failure and choose another admissible source. Do not fabricate a transcript or silently substitute comments.

## Why is the first `corpus_add` slow?

The local embedding model may need to download and initialize. Corpus creation also fetches, chunks, embeds, and persists transcript data.

## Where is local data stored?

With the portable MCP config, cache and corpus databases are placed under `${PLUGIN_DATA}/cache`. The operator controls filesystem access, backup, and retention.

## Does the corpus retain a canonical raw transcript separately?

The cache retains fetched segments, while the current corpus database stores flat chunks and vectors. The Corpus v2 persisted format is now frozen as `corpus-v2.db` with immutable source versions, temporal projections, and rebuildable lexical/dense indexes, but it is not current runtime behavior.

## Are corpus similarity scores confidence probabilities?

No. Scores support ranking within a retrieval run. Verify selected hits against timestamped transcript evidence.

## Does tube-bridge understand chapters or argument structure?

Not in the released corpus runtime. Hierarchy, topic nodes, discourse roles, and logical relations remain design and benchmark work.

## Can the plugin inspect video frames?

The v1.1.0 `youtube_get_frame` tool returns one bounded ephemeral JPEG as MCP `ImageContent`. It does not inspect audio, retain the clip/image, or prove what happened outside that frame.

## Is deleting a corpus reversible?

No. `corpus_delete` permanently removes the corpus rows, chunks, and vector table. Confirm the corpus identifier before calling it.

## Should every investigation create a corpus?

No. For a small number of selected videos, direct timestamped transcript reading is often clearer and more complete. Use a corpus when repeated or large-scale retrieval justifies indexing.
