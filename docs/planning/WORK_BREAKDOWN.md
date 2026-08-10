# Work Breakdown — tube-bridge

**Active authority:** ADR-003
**Completed transition:** WI-00060
**Completed release:** WI-00067 (v1.0.3)
**Authorized release:** v1.1.0 runtime plus Agent Plugin preview

## Block A — Interaction Engine

**Status:** Complete

- 17-tool `TOOL_CATALOG` and matching dispatch/help.
- bounded ephemeral timestamp-to-JPEG `ImageContent` extraction;
- deterministic default-language subtitle cohort selection.
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

**Status:** v1.0.3 historical gate complete; v1.1.0 local candidate PASS

- original 125-test core freeze;
- five-test self-hosted-only retirement contract;
- two-test private-endpoint help remediation;
- five-test v1.0.3 artifact contract, including whole-wheel/sdist private-metadata scans;
- local 137-test, build/twine, isolated install, Docker and MCP candidate checks pass;
- hosted branch/tag runs `31302040564` and `31302178955` pass; final conformance `5e992014` accepts WI-00067 closure.

## Block E — Documentation and Release History

**Status:** v1.1.0 published and externally verified

- self-hosting-only public language;
- the pre-publication condition “v1.1.0 will supersede v1.0.3” is satisfied across GitHub, PyPI and GHCR without rewriting history;
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

**Status:** Complete; WI-00067 closed

- [x] Operator authorized GitHub Release, PyPI and GHCR publication.
- [x] Deterministic release contract and test-literal hygiene correction frozen and audited.
- [x] Local 137-test/build/twine/wheel-install/Docker/artifact-scan evidence passes.
- [x] Independent source conformance PASS on the final candidate.
- [x] Hosted branch CI PASS.
- [x] Tag `v1.0.3`; release workflow publishes GitHub/PyPI/GHCR.
- [x] Download/pull all public artifacts and verify version/help/16 tools/no private metadata.
- [x] Append and verify the `v1.0.2` GitHub supersession notice without yanking history.
- [x] Terminal docs/TME/Station closure.

## Block H — Publish v1.1.0 Runtime and Agent Plugin Preview

**Status:** Complete; v1.1.0 published and externally verified

- [x] Operator authorized GitHub Release, PyPI and GHCR publication; Railway excluded.
- [x] 17-tool frame/subtitle/plugin/Corpus-contract source line independently audited.
- [x] Local 188-test/build/twine, clean install, Docker and live Pi ImageContent smoke pass.
- [x] Branch/PR and merge-commit CI pass on Python 3.12/3.13; merge run `31391181342`.
- [x] Tag `v1.1.0`; release workflow `31391398028` publishes wheel, sdist, GHCR image and Agent Plugin ZIP.
- [x] GitHub/PyPI wheel+sdist hashes match; release `SHA256SUMS` verifies by basename.
- [x] Clean PyPI install exposes v1.1.0/17 tools and returns a valid ephemeral JPEG `ImageContent`.
- [x] GHCR `1.1.0`, `1.1` and `latest` resolve to digest `sha256:207d3a6356ee65b93412f8842557792f73dde884769420340a46d278cb0eef8d`; pulled MCP/auth/17-tool and image-boundary checks pass.
- [x] Public Agent Plugin ZIP has one skill, launches the 17-tool stdio MCP, and contains no private methodology source or deployment metadata.
- [x] Final Station evidence and post-publication state recorded; Railway remained untouched.

## Dependency Graph

```text
A Interaction Engine ─┬─> B Transports/Packaging ─┬─> D Verification
                      └─> C Local Storage ─────────┘
                                      │
                                      └─> E Docs/History ─> F Retirement Gate
```

## Active Test Authority

- v1.1.0 candidate: `.brainops/methodology/frozen-tests/frozen-v1.1.0-release-candidate-tests.json`
- Supersession record: `.brainops/methodology/frozen-tests/supersession-v1.1.0-release-contract.json`
- Decision authority: `docs/adr/004-v1.1.0-release-test-contract-supersession.md`

The prior core, ADR-003 transcript-error, and v1.0.3 manifests remain immutable historical evidence but no longer provide current hash authority for files superseded by ADR-004. Demo/OAuth manifests remain historical and do not define the active product.

## Product Rule

The project publishes software, not hosted access. Every user installs and evaluates their own MCP instance.
