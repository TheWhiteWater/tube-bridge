# Evaluation

Choose corpus processing and retrieval methods through reproducible comparison on the same immutable source transcripts.

## Baselines

1. Current fixed 80-second windows with 20-second overlap.
2. Full-transcript or bounded direct reading where context permits.
3. Non-overlapping semantic units with lexical and dense retrieval.
4. Structure-only navigation over a generated outline.
5. Temporal hierarchy plus hybrid retrieval.
6. Temporal hierarchy plus optional logical and cross-video relations.

## Query classes

Include at least:

- exact quotation, name, or number
- semantic paraphrase
- what occurred before or after an anchor
- development of an argument within one video
- evidence combined from separated parts of one video
- comparison across videos
- global corpus theme or contradiction
- an unanswerable query that should expose missing evidence

## Ground truth

For every benchmark question, record admissible videos, required timestamp spans, acceptable alternative evidence, and why the evidence answers the question. Freeze this set before tuning the implementation being evaluated.

## Measurements

- evidence Recall@k and MRR or NDCG
- source timestamp overlap and ordering accuracy
- selected hierarchy-path accuracy where applicable
- multi-hop evidence completeness
- answer grounding and source traceability
- false confidence on unanswerable questions
- indexing time, model calls, and failures
- query latency and context tokens loaded
- storage and embedding footprint

Do not invent acceptance thresholds after seeing the results. Define them in the corpus-evaluation template before running the comparison.

## Run discipline

- Pin source transcript hashes and selected subtitle provenance.
- Record runtime, schema, processor, embedding, and model versions.
- Use the same query set across baselines.
- Separate retrieval quality from answer-generation quality.
- Keep failed and null results; do not score only successful queries.
- Publish enough evidence to reproduce the comparison without refetching mutable source content where policy permits.

## Decision rule

Prefer the simplest method that satisfies the predeclared evidence, latency, cost, and traceability criteria. Architectural novelty is not evidence of retrieval quality.
