# WI-00060 Retire Demo/OAuth and Keep Private Railway

## Goal

Return the active product tree to the published self-hosted core while preserving the later transcript error fix and release-history documentation. Convert Railway to private Operator infrastructure.

## Source/Test Scope

- Restore `tube_bridge/cli.py`, `server.py`, `transport.py`, and `youtube/api.py` from `v1.0.2`.
- Do **not** restore `corpus.py` wholesale: retain the nullable five-column `expires_at` schema/migration and current non-demo transactional behavior so databases touched by the retired demo remain readable. Remove only demo-policy imports, expiry workers/helpers, forced deadlines, and demo-only branches.
- Preserve current `tube_bridge/youtube/transcript.py` so the later transcript failure fix is not lost.
- Remove `tube_bridge/demo_policy.py`, `demo_ttl.py`, and `oauth.py`.
- Remove demo/OAuth test files and their active frozen manifests; preserve the core WI-00028 manifest.
- Keep `scripts/station-verify.mjs`, but bind it to the active core source/manifest and core test run.
- Do not rewrite commits or release tags.

## Documentation Scope

- Make README, Project Vision, AGENTS, constitution, planning and index state one public self-hosted product only.
- Do not advertise the private Railway hostname as a demo or public connector.
- Record ADR-001 hosted-demo clauses and ADR-002 as superseded by ADR-003; historical evidence remains available through Git/Station.
- Preserve v1.0.0 metadata-hygiene history and current public release `v1.0.2`.

## Deployment Scope

- Remove OAuth, demo-mode and trusted-proxy variables.
- Keep `TUBE_BRIDGE_AUTH_KEY`, `YOUTUBE_API_KEY`, and `TUBE_BRIDGE_PROXY` without printing or rotating values.
- Deploy the simplified source.
- Verify public network reachability does not imply public access: unauthenticated `/mcp` must return 401 and authenticated Operator initialize must pass.

## Frozen Retirement Contract

Before source deletion, add and independently audit a separate deterministic contract proving:

- retired `oauth`, `demo_policy`, and `demo_ttl` modules are absent;
- active package source contains none of their deployment environment names/imports;
- `/health` contains no demo/OAuth aggregates;
- static Bearer still rejects unauthenticated personal HTTP access and permits the existing protected surface;
- OAuth paths are absent after valid static authentication;
- the later transcript fix still distinguishes upstream/network errors from confirmed missing captions;
- an existing four-column corpus schema migrates safely to nullable `expires_at`, and self-host corpus creation writes five explicit columns with `expires_at = NULL`.

Freeze its SHA-256 without modifying the historical core manifest or any retired historical manifest. Production deletion begins only after ordinary RED and independent contract PASS.

## Gates

1. Independent ADR/plan/test-contract audit PASS.
2. New retirement-contract and historical core-manifest hashes remain valid.
3. Core deterministic, release-build, twine and Docker tests pass.
4. Independent source and bounded documentation audits pass.
5. Hosted CI and private Railway checks pass.
6. WI-00047 and WI-00057 are cancelled/superseded; WI-00060 closes with evidence.
