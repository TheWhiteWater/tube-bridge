# Retrieval

Select retrieval strategy from task shape and evidence scale.

## Direct transcript reading

Use direct timestamped transcript analysis when one or a few selected videos fit the available context. This preserves chronology and avoids unnecessary retrieval loss.

Best for:

- explaining one argument end to end
- chronological questions
- finding what came before or after a known anchor
- close reading of a short or medium video

## Current corpus search

`corpus_search` performs dense retrieval over flat overlapping windows. Use it to locate candidate spans across indexed videos.

Best for:

- semantic paraphrases
- discovering which videos discuss a concept
- reducing a large corpus to a reviewable candidate set

Limitations:

- no lexical search for exact names, numbers, or quotations
- no chapter or parent-child navigation
- no explicit previous or next links
- no logical or cross-video relation graph
- overlap can return near-duplicate hits
- score is relative ranking evidence, not calibrated confidence

After a hit, identify its video and time span and inspect the timestamped source transcript around that location.

## Corpus v2 retrieval direction

Evaluate a hybrid route rather than assuming either vector retrieval or structure-only navigation is sufficient:

1. lexical retrieval for exact terms, quotations, names, and numbers;
2. dense retrieval for paraphrases and semantic similarity;
3. temporal traversal for before, after, and development-over-time questions;
4. hierarchy for summaries and parent-child context;
5. optional typed relations for support, example, contrast, contradiction, and cross-video concepts;
6. reranking and source-span expansion before answer generation.

Pure vector search, pure tree navigation, and full-transcript loading are comparison baselines. The winning route may vary by query class.

## Evidence assembly

- Retrieve more than one candidate for consequential claims.
- Preserve source ordering when combining spans from one video.
- Label cross-video synthesis separately from statements made by an individual source.
- Include disagreement and missing evidence rather than forcing consensus.
- Never cite a generated summary when a source transcript span is available.
- Never treat an absent top-k result as proof of absence without the observation contract in [methodology/01-evidence-protocol.md](methodology/01-evidence-protocol.md); see [examples/03-absence-is-not-negative-evidence.md](examples/03-absence-is-not-negative-evidence.md).
