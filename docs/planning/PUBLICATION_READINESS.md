# Publication Readiness — tube-bridge

**Last updated:** 2026-08-09
**Status:** Self-hosted core published. No hosted-demo surface exists.

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
| C2 | Deterministic tests and CI | P0 | In verification | Original 125-test core freeze plus five ADR-003 retirement tests pass locally/through Station; final hosted Python 3.12/3.13 CI for the transition is pending. |
| C3 | Packaging and installed runtime | P0 | Resolved | Wheel/sdist, twine, isolated install, synchronous CLI, installed MCP runtime and exact dependency lock pass. |
| C4 | Container distribution | P0 | Resolved | Public GHCR image and authenticated MCP handshake pass. |
| C5 | Secret and license review | P0 | Resolved | MIT license; no bundled API/proxy/Bearer credentials. |
| C6 | Documentation alignment | P0 | In verification | Public docs must describe self-hosting only and ADR-003 as active. |
| C7 | Historical release metadata | P1 | Resolved | Functional `v1.0.0` remains unyanked and explicitly metadata-superseded by current `v1.0.2`. |

## No-Go Conditions

- Bundling or printing credentials.
- Advertising the Operator's private Railway instance as public access.
- Claiming a hosted demo, tester program, OAuth service, managed storage, shared quota/key, account system, SLA, pricing, legal clearance or unsupported coverage metric.
- Misrepresenting GitHub/PyPI/GHCR/CI state.
- Reintroducing retired demo/OAuth behavior without a new accepted ADR and full methodology gates.

## Private Operator Railway

The existing Railway service is personal infrastructure, not a launch surface. Final WI-00060 deployment verification is pending:

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

The project is ready when core C1–C7 are resolved, hosted CI is green, documentation audits pass, and the private Operator Railway checks pass. There is no second demo acceptance surface.
