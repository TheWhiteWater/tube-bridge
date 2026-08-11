# Publication Readiness — tube-bridge

**Last updated:** 2026-08-10
**Status:** v1.1.1 is the Operator-authorized Corpus v1 ranking patch candidate. Publication requires complete local, independent, hosted and downloaded-artifact PASS. v1.1.0 remains immutable. Railway is outside the release surface.

## Public Surface

The only public product is the MIT self-hosted MCP distributed through:

- GitHub source and releases;
- PyPI;
- public GHCR image;
- a GitHub-only Agent Plugin preview bundle.

Users deploy their own instance and own credentials, storage, quota, retention, auth, availability and compliance. Agent Plugins v1 does not standardize dependency installation; the preview bundle requires an operator-prepared Python 3.12+ environment and ffmpeg.

## v1.1.1 Patch Gates

| # | Area | Priority | Status | Evidence |
|---|---|:---:|---|---|
| P1 | Corpus v1 behavior | P0 | Resolved | Frozen ranking suites, 211-test preflight and fresh four-video/64-chunk live rerun pass: all four sources represented, strict overlap suppressed, titles and timestamp URLs present. |
| P2 | Release identity and supersession | P0 | In progress | ADR-005 and frozen `test_v1_1_1_release_contract.py` bind exact 1.1.1 package/plugin/server/docs identity and preserve v1.1.0 receipts. |
| P3 | Complete release candidate | P0 | Pending | Requires full 218-test suite, build/twine, clean install, plugin ZIP, artifact scanners and Docker boundary. |
| P4 | Independent and Station audit | P0 | Pending | Requires P0=0/P1=0 and Station conformance PASS for the exact candidate commit. |
| P5 | Public publication | P0 | Pending | Tag workflow must publish GitHub/PyPI/GHCR and all four jobs must pass. |
| P6 | Downloaded artifacts | P0 | Pending | GitHub/PyPI byte equality, clean official-PyPI install, pulled GHCR and public plugin ZIP must pass. |
| P7 | Railway isolation | P0 | Resolved | No Railway deployment or configuration is authorized; workflow contains leak scanners only. |

## Historical v1.1.0 Gates

| # | Area | Priority | Status | Evidence |
|---|---|:---:|---|---|
| C1 | Tool/help/schema consistency | P0 | Resolved | One `TOOL_CATALOG` defines exactly 17 tools; public PyPI and pulled-GHCR MCP smokes expose the same names and v1.1.0 help. |
| C2 | Deterministic tests and CI | P0 | Resolved | 188/188 local PASS; PR/branch and merge CI pass on Python 3.12/3.13; merge run `31391181342`; release run `31391398028`. |
| C3 | Python packaging and installed runtime | P0 | Resolved | GitHub/PyPI wheel SHA-256 `ffad2bc8f30ddc2d8cd3b40b4535c8ecab1310697e4c03c99a5b4283bf0349de`; sdist `058686fa6ddcd98f0a08ba67d2e233eedc2f5fa50e2116430ffa6e1009051a6f`; cross-registry bytes match. Official-PyPI clean install, dependency check, stdio initialize/help/17 tools and live JPEG frame pass. |
| C4 | Container distribution | P0 | Resolved | GHCR `1.1.0`, `1.1` and `latest` resolve to `sha256:207d3a6356ee65b93412f8842557792f73dde884769420340a46d278cb0eef8d`; pulled health/auth/MCP/17-tool, revision label and exact runtime-filesystem boundary pass. |
| C5 | Agent Plugin preview | P0 | Resolved | GitHub asset `tube-bridge-agent-plugin-1.1.0.zip` SHA-256 `e76accc86e6576464f360e80defda07821a198e21e15b6f3fbe13b004b02a2e3`; one discoverable skill, resolved content, public ZIP stdio v1.1.0/17-tool handshake and manual-bootstrap documentation pass. |
| C6 | Secret and license review | P0 | Resolved | MIT license; GitGuardian PASS; TruffleHog verified findings 0; artifact and pulled-image scans find no bundled API/proxy/Bearer credentials, private methodology source or private deployment metadata. |
| C7 | Documentation alignment | P0 | Resolved | Public docs distinguish current v1 corpus runtime from frozen Corpus v2 contract, identify plugin dependency bootstrap as manual, and state no hosted service. Independent convergence audit PASS, P0=0/P1=0. |
| C8 | Historical release integrity | P1 | Resolved | v1.0.0–v1.0.3 remain immutable and unyanked by project policy; v1.1.0 supersedes rather than rewrites them. |

## Public Receipts

- GitHub Release: `https://github.com/TheWhiteWater/tube-bridge/releases/tag/v1.1.0`
- PyPI: `https://pypi.org/project/tube-bridge/1.1.0/`
- GHCR: `ghcr.io/thewhitewater/tube-bridge:1.1.0`
- Tag target: `f7afa9cce0c59753be8105c7931ec3a44f8ea59d`
- Release workflow: `31391398028` — all four jobs PASS
- GitHub assets: wheel, sdist, Agent Plugin ZIP, basename-only `SHA256SUMS`

## No-Go Conditions

- Bundling or printing credentials.
- Advertising the Operator's private Railway instance as public access.
- Claiming a hosted demo, tester program, OAuth service, managed storage, shared quota/key, account system, SLA, pricing, legal clearance or unsupported coverage metric.
- Claiming the frozen Corpus v2 storage format is implemented by the current runtime.
- Claiming Agent Plugins v1 installs Python dependencies, secrets, permissions, signatures or a test harness.
- Reintroducing retired demo/OAuth behavior without a new accepted ADR and full methodology gates.

## Private Operator Railway

The existing Railway service remains personal infrastructure and is not a v1.1.1 launch surface. It is not deployed, modified, or advertised by this release. Its hostname and credentials are not published as a demo.

## Historical Supersession

- ADR-001 hosted-demo controls and WI-00029/WI-00037/WI-00039/WI-00041 evidence remain historical but are not active gates.
- ADR-002 and WI-00047/WI-00057 OAuth/tester work are superseded/cancelled.
- ADR-003 and WI-00060 own the active self-hosted-only transition.
- WI-00067 records the accepted v1.0.3 release; v1.1.0 preserves that history.
- ADR-004 records v1.1.0 test-hash supersession without rewriting prior manifests.
- ADR-005 records the v1.1.1 patch contract and preserves v1.1.0 artifact evidence.

## Exit Rule

v1.1.1 remains blocked until branch/merge CI, tag release workflow, GitHub assets, PyPI wheel/sdist, pulled GHCR MCP, public Agent Plugin ZIP, checksums, secret/private-metadata scans and independent artifact hashes all pass. Railway remains explicitly outside the release surface.
