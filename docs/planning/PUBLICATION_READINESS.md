# Publication Readiness — tube-bridge

**Last updated:** 2026-08-10
**Status:** v1.1.0 publication authorized; local release candidate PASS. Hosted publication and downloaded-artifact verification are the remaining release gates.

## Public Surface

The only public product is the MIT self-hosted MCP distributed through:

- GitHub source and releases;
- PyPI;
- public GHCR image;
- a GitHub-only Agent Plugin preview bundle.

Users deploy their own instance and own credentials, storage, quota, retention, auth, availability and compliance. Agent Plugins v1 does not standardize dependency installation; the preview bundle requires an operator-prepared Python 3.12+ environment and ffmpeg.

## v1.1.0 Gates

| # | Area | Priority | Status | Evidence / Exit Criterion |
|---|---|:---:|---|---|
| C1 | Tool/help/schema consistency | P0 | Resolved | One `TOOL_CATALOG` defines exactly 17 tools and derived help metadata; deterministic subtitle selection and frame contracts pass. |
| C2 | Deterministic tests and CI | P0 | Local PASS; hosted pending | 188 deterministic tests pass locally on the candidate. Branch and tag workflows must pass on hosted Python 3.12/3.13. |
| C3 | Python packaging and installed runtime | P0 | Local PASS; publication pending | Wheel/sdist, twine, complete-archive scan, clean install and installed MCP help/version/17-tool checks pass locally. PyPI download must reproduce them after publication. |
| C4 | Container distribution | P0 | Local PASS; publication pending | Candidate Docker MCP handshake passes. GHCR `1.1.0`, `1.1` and `latest` must resolve to one digest and the pulled image must expose v1.1.0/17 tools. |
| C5 | Agent Plugin preview | P0 | Local PASS; publication pending | One discoverable skill, portable secret-free manifests, resolved links, stdio handshake and explicit manual-bootstrap documentation pass. GitHub Release must attach the plugin ZIP. |
| C6 | Secret and license review | P0 | Resolved | MIT license; no bundled API/proxy/Bearer credentials or private methodology source. |
| C7 | Documentation alignment | P0 | Resolved for candidate | Public docs distinguish current v1 corpus runtime from the frozen Corpus v2 contract and identify the plugin as preview/manual bootstrap. |
| C8 | Historical release integrity | P1 | Resolved | v1.0.0–v1.0.3 remain immutable and unyanked; after its gate closes, v1.1.0 will supersede rather than rewrite them. |

## No-Go Conditions

- Bundling or printing credentials.
- Advertising the Operator's private Railway instance as public access.
- Claiming a hosted demo, tester program, OAuth service, managed storage, shared quota/key, account system, SLA, pricing, legal clearance or unsupported coverage metric.
- Claiming the frozen Corpus v2 storage format is implemented by the current runtime.
- Claiming Agent Plugins v1 installs Python dependencies, secrets, permissions, signatures or a test harness.
- Misrepresenting GitHub/PyPI/GHCR/CI state.
- Reintroducing retired demo/OAuth behavior without a new accepted ADR and full methodology gates.

## Private Operator Railway

The existing Railway service remains personal infrastructure and is not a v1.1.0 launch surface. It is not deployed, modified, or advertised by this release. Its hostname and credentials are not published as a demo.

## Historical Supersession

- ADR-001 hosted-demo controls and WI-00029/WI-00037/WI-00039/WI-00041 evidence remain historical but are not active gates.
- ADR-002 and WI-00047/WI-00057 OAuth/tester work are superseded/cancelled.
- ADR-003 and WI-00060 own the active self-hosted-only transition.
- WI-00067 records the accepted v1.0.3 release; v1.1.0 preserves that history.
- Git ancestry, audits and receipts remain preserved.

## Exit Rule

Publication is complete only when branch CI, tag release workflow, GitHub Release assets, PyPI wheel/sdist, GHCR pulled-image MCP, Agent Plugin ZIP inspection, and public artifact hashes all pass. Railway is explicitly outside the gate.
