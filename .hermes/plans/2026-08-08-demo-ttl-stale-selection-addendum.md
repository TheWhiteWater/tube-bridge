# WI-00029 Addendum — Atomic Expiry Selection

**Trigger:** `.brainops/methodology/audits/2026-08-08T14-11-19-284Z-6968720d-codex/station-codex-audit.json`.

## Contract

`delete_expired_demo_corpora(now)` must select expired corpus IDs and delete their relational/vector data under one SQLite write transaction. A concurrent delete-and-recreate of the same `corpus_id` with a fresh deadline must not be removed because cleanup acts on a stale pre-lock ID selection.

## RED strategy

One new deterministic test uses real isolated SQLite, a SQLite authorizer barrier at cleanup's first DELETE, and a concurrent recreate transaction. The fresh row must survive whether recreation wins before selection or waits until cleanup commits. Both earlier frozen manifests and tests remain byte-identical.

## Scope

No quota, transport, API, worker timing, corpus public contract, docs, deployment, or packaging change. Expected implementation is transaction-ordering only: acquire the write reservation before the expiry SELECT and retain existing rollback behavior.
