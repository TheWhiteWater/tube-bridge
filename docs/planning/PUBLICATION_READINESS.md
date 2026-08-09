# Publication Readiness — tube-bridge

**Last updated:** 2026-08-09
**Status:** Self-hosted-only v1.0.3 is published. WI-00067 publication evidence is complete; terminal conformance and Station closure are pending.

## Public Surface

The only public product is the MIT self-hosted MCP distributed through:

- GitHub source and releases;
- PyPI;
- public GHCR image.

Users deploy their own instance and own credentials, storage, quota, retention, auth, availability and compliance.

## Core Gates

| # | Area | Priority | Status | Evidence / Exit Criterion |
|---|---|:---:|---|---|
| C1 | Tool/help/schema consistency | P0 | Resolved | One `TOOL_CATALOG` defines exactly 16 tools and derived help metadata. |
| C2 | Deterministic tests and CI | P0 | Resolved | 137 tests pass locally and on Python 3.12/3.13 branch run `31302040564`; tag release run `31302178955` also passes 137 tests and artifact scanning. |
| C3 | Packaging and installed runtime | P0 | Resolved | PyPI/GitHub wheel and sdist share verified registry hashes; twine, complete-archive scan, clean install and installed MCP help/version/16-tool checks pass. |
| C4 | Container distribution | P0 | Resolved | GHCR `1.0.3`, `1.0` and `latest` resolve to digest `sha256:e5a5a735501a5a9f7be5b6a4a66981c959e7736bd6303e9829e1484c27cbaf58`; pulled-image MCP help/version/16-tool checks pass. |
| C5 | Secret and license review | P0 | Resolved | MIT license; no bundled API/proxy/Bearer credentials. |
| C6 | Documentation alignment | P0 | Final gate | Three bounded v1.0.3 candidate packs pass; terminal post-publication sync/conformance remains before WI-00067 closure. |
| C7 | Historical release metadata | P1 | Resolved | Functional history remains unyanked; the v1.0.2 GitHub release now identifies current `v1.0.3` as its superseding release. |

## No-Go Conditions

- Bundling or printing credentials.
- Advertising the Operator's private Railway instance as public access.
- Claiming a hosted demo, tester program, OAuth service, managed storage, shared quota/key, account system, SLA, pricing, legal clearance or unsupported coverage metric.
- Misrepresenting GitHub/PyPI/GHCR/CI state.
- Reintroducing retired demo/OAuth behavior without a new accepted ADR and full methodology gates.

## Private Operator Railway

The existing Railway service is personal infrastructure, not a launch surface. Deployment `dd031af0-de10-49ff-aca8-97c7dc00e1fe` is privately verified:

- static `TUBE_BRIDGE_AUTH_KEY` protects MCP routes;
- OAuth/demo/trusted-proxy variables are absent;
- unauthenticated MCP requests must receive `401`;
- authenticated Pi/CLI initialize must pass;
- it carries no public availability, retention, support or compatibility promise.

Its hostname and credentials are not published as a demo.

## Historical Supersession

- ADR-001 hosted-demo controls and WI-00029/WI-00037/WI-00039/WI-00041 evidence remain historical but are not active gates.
- ADR-002 and WI-00047/WI-00057 OAuth/tester work are superseded/cancelled.
- ADR-003 and WI-00060 own the active self-hosted-only transition.
- Git ancestry, audits and receipts remain preserved.

## Exit Rule

WI-00067 closes only when C1–C7 are resolved, hosted branch and tag workflows are green, downloaded registry artifacts pass inspection, documentation audits pass, and the private Operator Railway remains closed. There is no second demo acceptance surface.
