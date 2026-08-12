# Source capture

Capture the intended subtitle track before analysis or corpus indexing. Track selection is part of evidence provenance.

## Required sequence

1. Inspect the video with `youtube_get_video_info`.
2. Enumerate subtitle tracks with `youtube_get_available_languages`.
3. Determine the intended language from the research brief, video metadata, and available tracks.
4. Pass that language code explicitly to `youtube_get_transcript`.
5. Request `with_timestamps=true` for evidentiary use.
6. Verify the response `language` and `is_generated` fields against the selected track.
7. Record video identity, retrieval time, requested and selected languages, track type, warnings, and material time spans.

## Default selector behavior

In v1.1.0, `lang=None` uses the provider's first generated track to identify the default language family, then tries exact-code manual, same-family regional manual, and generated tracks in that family. It never falls through to an unrelated foreign manual dub. If no generated track exists, only the provider's first manual track is treated as the default.

This deterministic fallback is not a substitute for research provenance:

- pass `lang` explicitly whenever a suitable code is available;
- reject or recapture a response whose returned language differs from the intended track;
- record when default selection was used;
- do not add an ambiguously interpreted transcript to a research corpus.

Manual subtitles are generally preferable to generated ASR only within the intended language. “Manual” alone does not make a foreign dub the correct source.

## Evidence record

For each material span, retain:

- video URL or `video_id`
- title and channel when available
- requested language and returned language
- manual or generated status
- start and end timestamp
- short quotation or faithful observation
- retrieval warning or quality limitation
- verification status and notes

Use the evidence-ledger template for a consistent record.

## Quality cautions

- ASR can corrupt names, numbers, punctuation, and speaker changes.
- Subtitle text may omit material visible or audible in the video.
- Do not infer speaker identity unless the source establishes it.
- Verify high-impact details with another source or direct media inspection where available.
- `youtube_get_frame` observes one bounded visual frame only. It does not inspect audio, identify a speaker, prove off-screen context, or convert transcript evidence into authenticated verbatim speech.

## Copyright-aware handling

Retain the complete transcript only where the operator's research and storage policy permits it. In reports, quote only the evidence needed and prefer timestamped links plus analysis over reproducing long passages.

After capture, classify the material using [methodology/01-evidence-protocol.md](methodology/01-evidence-protocol.md). A transcript directly proves only what the selected subtitle track renders at a time span. Exact speech, speaker endorsement, and the underlying world claim require the additional verification defined by the research brief.
