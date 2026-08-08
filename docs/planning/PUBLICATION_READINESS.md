# Publication Readiness Checklist — tube-bridge

**Last updated:** 2026-08-09
**Status:** Both independently gated surfaces are accepted: the published self-hosted core, and the controlled disposable Railway demo with bounded quota and retention.

## How to Read This Table

- **Launch Surface** — which product boundary this item gates: Core library, or Disposable try-before-install demo.
- **P0** = must resolve before accepting the named surface as publication-ready.
- **P1** = should resolve before a broad announcement; explicitly triageable with owner and a calendar or event-based review trigger.
- **P2** = nice-to-have; does not block any surface.
- **Owner Role** = the role responsible for the decision (Operator, Architect), never an agent ID.
- **Exit Criterion** = verifiable condition that marks the row as resolved.
- Rows with "Decision Required" in the Evidence column mean the threshold/value is undecided and needs operator input.

## No-Go Gate

The following conditions permanently block any publication that would violate the MIT open-core boundary:

| Condition | Rationale |
|-----------|-----------|
| Bundling API keys, tokens, or secrets in the repository | Security risk; violates open-core principle |
| Claiming PyPI release when none exists | Misrepresentation |
| Claiming automated CI when none is configured | Misrepresentation |
| Inventing coverage percentages, SLAs, pricing, launch channels, or legal conclusions | Undecided thresholds; must be operator decisions |
| Claiming full-publication acceptance when gates are unresolved | See exit rules below |

## Launch Surface 1: Core Library (MIT)

**Target this cycle.** The open-core Python package — 16 MCP tools, all transports, all cache/corpus logic. Independently installable from source.

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion |
|---|------|:---:|--------|------------|---------------------------|
| C1 | HELP_TEXT / package-docstring count drift | P0 | Resolved | Architect | `TOOL_CATALOG` is the single runtime registry for 16 tools; HELP metadata is derived from it and package docs state 16. Frozen tool/schema/dispatch tests pass. |
| C2 | Deterministic tests and CI | P0 | Resolved | Operator | 125 frozen deterministic tests pass, including SQLite lifecycle and MCP/Docker contracts; hosted CI passes on Python 3.12 and 3.13. |
| C3 | Installation, entrypoint, and registry verification | P0 | Resolved | Architect | Packaged `tube_bridge.cli:main`, wheel+sdist/twine, PyPI publication/install, public GHCR pull, and authenticated registry-image MCP handshake pass. |
| C4 | Independent docs audit | P0 | Resolved | Auditor | Historical corrected-model PASS: `.brainops/methodology/audits/2026-08-08T06-30-02-732Z-f614f821-codex/station-codex-audit.json`. Subsequent audit receipts preserve the remediation trail; current core publication claims are additionally grounded by lifecycle and external release evidence. Demo acceptance remains separate. |
| C5 | Release configuration and license review | P0 | Resolved | Architect | PEP 517/setuptools metadata, MIT license, bounded MCP compatibility, full SHA-256 runtime lock, reproducible Docker consumption, and no bundled auth values verified. |
| C6 | Historical release metadata hygiene | P1 | Resolved | Operator | `v1.0.0` is functional but contains stale publication-state text. It remains unyanked under PyPI's disruption-aware guidance; its GitHub release is explicitly marked superseded for metadata by current `v1.0.2`. Tags/assets and `v1.0.1`/`v1.0.2` are preserved. See the [hygiene audit](../audits/2026-08-09-v1.0.0-release-metadata-hygiene.md). |

## Launch Surface 2: Disposable Try-Before-Install Demo

**Target this cycle.** Railway-hosted disposable demo endpoint (`tube-bridge-production.up.railway.app`) with controlled public access. Decisions resolved per ADR-001 (accepted 2026-08-08): exactly 5 Data API operations per client/IP, isolated Google Cloud project separate from personal use, corpora auto-delete 10 minutes after creation, no persistent volume/accounts/backups/durable transcripts/SaaS/managed hosting.

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion |
|---|------|:---:|--------|------------|---------------------------|
| D1 | Dedicated Google Cloud project and server-side upstream setup | P0 | Resolved | Operator | Operator-confirmed isolated demo GCP configuration; API key and proxy/auth values are Railway environment variables only. Repository and package secret checks pass. |
| D2 | Exact budgets, rate limits, abuse controls, and access controls | P0 | Resolved | Operator | Data API boundary counts exactly 5 attempted network operations per process-lifetime client bucket. Production selects Railway-overwritten `X-Real-IP`; a six-value spoof probe produced one bucket, five allows, and a structured sixth rejection. Restart reset counters to zero. |
| D3 | Monitoring and observability | P0 | Resolved | Operator | `/health` exposes only aggregate allowed/rejected/bucket/TTL metrics; policy failures are structured. Application access logging is disabled and known probe IPs were absent from Railway application logs. No complex exporter is required for this disposable surface. |
| D4 | Policy, privacy, copyright, retention, and deletion | P0 | Resolved | Operator | README publishes the demo data-handling/deletion notice. The application never persists raw IPs; process-random salted HMAC buckets exist only in memory. Railway manifest has no volume; there are no backups/accounts/durable hosting promises. Applicable external policy obligations remain. |
| D5 | Corpus exposure, persistence, and retention choice | P0 | Resolved | Operator | Deterministic clocks prove deletion at the persisted 600-second deadline; startup reconciliation, nearest-deadline worker, transactional relational/vector deletion, rollback and race tests pass. Non-invasive live sampling first observed complete absence 1.577 seconds after the deadline without invoking corpus APIs. Self-hosted storage remains persistent. |
| D6 | YouTube API Services audit/quota-extension path | P1 | Acknowledged | Operator | Official audit/extension path is documented; no request or grant is claimed. Review before any broad demo announcement and immediately if demand approaches the default allocation; becomes P0 if the ceiling is hit first. |

