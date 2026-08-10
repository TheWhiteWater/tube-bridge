# tube-bridge — Project Index

**Self-hosted MIT YouTube MCP. Source tree: 17 tools; 14 keyless-capable, 3 with a user-owned Data API key. No public hosted demo.**

## Quick Navigation

| Document | Purpose |
|---|---|
| [Project Vision](../PROJECT_VISION.md) | Active self-hosted-only product boundary |
| [README](../README.md) | Public install, tools and configuration |
| [Mission](constitution/00_MISSION.md) | Why the project exists |
| [System Context](constitution/01_SYSTEM_CONTEXT.md) | Runtime and trust boundaries |
| [Architecture](constitution/02_ARCHITECTURE.md) | Package and transport design |
| [Data Model](constitution/03_DATA_MODEL.md) | Tool envelopes and SQLite schemas |
| [Glossary](constitution/04_GLOSSARY.md) | Terms |
| [Non-Goals](constitution/05_NON_GOALS.md) | Explicit exclusions |
| [ADR Rules](constitution/06_ADR_RULES.md) | Decision process and active ADR state |
| [MVP Scope](planning/MVP_SCOPE.md) | Included/excluded product surface |
| [Work Breakdown](planning/WORK_BREAKDOWN.md) | Implementation and retirement blocks |
| [Publication Readiness](planning/PUBLICATION_READINESS.md) | Core-only release gates |
| [Open Questions](planning/OPEN_QUESTIONS.md) | Resolved and conditional questions |
| [ADR-003](adr/003-self-hosted-only-private-operator-railway.md) | Active self-hosted-only/private-infrastructure decision |
| [ADR-004](adr/004-v1.1.0-release-test-contract-supersession.md) | v1.1.0 release-test hash authority and historical-manifest preservation |
| [ADR-001](adr/001-demo-api-quota-and-product-boundary.md) | Historical; demo clauses superseded |
| [ADR-002](adr/002-demo-oauth-test-identity.md) | Historical; superseded in full |
| [v1.1.0 release notes](releases/v1.1.0.md) | Frame, subtitle, plugin preview and upgrade boundaries |
| [Corpus v1 retrieval dogfood](research/2026-08-10-corpus-v1-rag-retrieval-dogfood.md) | Four-video retrieval experiment and bounded Corpus v2 findings |
| [v1.0.0 metadata hygiene](audits/2026-08-09-v1.0.0-release-metadata-hygiene.md) | Historical release disposition |

## Tool Inventory

`TOOL_CATALOG` registers 11 YouTube tools, 5 corpus tools and 1 help tool.

- Keyless-capable: search fallback, video info, trending, channel videos, playlist, transcript, one ephemeral timestamped frame, available languages, all five corpus tools and help.
- Data API required: comments, channel search and channel information.

## Active State

- Current public release: `v1.1.0`, with 17 runtime tools plus a GitHub Agent Plugin preview bundle. The historical authorization record (“Authorized release candidate: `v1.1.0`”) is closed by the live evidence in Publication Readiness; earlier artifacts remain immutable release history.
- Public distribution: GitHub, PyPI and GHCR.
- Product: self-hosted software only.
- Auth: optional static Bearer for self-hosted HTTP.
- Storage: user-managed cache/corpus databases with no forced TTL.
- Tests: 188 deterministic source-tree tests, including the preserved release/privacy contracts plus frame, plugin, subtitle, and Corpus v2 contracts.
- Completed WorkItem: WI-00060 closed after source/docs/CI/private-Railway verification and final conformance PASS.
- Completed WorkItem: WI-00067 published and verified self-hosted-only v1.0.3 across GitHub, PyPI and GHCR; final conformance PASS. Published v1.1.0 now supersedes it without altering historical artifacts.
- Historical demo/OAuth WorkItems WI-00047 and WI-00057 are terminal with superseded/cancelled resolutions and do not define current product behavior.
- Grabbit is a completely separate MCP.

## Private Infrastructure

The Operator's Railway service is private personal infrastructure for header-capable Pi/CLI clients. It is not indexed as a public endpoint, demo, tester service or support promise.
