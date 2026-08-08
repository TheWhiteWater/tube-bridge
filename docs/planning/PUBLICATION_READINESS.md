# Publication Readiness Checklist — tube-bridge

**Last updated:** 2026-08-08
**Status:** Core release candidate accepted locally under frozen TDD. External full-publication readiness is not yet accepted: push, remote CI, tag, GitHub Release, PyPI upload, and Docker registry publication require a separate Operator gate.

## How to Read This Table

- **Launch Surface** — which product boundary this item gates: Core library, or Disposable try-before-install demo.
- **P0** = must resolve before accepting the named surface as publication-ready.
- **P1** = should resolve before a broad announcement; explicitly triageable with owner and timeline.
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
| C2 | Deterministic tests and CI | P0 | Local Resolved / Remote CI Pending | Operator | 125 frozen deterministic tests pass, including SQLite lifecycle, actual MCP handshakes and Docker. `.github/workflows/ci.yml` is configured; a green hosted run requires the separately authorized push. |
| C3 | Installation, entrypoint, and registry verification | P0 | Local Resolved / Publication Pending | Architect | Packaged synchronous `tube_bridge.cli:main`, isolated wheel install, installed CLI/MCP handshake, wheel+sdist build and `twine check` pass. Actual PyPI upload is an external release action. |
| C4 | Independent docs audit | P0 | Resolved | Auditor | Current corrected-model Station Codex audit passed: `.brainops/methodology/audits/2026-08-08T06-30-02-732Z-f614f821-codex/station-codex-audit.json`. It verifies continuation-safe documentation coherence only; it does not accept source, tests, package, demo implementation, or publication. Two intermediate FAIL receipts (`2026-08-08T06-24-15-276Z-76db5398` and `2026-08-08T06-26-29-240Z-6941e798`) were remediated and retained as audit trail. The older independent report is explicitly marked historical/superseded. |
| C5 | Release configuration and license review | P0 | Resolved | Architect | PEP 517/setuptools metadata, MIT license, bounded MCP compatibility, full SHA-256 runtime lock, reproducible Docker consumption, and no bundled auth values verified. |

## Launch Surface 2: Disposable Try-Before-Install Demo

**Target this cycle.** Railway-hosted disposable demo endpoint (`tube-bridge-production.up.railway.app`) with controlled public access. Decisions resolved per ADR-001 (accepted 2026-08-08): exactly 5 Data API operations per client/IP, isolated Google Cloud project separate from personal use, corpora auto-delete 10 minutes after creation, no persistent volume/accounts/backups/durable transcripts/SaaS/managed hosting.

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion |
|---|------|:---:|--------|------------|---------------------------|
| D1 | Dedicated Google Cloud project and server-side upstream setup | P0 | Decision Resolved / Implementation Open | Operator | ADR-001 decision #1: Separate GCP project created; auth material held server-side only; never committed to repo. Upstream API key provisioned and deployed as Railway environment variable. |
| D2 | Exact budgets, rate limits, abuse controls, and access controls | P0 | Decision Resolved / Implementation Open | Operator | ADR-001 decision #2: Exactly 5 official YouTube Data API v3 operations per observed client IP during the current demo-process lifetime. IP-only identity; no accounts or sessions. Counter is memory-only, has no time reset, resets on process restart, and is never written to durable storage. Implementation and deterministic tests remain open. |
| D3 | Monitoring and observability | P0 | Decision Resolved / Implementation Open | Operator | Counters/errors sufficient to enforce the 5-operation limit and 10-minute corpus TTL. Structured logging deployed. Health-check endpoint monitored. No complex metrics export or multi-signal alerting required for a disposable demo. |
| D4 | Policy, privacy, copyright, retention, and deletion | P0 | Decision Resolved / Implementation Open | Operator | ADR-001 decisions #3 and #6: No persistent volume, backups, accounts, or durable transcript/corpus hosting. Corpora auto-delete 10 minutes after creation. Publish a concise demo data-handling and deletion notice. The transient model avoids an account-based compliance platform but does not waive applicable privacy, copyright, or YouTube policy obligations. |
| D5 | Corpus exposure, persistence, and retention choice | P0 | Decision Resolved / Implementation Open | Operator | ADR-001 decision #3: Every corpus created on the demo is automatically deleted 10 minutes after creation. No persistent volume, backups, accounts, or durable transcript/corpus hosting. Self-hosted instances have full persistent corpus storage under `~/.tube_bridge`. |
| D6 | YouTube API Services audit/quota-extension path | P1 | Acknowledged | Operator | Audit/compliance extension process initiated or documented as a plan with timeline. Becomes P0 if demo demand exceeds default allocation before extension is complete. |

