# Open Questions

Unresolved questions that need ADRs or investigation.

## Q1: yt-dlp rate-limiting risk
**Status:** Open  
**Owner:** W-1020  
**Context:** yt-dlp uses YouTube's InnerTube API without auth. Moderate use is fine, but heavy search traffic may trigger CAPTCHA or IP blocks.  
**Options:**
- A. Keep yt-dlp as primary, document rate-limit risk
- B. Add optional Data API v3 as primary for search, yt-dlp as fallback
- C. Both: primary=yt-dlp, optional upgrade to API key for guaranteed quota

## Q2: Comments — yt-dlp or Data API v3
**Status:** Needs ADR  
**Owner:** W-1020  
**Context:** Comments are the only feature where Data API v3 clearly beats yt-dlp. yt-dlp comment extraction is slow, fragile, and breaks on YouTube layout changes.  
**Leaning:** Data API v3 with optional `YOUTUBE_API_KEY`. Graceful fallback: if no key, tool returns "comments require API key" instead of error.

## Q3: One tool vs two for transcript
**Status:** Resolved — merged into one tool with `with_timestamps` param.  
**Resolution:** 2026-08-07.

## Q4: Trending accuracy
**Status:** Open  
**Context:** Trending uses YouTube's `results?search_query=trending&sp=...` page which is geo-dependent. Non-US IPs get regional trending.  
**Options:**
- A. Accept geo-dependency, document it
- B. Add optional `region` parameter with yt-dlp `--geo-bypass`
- C. Use Data API v3 for region-independent trending

## Q5: Deployment target
**Status:** Open  
**Context:** Currently local stdio only. Options: Railway (same as BrainOps stack), Fly.io, or keep local.  
**Consideration:** MCP servers typically run local; HTTP transport adds auth complexity.

## Q6: Channel search (not just video search)
**Status:** Backlog  
**Context:** `youtube_search` returns videos. Should we add `youtube_search_channels`?  
yt-dlp supports `ytsearchN:query` but doesn't distinguish channel results well.
