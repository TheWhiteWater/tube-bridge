# Work Breakdown — tube-bridge

**Active authority:** ADR-003
**Completed transition:** WI-00060
**Active release gate:** WI-00067

## Block A — Interaction Engine

**Status:** Complete

- 16-tool `TOOL_CATALOG` and matching dispatch/help.
- Dual-source Data API/yt-dlp behavior.
- Transcript extraction with real failure causes preserved.
- Read-only YouTube interaction boundary.

## Block B — Transports and Packaging

**Status:** Complete

- Installed synchronous CLI.
- stdio, Streamable HTTP and legacy SSE.
- Optional static Bearer.
- Wheel/sdist, exact lock, PyPI and GHCR distribution.

## Block C — Local Storage and Corpus

**Status:** Complete

- separate `cache.db` and `corpus.db`;
- local fastembed/sqlite-vec search;
- user-managed persistence and retention;
- nullable historical `expires_at` compatibility without active TTL;
- transactional corpus mutation and validated vector-table identifiers.

## Block D — Verification

**Status:** Established core complete; v1.0.3 release gate active

- original 125-test core freeze;
- five-test self-hosted-only retirement contract;
- two-test private-endpoint help remediation;
- five-test v1.0.3 artifact contract, including whole-wheel/sdist private-metadata scans;
- local 137-test, build/twine, isolated install, Docker and MCP candidate checks pass;
- hosted branch/tag CI and terminal release audit remain pending for WI-00067.

## Block E — Documentation and Release History

**Status:** v1.0.3 candidate prepared; external evidence pending

- self-hosting-only public language;
- candidate that becomes the current release `v1.0.3` only after the active registry gate passes;
- functional `v1.0.0`/`v1.0.2` unyanked history preserved;
- ADR-001 hosted-demo clauses and ADR-002 marked superseded;
- private infrastructure excluded from public product claims.

## Block F — Retire Hosted Demo and OAuth

**Status:** Complete; WI-00060 closed after final conformance PASS

### Completed

- [x] Operator accepted ADR-003.
- [x] OAuth/demo/trusted-proxy variables removed from Railway.
- [x] Retirement contract frozen before source changes.
- [x] Demo/OAuth modules and tests removed from active tree.
- [x] Core transport/API/server behavior restored while preserving transcript fix.
- [x] Corpus schema compatibility retained while demo TTL behavior removed.

### Final Evidence

- [x] Independent source audit PASS.
- [x] Six bounded documentation audit packs PASS.
- [x] Source and final-doc hosted CI PASS.
- [x] Simplified source deployed privately as `dd031af0-de10-49ff-aca8-97c7dc00e1fe`.
- [x] Unauthenticated `401`, authenticated MCP initialize/help, Pi extension, absent OAuth routes and exact non-demo health surface verified.
- [x] WI-00047 and WI-00057 recorded terminal as superseded/cancelled by ADR-003.
- [x] WI-00064 removed the final hard-coded private hostname from MCP help; source audit, hosted CI and private live verification pass.
- [x] WI-00060 final conformance PASS and Station closure.

## Block G — Publish v1.0.3 Self-Hosted Artifacts

**Status:** Active; WI-00067

- [x] Operator authorized GitHub Release, PyPI and GHCR publication.
- [x] Deterministic release contract and test-literal hygiene correction frozen and audited.
- [x] Local 137-test/build/twine/wheel-install/Docker/artifact-scan evidence passes.
- [ ] Independent source conformance PASS on the final candidate.
- [ ] Hosted branch CI PASS.
- [ ] Tag `v1.0.3`; release workflow publishes GitHub/PyPI/GHCR.
- [ ] Download/pull all public artifacts and verify version/help/16 tools/no private metadata.
- [ ] Append and verify the `v1.0.2` GitHub supersession notice without yanking history.
- [ ] Terminal docs/TME/Station closure.

## Dependency Graph

```text
A Interaction Engine ─┬─> B Transports/Packaging ─┬─> D Verification
                      └─> C Local Storage ─────────┘
                                      │
                                      └─> E Docs/History ─> F Retirement Gate
```

## Active Test Authority

- Core: `.brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json`
- ADR-003: `.brainops/methodology/frozen-tests/frozen-20260809051810-test_self_hosted_only_contract.py.json`

Demo/OAuth manifests remain in Git history but are removed from the active manifest directory.

## Product Rule

The project publishes software, not hosted access. Every user installs and evaluates their own MCP instance.