## Conditional / Cross-Surface Items

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion | Condition |
|---|------|:---:|--------|------------|---------------------------|-----------|
| X1 | Quota extension for bounded demo | P1 (conditional) | Acknowledged | Operator | Additional allocation requested or documented plan. | Blocking only if demo usage hits default quota ceiling before audit/extension complete. |
| X2 | Proxy reliability and volume (IPRoyal residential proxy) | P1 (conditional) | Deployed | Operator | `TUBE_BRIDGE_PROXY` configured and deployed. Transcript pipeline depends on it for datacenter deployments. Reliability is not yet accepted. | P1 with disclosed limitations. Becomes P0 if the accepted demo transcript/corpus promise fails an Operator-defined availability threshold. |
| X3 | Railway persistence / backups | P1 (conditional) | N/A | Operator | No persistent volume required — demo corpora auto-delete after 10 minutes per D5/ADR-001 decision #3. | N/A when corpus is ephemeral. Removed from blocking consideration. |

## Exit Rules

1. **Full-publication readiness is not yet accepted.** Do not claim PyPI publication, completed CI, production acceptance, one-click deployment, legal compliance, or any production-ready promise until all P0 items for the named surface are resolved.
2. **Core library (Surface 1) and disposable demo (Surface 2) may be released independently.** Each surface has its own gates.
3. **Per-surface gate:** All P0 items for a surface must be resolved with documented evidence before that surface is accepted as ready. P1 items must be triaged with owner and timeline. No-go gate conditions must be confirmed absent.
4. **Operator/Architect sign-off:** Required as a gate verdict for each surface before acceptance.
5. **No claim of unfinished acceptance.** Do not claim a P0 item is resolved without verifiable evidence. Do not extrapolate partial progress into gate satisfaction.

## Current State Summary

- **Product model corrected:** Commercial extension (E1–E4) and Grabbit connector (G1–G2) surfaces removed per ADR-001. Tube-bridge is an MIT self-hosted MCP with a disposable try-before-install demo. No product gateway, billing, entitlement, or managed hosting.
- **Demo decisions resolved (ADR-001):** Isolated Google Cloud project separate from personal use; exactly 5 Data API operations per client/IP; corpora auto-delete 10 minutes after creation; no persistent volume, accounts, backups, durable transcripts, SaaS, or managed hosting. Implementation remains open.
- **README and architecture sync:** Complete. README.md, PROJECT_VISION.md, docs/constitution/02_ARCHITECTURE.md, and 01_SYSTEM_CONTEXT.md are synchronized with shipped source.
- **Official doc audit:** Current corrected-model PASS at `.brainops/methodology/audits/2026-08-08T06-30-02-732Z-f614f821-codex/station-codex-audit.json`; C4 resolved for documentation coherence only. Source/test/package/demo/publication gates remain independent and open.
- **Deterministic tests and CI:** 125 local frozen tests PASS; hosted CI pending authorized push (C2).
- **Install/entrypoint/package route:** local artifact/CLI/MCP/twine verification PASS; external publication pending (C3).
- **Full-publication readiness remains unaccepted.**
- **Station items:** WI-00027 and WI-00028 are ready for gate; WI-00029 demo hardening is draft. DIR-004-publication-productization remains the active TME direction.
- **ADR-001:** Accepted as architecture direction; not launch approval.
