# Publication Readiness Checklist — tube-bridge

**Last updated:** 2026-08-08
**Status:** Decision-ready table for Operator/Architect review. Full-publication readiness is not yet accepted.

## How to Read This Table

- **Launch Surface** — which product boundary this item gates: Core library, Controlled hosted demo, Commercial extension, or Optional Grabbit connector.
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
| C1 | HELP_TEXT / package-docstring count drift | P0 | Open | Architect | `tube_bridge/server.py` line 20: numeric `"tools": 11` is overwritten by an 11-entry runtime `"tools"` list (lines 28–51) that omits 5 corpus tools. No separate numeric count field exists. `tube_bridge/__init__.py` docstring line 3 claims "10 tools." Target: 10 YouTube interaction + 5 corpus + 1 help = 16. Both must be corrected to reflect the authoritative count of 16 registered in `list_tools()`. |
| C2 | Deterministic tests and CI | P0 | Open | Operator | Deterministic unit/contract tests with mocked upstreams (must not depend on live YouTube). CI pipeline running on PRs. Existing `test_tools.py` 4-tool live smoke retained as optional manual integration evidence, not the sole CI gate. |
| C3 | Installation, entrypoint, and registry verification | P0 | Open | Architect | `pip install .` verified from source checkout. Console entrypoint `tube-bridge = "server:main"` (`pyproject.toml` line 17) verified. Package-registry decision recorded (PyPI vs source-only vs both). |
| C4 | Independent docs audit | P0 | Resolved | Auditor | Independent documentation audit completed at `docs/audits/2026-08-08-publication-document-audit.md` (verdict: PASS WITH FINDINGS). P1/P2 documentation imprecisions (F1-F5) remediated across PROJECT_VISION.md, README.md, AGENTS.md, and WORK_BREAKDOWN.md. Official Station Codex document audit at `.brainops/methodology/audits/2026-08-08T05-16-06-772Z-64150819-codex/station-codex-audit.json` returned PASS: all planning ID/priority contradictions resolved. This resolves documentation coherence only and does not imply source/runtime/test/package/demo acceptance. Prior FAIL (`.brainops/methodology/audits/2026-08-08T05-04-04-265Z-2951ec8e-codex/station-codex-audit.json`) remediated and retained as audit trail. |
| C5 | Release configuration and license review | P0 | Open | Architect | `pyproject.toml` reviewed for publication readiness (version, metadata, dependencies, classifiers). MIT license file present and accurate. No bundled secrets. |

## Launch Surface 2: Controlled Hosted Demo

**Target this cycle.** Railway-hosted demo endpoint (`tube-bridge-production.up.railway.app`) with controlled public access.

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion |
|---|------|:---:|--------|------------|---------------------------|
| D1 | Dedicated Google Cloud project and server-side upstream setup | P0 | Proposed | Operator | Separate GCP project created; auth material held server-side only; never committed to repo. Upstream API key provisioned and deployed as Railway environment variable. |
| D2 | Exact budgets, rate limits, abuse controls, and access controls | P0 | Proposed | Operator | Per-consumer identity scheme chosen (IP-based or token-based). Per-user/IP and global daily budgets set and enforced. Rate limiting, anomaly detection, and IP-based throttling deployed. Budget-exceeded returns configurable message. |
| D3 | Monitoring and observability | P0 | Proposed | Operator | Structured logging deployed. Metrics export configured (tool call counts, error rates, quota usage). Alerting configured for quota exhaustion, error spikes, and abuse patterns. Health-check endpoint monitored. |
| D4 | Policy, privacy, copyright, retention, and deletion | P0 | Decision Required | Operator | Written policy: transcript retention period, copyright compliance stance, DMCA takedown path, user data deletion procedure, GDPR considerations. |
| D5 | Corpus exposure, persistence, and retention choice | P0 | Decision Required | Operator | Persistence mode chosen from: ephemeral (may be lost on restart/redeploy; requires disclosure and deletion treatment), persistent (Railway volume mount + retention policy + backup + deletion), or disabled (corpus tools return "not available on demo"). Every mode including ephemeral needs disclosure and deletion/retention treatment documented. |
| D6 | YouTube API Services audit/quota-extension path | P1 | Acknowledged | Operator | Audit/compliance extension process initiated or documented as a plan with timeline. Becomes P0 if demo demand exceeds default allocation before extension is complete. |

