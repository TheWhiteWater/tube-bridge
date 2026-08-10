# Corpus v1 Dogfood — Retrieval Architectures for Long Video Transcripts

**Date:** 2026-08-10

**Status:** Completed bounded exploratory run

**Corpus:** `rag-retrieval-architecture-2026-test`

**Runtime under test:** private in-session v1.0.3 MCP snapshot, 16 tools; corpus implementation is the same flat v1 `80s/20s-overlap` path retained by public v1.1.0
**Embedding model:** `BAAI/bge-small-en-v1.5`

## Frozen Research Frame

**Question:** What should replace or augment fixed-size chunk retrieval for long, timestamped YouTube transcripts: contextual retrieval, late chunking, GraphRAG, or reasoning-tree/vectorless navigation?

**Material rule:** use four technical videos with available English transcripts, including one detailed video-retrieval walkthrough and one source associated with each alternative architecture.

**Output rule:** produce timestamped mechanism and limitation evidence, test retrieval behavior, and recommend only bounded Corpus v2 experiments. Similarity scores, source count, and vendor agreement are not treated as proof.

**Non-goals:** no production Corpus v2 implementation, no Railway deployment/configuration change, no claim that the four videos form an independent benchmark, and no validation of papers or benchmark datasets outside the captured transcripts.

## Captured Sources