## Conditional / Cross-Surface Items

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion | Condition |
|---|------|:---:|--------|------------|---------------------------|-----------|
| X1 | Quota extension for bounded demo | P1 (conditional) | Acknowledged | Operator | No additional allocation is claimed. Review before broad announcement and when usage approaches default allocation. | Blocking only if the default ceiling is reached before audit/extension completion. |
| X2 | Proxy reliability and volume (IPRoyal residential proxy) | P1 (conditional) | Deployed | Operator | `TUBE_BRIDGE_PROXY` is configured; no reliability SLA is accepted. Review before broad announcement and on an Operator-observed availability-threshold breach. | Becomes P0 only if the accepted transcript/corpus demo promise fails that threshold. |
| X3 | Railway persistence / backups | N/A | N/A | Operator | No persistent volume is required; ephemeral corpora delete at 10 minutes and may disappear earlier on restart. | Removed from blocking consideration while the demo remains non-durable. |

## Exit Rules

1. **Core publication readiness is accepted.** Claims are bounded to GitHub Release, PyPI, public GHCR, hosted CI, and verified self-hosted runtime; no SLA, managed hosting, or legal conclusion is implied.
2. **Core library (Surface 1) and disposable demo (Surface 2) may be released independently.** Each surface has its own gates.
3. **Per-surface gate:** All P0 items for a surface must be resolved with documented evidence before that surface is accepted as ready. P1 items must be triaged with an owner and explicit calendar or event-based review trigger. No-go gate conditions must be confirmed absent.
4. **Operator/Architect sign-off:** Required as a gate verdict for each surface before acceptance.
5. **No claim of unfinished acceptance.** Do not claim a P0 item is resolved without verifiable evidence. Do not extrapolate partial progress into gate satisfaction.

## Current State Summary

- **Product model corrected:** Commercial extension (E1–E4) and Grabbit connector (G1–G2) surfaces removed per ADR-001. Tube-bridge is an MIT self-hosted MCP with a disposable try-before-install demo. No product gateway, billing, entitlement, or managed hosting.
- **Demo decisions implemented (ADR-001):** Isolated server-side setup; exactly 5 attempted Data API operations per Railway-observed IP/process; 10-minute corpus deadlines; no persistent volume, accounts, backups, durable hosting, SaaS, or managed hosting.
- **README and architecture sync:** README, Project Vision, ADR-001 and planning state now describe active controls and their bounded evidence.
- **Audit lineage:** Corrected-model/core receipts remain historical evidence. Demo frozen-TDD includes independent test/source audits plus Station verification, hosted CI and live Railway receipts.
- **Deterministic tests and CI:** Core acceptance remains the original 125-test freeze; the cumulative suite is 209 deterministic tests with hosted Python 3.12/3.13 CI PASS.
- **Install/entrypoint/package route:** PyPI install, CLI/MCP, artifacts/twine and public GHCR runtime PASS (C3).
- **Both surfaces are accepted independently.** The demo acceptance adds no SLA, account continuity, managed-hosting, or durability claim.
- **Release history hygiene:** WI-00034 is complete. Functional PyPI `1.0.0` remains unyanked; GitHub `v1.0.0` now carries an explicit documentation-metadata supersession notice pointing to current `v1.0.2`.
- **Station items:** WI-00028 core publication, WI-00029 demo hardening, and WI-00034 metadata hygiene are complete; conditional P1 items D6/X1/X2 remain triaged and non-blocking absent their documented thresholds.
- **ADR-001:** Accepted and implemented; lifecycle/live evidence, not the ADR alone, supplies demo acceptance.
