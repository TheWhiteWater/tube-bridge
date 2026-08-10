# Corpus v1 Ranking Convergence Audit

**Date:** 2026-08-10

**WorkItem:** `WI-CORPUS-RANKING-20260810`

**Status:** Source candidate verified and independently audited; public v1.1.0 remains unchanged and a patch release is not authorized by this work block.

## Accepted Scope

- Suppress positively overlapping same-video result windows.
- Bound dense candidate over-fetch and limit source domination with deterministic refill.
- Preserve single-video top-k and stable tie ordering.
- Return nullable cached title, canonical video URL and timestamp URL.
- Validate `top_k` from 1 through 50 without adding tool arguments or tool names.
- Add nullable title to old databases.
- Remove replaced vector rows during `force_reembed` without touching other videos.
- Replace collision-prone dash/underscore vector table names and transactionally split legacy shared tables.

Excluded: multilingual retrieval, embedding changes, Corpus v2 runtime/cutover, publication, and Railway changes.

## Frozen Contract Chain

| Contract | SHA-256 | State |
|---|---|---|
| Primary ranking contract | `d831c0ed077ea0ee12bfe934a09c9b014b11ca6884b99fe6999f73d856d1a031` | Final Station freeze `.brainops/methodology/frozen-tests/frozen-20260810171509-test_corpus_search_ranking.py.json` |
| P1 remediation addendum | `15d1520fbf42bd97345a58f6e4368c16415a8598a8ae2dbc0141d93be86bda0e` | Station freeze `.brainops/methodology/frozen-tests/frozen-20260810171053-test_corpus_search_ranking_addendum.py.json` |

Earlier primary manifests are preserved. Two test-data corrections are bounded in `.hermes/plans/2026-08-10-corpus-ranking-frozen-test-correction.md`: contradictory interval fixtures and one private legacy table-name literal. Independent correction audits returned PASS with P0=0/P1=0 before each replacement freeze.

## Verification

- Focused contracts: **23/23 PASS**.
- Full deterministic suite: **211/211 PASS**.
- Station verification: `.brainops/methodology/verification/verification-1786383021743.json`, status PASS, 197 bounded tests.
- `node scripts/station-verify.mjs`: PASS.
- Wheel/sdist build and `twine check`: PASS.
- Compile and `git diff --check`: PASS.
- Exact runtime hashes:
  - `tube_bridge/corpus.py`: `e749e1ffe731108998899345b84cdcefea07f066458a385f63eebf2798d0ed84`
  - `tube_bridge/tools.py`: `24a7d6fcedbff172dea45535e135849a045495fd90574393388ab926e7614d86`
  - `tube_bridge/server.py`: `8da67c9c544b08a9b18fc320d522ec48ab02255f1989a03b360d22bbcb2f2b26`

## Live Evidence

The same four-video corpus was rebuilt locally: four videos, 64 chunks. Both evaluation queries returned all four sources, no same-video overlaps, titles and timestamp URLs. The long source was capped at four of eight results. A database produced by the legacy table mapping migrated to a 64-row hash-named table and removed the old table.

Sanitized receipt: `docs/research/evidence/2026-08-10-corpus-v1-ranking-live.json`, SHA-256 `319f60489b79f290fbe2c312e1ecafc2bceb4169fefdb760bafd851dc074be56`.

## Independent Audits

- Initial source audit: FAIL, P0=0/P1=3. It found force-reembed orphan vectors, dash/underscore table collision, and saturated KNN tie nondeterminism.
- Addendum contract audits: final PASS, P0=0/P1=0.
- Final source convergence audit after remediation: **PASS, P0=0/P1=0**.
- Product docs pack (`PROJECT_VISION.md`, `README.md`, `AGENTS.md`): PASS, P0=0/P1=0.
- Constitution pack (`02_ARCHITECTURE.md`, `03_DATA_MODEL.md`, `04_GLOSSARY.md`): PASS, P0=0/P1=0.
- Research/skill pack, after adding release qualifiers and reproducibility receipt: PASS, P0=0/P1=0.

## Station Conformance State

The first Station conformance call returned **INCONCLUSIVE**, not PASS, because it ran before a durable implementation commit/hosted-CI receipt and before WorkItem evidence refs were attached. That receipt is preserved at `.brainops/methodology/audits/2026-08-10T17-32-29-330Z-d3d987a8-codex/station-codex-audit.json`. It must not be represented as acceptance. Final Station conformance is rerun only after commit, PR CI and WorkItem evidence attachment.