| Video | Role | Duration | Track | v1 chunks |
|---|---|---:|---|---:|
| [Pinecone + Anthropic — Build Contextual Retrieval](https://youtube.com/watch?v=u-ocR-2P_YA) | Detailed contextual/multimodal video pipeline | 53:45 | English ASR | 55 |
| [Weaviate — Late chunking improves context recall](https://youtube.com/watch?v=buzWGXOydD8) | Late-chunking mechanism and storage claim | 2:45 | English ASR | 3 |
| [IBM — GraphRAG vs Traditional RAG](https://youtube.com/watch?v=Aw7iQjKAX2k) | Graph extraction and relation retrieval | 4:17 | English manual preferred | 4 |
| [Vectify AI — Introducing PageIndex](https://youtube.com/watch?v=x6Is1kShF5Q) | First-party reasoning-tree description | 2:30 | English ASR | 2 |

Total: **4 videos / 64 chunks**. The Pinecone webinar accounts for **55/64 (86%)** of all indexed chunks.

## Timestamped Findings

### 1. Contextual retrieval enriches each derived chunk before indexing

Anthropic describes ordinary chunk isolation and appending LLM-generated, document-aware context before embedding at [13:59–16:22](https://youtube.com/watch?v=u-ocR-2P_YA&t=839s). The speaker reports up to a **67% reduction in incorrect chunk retrieval**, but this run did not capture the underlying evaluation dataset or reproduce the metric. Treat it as a reported first-party result, not an independently established effect.

Prompt caching is presented as the mechanism that makes repeated whole-document contextualization economical at [16:59–18:22](https://youtube.com/watch?v=u-ocR-2P_YA&t=1019s), with an estimate of roughly **$1 per million document tokens** for the then-current Claude 3.5 Sonnet workflow. This is model/provider/time-specific, not a general cost constant.

### 2. Late chunking preserves full-document token context before pooling chunks

Weaviate contrasts naive chunks, ColBERT-style late interaction, and late chunking at [00:00–02:46](https://youtube.com/watch?v=buzWGXOydD8). The described sequence is: encode the long document, split token embeddings after encoding, then pool chunk representations. The source reports **2.5 TB vs 5 GB** for one ColBERT comparison and claims late chunking retains naive-chunk storage. The benchmark was not reproduced here.

This technique is not directly compatible with the current 512-token `bge-small-en-v1.5` encoder for whole long-video transcripts; it requires a suitable long-context embedding model and a separate benchmark.

### 3. PageIndex uses a hierarchy as a navigation layer

Vectify describes generating a table-of-contents tree and having an agent navigate it step by step at [01:04–02:28](https://youtube.com/watch?v=x6Is1kShF5Q&t=65s). This supports the Corpus v2 idea of hierarchy for navigation and transparent trajectories.

However, the captured source is a 150-second product introduction. A probe asking for PageIndex failure cases, cost, and latency returned only benefits and competitor limitations. Therefore its comparative superiority is **INCONCLUSIVE** in this corpus.

### 4. GraphRAG adds extracted entities and relations over text chunks

IBM describes retaining text chunks while extracting entities and relations into a graph at [00:55–02:20](https://youtube.com/watch?v=Aw7iQjKAX2k&t=56s). Explainability, traceability, maintenance, and answer quality are claimed at [02:56–04:12](https://youtube.com/watch?v=Aw7iQjKAX2k&t=176s), but no numerical same-dataset comparison is supplied.

For transcript-first corpora this is a possible derived layer, not a replacement for immutable temporal source or baseline lexical/dense retrieval.

### 5. Video evidence must preserve visual/spoken divergence

The Pinecone walkthrough explicitly notes that slides can contain information the speaker is not saying at the same moment at [03:59–07:20](https://youtube.com/watch?v=u-ocR-2P_YA&t=239s). Its demo samples frames every 45 seconds, aligns words by timestamp, and combines frame, local transcript, and whole-video summary at [18:59–21:23](https://youtube.com/watch?v=u-ocR-2P_YA&t=1139s). Contextual text is indexed while image paths remain metadata and images are loaded for final multimodal answering at [27:56–29:18](https://youtube.com/watch?v=u-ocR-2P_YA&t=1676s) and [45:18–46:38](https://youtube.com/watch?v=u-ocR-2P_YA&t=2718s).

This supports a separate timestamped visual-evidence contract. It does not justify fixed 45-second sampling as a universal policy, nor does the current ephemeral `youtube_get_frame` constitute persisted visual indexing.

## Retrieval Dogfood Results

| Probe | Result |
|---|---|
| Preserve document-level context | Correctly surfaced contextual retrieval, late chunking, and PageIndex mechanisms with timestamps. |
| Numerical evaluation | Found the 67%, $1/million tokens, 90% prompt-input, 80% time-to-first-token, and 500x storage claims, but mixed prompt-caching and retrieval metrics. Requires claim-level filtering. |
| Costs and limitations | Found useful contextual/ColBERT trade-offs; failed to recover meaningful PageIndex limitations because none were stated in its captured source. |
| Video transcript + slide retrieval | Strongly recovered frame/transcript/whole-video-summary architecture and visual/spoken mismatch. |
| Same-dataset head-to-head winner | **INCONCLUSIVE**. The corpus has no controlled comparison across all four methods. Semantic retrieval still returned nearby promotional numbers. |
| Evidence against “vector DBs are obsolete” | Recovered three architectures that continue to use chunking/vectors and GraphRAG that builds on chunks; useful contradiction to the absolute claim. |
| Russian semantic query | Poor. Top score was `0.1014` and results missed the direct pronoun/entity late-chunking passage; the analogous English probe reached `0.3926` and retrieved it first-page. |

Scores are embedding similarities, not confidence or evidentiary weight.

## Corpus v1 Product Findings

1. **Source-length domination:** one long webinar contributes 86% of chunks and dominates top-k results.
2. **Duplicate evidence:** 80-second windows with 20-second overlap return adjacent passages repeating the same claim.
3. **No source-aware diversification:** top-k can be filled by one video even when the query asks to compare methods.
4. **English-only retrieval weakness:** Russian queries against `bge-small-en-v1.5` are unreliable.
5. **No claim/gate semantics:** retrieval cannot distinguish a vendor assertion, a benchmark result, a question from the audience, or independent evidence.
6. **Flat context:** results expose timestamped windows but no chapter/topic path or source-segment lineage beyond video/time.
7. **Positive-result bias:** a request for missing limitations still returns semantically nearby benefit claims instead of an explicit `no evidence found` result.

## Bounded Corpus v1 Remediation Validation

A follow-up source branch implemented only the first ranking-layer fixes; it did not change embeddings, chunk generation, Corpus v2, tool names, or Railway. The same four videos were rebuilt locally into **64 chunks** and queried through the real embedding/runtime path.

- Context-preservation query, `top_k=8`: Pinecone 4, Weaviate 1, PageIndex 1, IBM 2. All four videos were represented; no returned same-video intervals overlapped.
- Controlled-comparison query, `top_k=8`: Pinecone 4, Weaviate 2, PageIndex 1, IBM 1. Before remediation this probe returned only Pinecone and Weaviate passages.
- Every hit included its cached title, canonical video URL and inspectable integer-second timestamp URL.
- The long Pinecone source remained capped at `ceil(8 / 2) = 4`, while deterministic refill still returned eight results.
- Full deterministic suite after independent P1 remediation: **211/211 PASS**.
- Repeated `force_reembed` now removes only replaced vector rows; legacy dash/underscore table collisions are split transactionally into hash-named tables; saturated equal-distance boundaries receive stable tie resolution.

This validates bounded overlap deduplication, source-aware first-pass caps, refill, result links, vector lifecycle and legacy collision migration. It does not establish semantic superiority, remove the need for source-quality review, or implement Corpus v2. The changes are source-tree work until separately reviewed/merged/released.

### Reproduction receipt

The sanitized receipt [`evidence/2026-08-10-corpus-v1-ranking-live.json`](evidence/2026-08-10-corpus-v1-ranking-live.json) records:

- both exact English query strings and `top_k=8`;
- before/after source distributions and every returned title, span, score and timestamp URL;
- the four video IDs, 64-chunk count and embedding model;
- base commit plus exact SHA-256 hashes for the three runtime source files and both frozen test files;
- the full-suite, build and twine commands/results;
- successful 64-vector legacy-table migration;
- explicit `secrets_included=false` and `railway_modified=false`.

Receipt SHA-256: `319f60489b79f290fbe2c312e1ecafc2bceb4169fefdb760bafd851dc074be56`.

## Bounded Recommendation for Corpus v2

1. Keep the immutable timestamped transcript as canonical source.
2. Build versioned `video → chapter → topic → passage` projection for navigation; do not replace lexical/dense retrieval with hierarchy.
3. Add source-aware result diversification, overlap deduplication, and per-video caps before evaluating more complex retrieval.
4. Benchmark optional contextual passage descriptions as a derived processor; never overwrite source text.
5. Benchmark late chunking only with a declared long-context encoder against fixed `80/20` and semantic-boundary baselines.
6. Treat GraphRAG as a later rebuildable entity/relation projection, justified only by relation-heavy tasks.
7. Evaluate tree navigation as an additional route with explicit cost/latency/failure measurements, not as “vectorless wins.”
8. Add multilingual embeddings or explicit query translation before advertising multilingual corpus search.
9. Define persisted visual evidence separately with exact transcript/frame provenance, deduplication, retention, and sampling policy.
10. Make retrieval able to return `INCONCLUSIVE` when required evidence classes or comparisons are absent.

## Reproducibility and Retention

The corpus remains available under `rag-retrieval-architecture-2026-test` in the Operator's private runtime until explicitly deleted. Repeated indexing is idempotent. No public service, deployment, or repository credential was created or changed during this run.
