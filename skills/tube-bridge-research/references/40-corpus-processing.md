# Corpus processing

**Status:** design guidance for Corpus v2 evaluation, not released runtime behavior.

Process subtitles as an ordered time series rather than an unordered bag of passages.

## Candidate pipeline

1. Select the intended subtitle track deterministically.
2. Persist the complete timestamped source transcript.
3. Normalize into a separate derived field while preserving original text.
4. Form non-overlapping addressable units from complete utterances or sentences with a model-specific token ceiling.
5. Detect contiguous topic boundaries using available chapters, description timestamps, pauses, discourse markers, and adjacent semantic change.
6. Build a hierarchy whose within-video nodes cover contiguous time ranges.
7. Generate summaries, keywords, discourse roles, or relations with explicit processor and model provenance.
8. Build independent lexical, dense, temporal, and optional relation indexes.
9. Evaluate exact, semantic, chronological, multi-hop, cross-video, and global queries.

## Structural rules

- Fixed-duration chunks can remain an embedding-compatibility baseline, but they are not logical structure.
- Prefer non-overlapping source units plus `PREVIOUS` and `NEXT` navigation over permanent overlap duplication when evaluating a new design.
- Within-video parent nodes must cover contiguous source spans and preserve chronology.
- Non-contiguous similarity belongs in a separate concept or cross-video relation layer.
- Generated summaries and relations are hypotheses about source content, never replacements for evidence.
- Each generated artifact must identify its processor, model or algorithm, configuration, source hash, and confidence where applicable.

## Adaptive loading

A selected short or medium transcript may be read in full when context permits. Larger corpora need compact summaries and addressable local units, but retrieval should still return to the underlying source span before conclusions are reported.

## Current baseline

The released `corpus.py` creates flat 80-second transcript windows with 20-second overlap, embeds them using the configured FastEmbed model, and searches with sqlite-vec. It has no normalization version, semantic boundary detector, outline, chapter hierarchy, neighbor links, or typed logical relations.

The persisted representation, provenance fields, and atomic rebuild envelope are frozen in [30-corpus-storage.md](30-corpus-storage.md). Do not replace the baseline until subtitle-track selection is corrected and frozen tests plus benchmark acceptance criteria establish the processing and retrieval algorithms inside that envelope.
