# Corpus Ranking Frozen-Test Correction

**WorkItem:** `WI-CORPUS-RANKING-20260810`

**Original frozen artifact:** `.brainops/methodology/frozen-tests/frozen-20260810162653-test_corpus_search_ranking.py.json`

**Original SHA-256:** `c91583277462408bf90232569fc1dd40dc376afb55b29c1bbb205c450c9229d8`

## Why correction is required

The first GREEN attempt exposed two contradictions inside the test data. Production code was not accepted and was restored to the pre-implementation tree before correcting tests.

1. `test_reverse_ranked_touching_and_disjoint_windows_are_preserved` described the third interval as disjoint but encoded `20–30` after selecting `0–100`; those intervals overlap and the frozen policy requires suppression.
2. `test_equal_scores_have_stable_order_independent_of_insertion` expected both `video-a` intervals beginning at 10 and 30 even though `_candidate()` made each 80 seconds, so the intervals `10–90` and `30–110` overlap and one must be suppressed.

## Authorized byte-only correction

- Move the third reverse-boundary interval from `20–30` to `120–130`, disjoint from both `0–100` and `100–110`.
- Move the second equal-score `video-a` interval from start 30 to start 100, making `10–90` and `100–180` non-overlapping.
- Change only the corresponding expected timestamps.

No accepted ranking formula, overlap rule, tool schema, migration behavior, title behavior, source file, public API, or non-goal changes. Re-run RED, obtain an independent P0/P1 audit, and create a new Station-owned frozen manifest before restoring implementation work.

## Second correction after collision-remediation addendum

**Previously corrected SHA-256:** `d71526a9c96edf7229f846aa987044e1cee46416eed1ed177f4032651e7e17de`

The later independently audited addendum requires collision-free vector table names because valid IDs `a-b` and `a_b` previously shared `vec_a_b`. One rollback assertion in the primary frozen test still queried the private legacy literal `vec_force_failure`, which is incompatible with any collision-free mapping even though the rollback behavior is correct.

Authorized correction: replace only that literal SQL table name with `ranking_corpus._vec_table("force-failure")`. The expected vector count, rollback semantics, corpus ID, and all public behavior remain unchanged. Audit the byte delta and create a new Station-owned frozen manifest; do not preserve a legacy alias that would reintroduce collisions.