## Conditional / Cross-Surface Items

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion | Condition |
|---|------|:---:|--------|------------|---------------------------|-----------|
| X1 | Quota extension for bounded demo | P1 (conditional) | Acknowledged | Operator | Additional allocation requested or documented plan. | Blocking only if demo usage hits default quota ceiling before audit/extension complete. |
| X2 | Proxy reliability and volume (IPRoyal residential proxy) | P1 (conditional) | Deployed | Operator | `TUBE_BRIDGE_PROXY` configured and deployed. Transcript pipeline depends on it for datacenter deployments. Reliability is not yet accepted. | P1 with disclosed limitations. Becomes P0 if the accepted demo transcript/corpus promise fails an Operator-defined availability threshold. |
| X3 | Railway persistence / backups | P1 (conditional) | Open | Operator | Railway volume mount for corpus.db; backup strategy defined and tested. | P0 if persistent hosted corpus is selected and advertised, requiring volume mount plus tested backup/deletion. N/A when corpus is disabled. Ephemeral corpus handled by D5. |

## Launch Surface 3: Commercial Extension (Not This Cycle)

**Must not block core library or controlled demo release.** The extension has its own launch gates independent of core library publication. This table records extension items for completeness; none are P0 for the current cycle.

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion |
|---|------|:---:|--------|------------|---------------------------|
| E1 | Product gateway design (auth, entitlements, usage enforcement) | Extension-only | Proposed | Architect | Server-side product gateway design for entitlements, auth, usage enforcement. |
| E2 | Entitlement model, billing integration, trial/pricing structure | Extension-only | Proposed | Operator | Entitlement model designed; billing integration planned; trial structure, pricing model, and support SLAs defined. |
| E3 | CWS compliance plan (Chrome Web Store) | Extension-only | Proposed | Operator | Chrome Web Store compliance plan if extension uses CWS distribution. |
| E4 | Deployment sharing between core and extension | Extension-only | Open | Architect | Architecture decision on whether extension deploys on same or separate Railway services. |

## Launch Surface 4: Optional Grabbit Connector (Not This Cycle)

**Must not block core library or controlled demo release.** Grabbit is an independent opt-in path with its own launch gates. This table records connector items for completeness; none block any other surface.

| # | Area | Priority | Status | Owner Role | Evidence / Exit Criterion |
|---|------|:---:|--------|------------|---------------------------|
| G1 | Integration contract for batch video-link collections | Connector-only | Proposed | Operator | Contract defined for batch video-link collection and transcript/research attachment to Grabbit items. |
| G2 | Cross-promotion terms | Connector-only | Proposed | Operator | Cross-promotion terms between tube-bridge extension and Grabbit agreed. |

## Exit Rules

1. **Full-publication readiness is not yet accepted.** Do not claim PyPI publication, completed CI, production acceptance, one-click deployment, legal compliance, or any production-ready promise until all P0 items for the named surface are resolved.
2. **Extension and Grabbit do not block core.** Core library (Surface 1) and controlled demo (Surface 2) may be released independently of extension (Surface 3) and Grabbit (Surface 4). Each surface has its own gates.
3. **Per-surface gate:** All P0 items for a surface must be resolved with documented evidence before that surface is accepted as ready. P1 items must be triaged with owner and timeline. No-go gate conditions must be confirmed absent.
4. **Operator/Architect sign-off:** Required as a gate verdict for each surface before acceptance.
5. **No claim of unfinished acceptance.** Do not claim a P0 item is resolved without verifiable evidence. Do not extrapolate partial progress into gate satisfaction.

## Current State Summary

- **README and architecture sync:** Complete. README.md, PROJECT_VISION.md, docs/constitution/02_ARCHITECTURE.md, and 01_SYSTEM_CONTEXT.md are synchronized with shipped source.
- **Official doc audit:** PASS (Codex station-codex-audit, 2026-08-08T05-16-06-772Z). C4 Resolved — documentation coherence verified. C1, C2, C3, C5 and D1–D6 remain unchanged/pending. C4 resolution does not imply source/runtime/test/package/demo acceptance. Prior FAIL receipt (2026-08-08T05-04-04-265Z) remediated and retained as audit trail.
- **Deterministic tests and CI:** Pending (C2, P0).
- **Install/entrypoint/package route:** Pending (C3, P0).
- **Full-publication readiness remains unaccepted.**
- **Active Station items:** WI-00027 (documentation synchronization), DIR-004-publication-productization (TME operating map direction).
- **ADR-001:** Accepted as architecture direction; not launch approval.
