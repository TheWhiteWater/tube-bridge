# tube-bridge — Project Index

**Self-hosted MIT YouTube MCP. 16 tools; 13 keyless-capable, 3 with a user-owned Data API key. No public hosted demo.**

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
| [ADR-001](adr/001-demo-api-quota-and-product-boundary.md) | Historical; demo clauses superseded |
| [ADR-002](adr/002-demo-oauth-test-identity.md) | Historical; superseded in full |
| [v1.0.0 metadata hygiene](audits/2026-08-09-v1.0.0-release-metadata-hygiene.md) | Historical release disposition |

## Tool Inventory

`TOOL_CATALOG` registers 10 YouTube tools, 5 corpus tools and 1 help tool.

- Keyless-capable: search fallback, video info, trending, channel videos, playlist, transcript, available languages, all five corpus tools and help.
- Data API required: comments, channel search and channel information.

## Active State

- Current public release: `v1.0.2`.
- Public distribution: GitHub, PyPI and GHCR.
- Product: self-hosted software only.
- Auth: optional static Bearer for self-hosted HTTP.
- Storage: user-managed cache/corpus databases with no forced TTL.
- Tests: original 125-test core freeze plus five ADR-003 retirement tests.
- Active WorkItem: WI-00060 finalizes source/docs/CI/private-Railway verification.
- Historical demo/OAuth WorkItems are superseded and do not define current product behavior.
- Grabbit is a completely separate MCP.

## Private Infrastructure

The Operator's Railway service is private personal infrastructure for header-capable Pi/CLI clients. It is not indexed as a public endpoint, demo, tester service or support promise.
