# Corpus evaluation plan

## Decision

- Representation or retrieval method under evaluation:
- Decision this benchmark will make:
- Acceptance thresholds fixed before the run:
- Stop and rollback conditions:

## Frozen source set

| Video ID | Requested → selected language | Track type | Source hash | Duration | Coverage role | Known limitations |
|---|---|---|---|---:|---|---|
|  |  |  |  |  |  |  |

## Compared baselines

| Baseline ID | Representation | Retrieval method | Model/version | Configuration |
|---|---|---|---|---|
| B-01 | Fixed 80/20 windows | Dense vector |  |  |

## Frozen query set

| Query ID | Class | Question | Required evidence spans | Acceptable alternatives | Expected absence contract | Unanswerable? |
|---|---|---|---|---|---|---|
| Q-001 | exact / semantic / temporal / multi-hop / cross-video / global |  |  |  |  | no |

## Metrics

- Evidence Recall@k:
- MRR or NDCG:
- Timestamp overlap and ordering:
- Duplicate-window rate:
- Multi-hop evidence completeness:
- Source-span traceability:
- False confidence on unanswerable queries:
- Negative-evidence false-positive rate:
- Indexing time, model calls, and failures:
- Query latency and loaded context:
- Storage and embedding footprint:

## Run record

| Run ID | Baseline | Runtime/schema/processor versions | Query-set version | Result artifact | Failures |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

## Error analysis

- Missed exact terms:
- Missed paraphrases:
- Wrong language or ASR effects:
- Temporal ordering errors:
- Shared-origin or duplicate results:
- Cases where “not found” was wrongly treated as absence:

## Verdict

- Thresholds met:
- Regressions:
- Cost and latency trade-offs:
- Traceability assessment:
- Decision:
- Required follow-up:
