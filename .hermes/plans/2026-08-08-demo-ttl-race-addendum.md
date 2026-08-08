# WI-00029 Addendum — TTL Deadline Races and Worker Recovery

**Trigger:** independent source audit FAIL at `.brainops/methodology/audits/2026-08-08T13-42-21-394Z-f782a2f5-codex/station-codex-audit.json`.

## Scope

Add one new frozen test file without modifying the existing WI-00029 or WI-00028 frozen tests. Fix only three audit-discovered defects:

1. `corpus_add` must abort, remove the expired corpus, and leave no chunks/vectors if the persisted deadline passes after its write lock/check but before commit.
2. `corpus_search` must not return results if embedding crosses the persisted deadline; it must purge the expired corpus and return the existing not-found contract.
3. `DemoTTLWorker` must survive and retry after transient exceptions from both nearest-deadline lookup and expiry deletion.

## Deterministic RED strategy

- Use a fake wall clock that crosses the deadline between checks; no 10-minute sleep.
- Seed real isolated SQLite/sqlite-vec data and prove no expired/orphan rows remain.
- Inject one-shot `sqlite3.OperationalError` into worker lookup and purge callbacks; require a later successful purge event.
- No production/test-file edits outside the new addendum test until independent test-contract PASS and a separate SHA-256 freeze manifest.

## Non-goals

No quota, proxy, transport, packaging, docs, Railway, public API, or self-host behavior changes. Existing 184 green tests and both prior frozen manifests must remain byte-identical.
