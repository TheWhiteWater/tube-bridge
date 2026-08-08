# Work Breakdown — tube-bridge

> **Decomposition into logical blocks. This is NOT a timeline.** Dates are not fabricated. Status reflects current shipped code, open verification items, and blocked decisions.

## Blocks

### Block A: YouTube Interaction Engine

**Status:** Shipped

**What:** The 10 YouTube interaction tools — search, video info, trending, channel videos, playlists, transcripts, languages, comments, channel search, channel info — plus the dual-source architecture (Data API v3 primary → yt-dlp fallback).

**Implementation:**
- `tube_bridge/tools.py` — async tool functions with lru_cache, retry, and dual-source dispatch
- `tube_bridge/youtube/api.py` — stdlib `urllib` Data API v3 client
- `tube_bridge/youtube/client.py` — yt-dlp subprocess client with retry + backoff
- `tube_bridge/youtube/transcript.py` — youtube-transcript-api wrapper (manual > ASR, proxy support)
- `tube_bridge/youtube/models.py` — VideoInfo dataclass

**Depends on:** —

**Evidence:** 16 `Tool()` registrations in `tube_bridge/server.py` `list_tools()` (lines 67–248); all 10 YouTube tool names verified. 13 work keyless; 3 require `YOUTUBE_API_KEY`.

**Exit Criteria:**
- [x] All 10 YouTube tools registered in source (`list_tools()`)
- [x] Dual-source fallback implemented in source (`tube_bridge/tools.py`)
- [x] Cache layer implemented in source (`cache.db` for transcripts and metadata)
- [x] HELP metadata is derived from the single 16-entry `TOOL_CATALOG`

---

### Block B: Transports and Deployment

**Status:** Core transports published and accepted; disposable-demo hardening open

**What:** All MCP transports — stdio (child process), Streamable HTTP `/mcp` (recommended for remote), legacy SSE `/sse` with `/messages` POST handler — plus `/health` route and optional Bearer auth. Railway demo deployment.

**Implementation:**
- `tube_bridge/transport.py` — StreamableHTTP session manager, SSE transport, auth middleware, `/messages` handler (line 77–78), auth check at line 66
- `server.py` — entrypoint: argument parsing, transport dispatch (stdio vs HTTP)
- `pyproject.toml` — verified project metadata and packaged synchronous console entrypoint

**Depends on:** Block A

**Evidence:** `tube_bridge/transport.py` lines 1–22 show `_get_auth_key()`, `_check_auth()`, and transport wiring. Line 66 auth check: `if path != "/health" and not _check_auth(scope)` protects `/mcp`, `/sse`, and `/messages`. Railway endpoint deployed at `tube-bridge-production.up.railway.app`.

**Exit Criteria:**
- [x] 3 transports (stdio, `/mcp`, `/sse`) plus `/messages` handler and `/health` route implemented in source
- [x] Bearer auth implemented in source: protects every remote route except `/health` (transport.py line 66)
- [x] Railway demo endpoint deployed
- [x] Isolated wheel installation and packaged `tube_bridge.cli:main` entrypoint verified (C3, P0)
- [ ] Public hardening: 5-operation limit enforcement and 10-minute corpus TTL not yet implemented (D1–D5, P0)

**Test Hash:** `.brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json` (transport/auth/MCP/Docker contracts included)

---

### Block C: Semantic Corpus Engine

**Status:** Self-hosted engine shipped; deterministic dispatch/SQLite lifecycle accepted, live embedding smoke remains environment-dependent

**What:** 5 corpus tools (`corpus_create`, `corpus_add`, `corpus_search`, `corpus_list`, `corpus_delete`) backed by sqlite-vec + fastembed local embedding inference.

**Implementation:**
- `tube_bridge/corpus.py` — corpus management, chunking, embedding via fastembed (BGE-small-en-v1.5, 384-dim)
- `corpus.db` — separate SQLite database in `~/.tube_bridge/` (same directory as `cache.db`)

**Depends on:** Block A (`corpus_add` fetches transcripts over network)

**Evidence:** `tube_bridge/corpus.py` line 15: `DB_PATH = CACHE_DIR / "corpus.db"`. 5 corpus tools registered in `list_tools()`. Local embedding inference implemented in source; initial model acquisition may require network.

**Exit Criteria:**
- [x] All 5 corpus tools registered in source (`list_tools()`)
- [x] Separate `corpus.db` from `cache.db` (source-verified)
- [x] Local embedding inference (fastembed) implemented in source; initial model acquisition remains environment-dependent
- [ ] Demo corpus TTL implementation/verification remains open under WI-00029 (D5, P0); self-hosted instances retain persistent storage
- [x] Automated corpus schema/dispatch and SQLite success/miss/early-return/rollback lifecycle contracts pass

**Test Hash:** `.brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json`

---

### Block D: Documentation and Station Synchronization

**Status:** Complete — documentation synchronized with published core and separately open demo gate

**What:** Governance, planning, and station-aligned documentation synchronized with the current product and readiness state. Includes ADR rules, MVP scope, work breakdown, and publication readiness checklist. Commercial extension and Grabbit connector surfaces removed per ADR-001.

**Implementation:**
- `docs/constitution/06_ADR_RULES.md` — ADR governance
- `docs/planning/MVP_SCOPE.md` — retrospective scope
- `docs/planning/WORK_BREAKDOWN.md` — this file
- `docs/planning/PUBLICATION_READINESS.md` — gate checklist
- `docs/adr/001-demo-api-quota-and-product-boundary.md` — accepted architecture direction

**Depends on:** Blocks A, B, C (documents describe shipped state)

**Evidence:** Active Station WorkItem tracks documentation synchronization. Commercial extension (E1–E4) and Grabbit connector (G1–G2) surfaces removed from planning docs per ADR-001. Demo decisions resolved: isolated Google project, 5 ops/IP, 10-min corpus TTL, no persistence/accounts. Current `docs/INDEX.md` and `docs/planning/OPEN_QUESTIONS.md` use only role-based owners (Operator, Architect) and current WorkItem identifiers; no stale project identifiers or agent IDs remain.

**Exit Criteria:**
- [x] ADR-001 accepted and documented as active architecture direction
- [x] MVP scope grounded in shipped code, not forward-looking speculation
- [x] Work breakdown blocks A–F defined with evidence-based statuses
- [x] Station references corrected — INDEX.md and OPEN_QUESTIONS use only role-based owners and current WorkItem identifiers; no stale project identifiers or agent IDs remain
- [x] Checklist classified/triaged by launch surface
- [x] B1–B4 Operator/Architect decisions resolved per ADR-001; implementation remains open
- [x] Historical corrected-model PASS retained; later core lifecycle/publication evidence and demo boundaries synchronized

**Docs Audit:** The corrected-model PASS at `.brainops/methodology/audits/2026-08-08T06-30-02-732Z-f614f821-codex/station-codex-audit.json` is historical documentation evidence. Later lifecycle and external receipts accept core source/tests/package/publication. B1–B3 demo decisions remain implementation-open under WI-00029; B4 core release evidence is complete.

**Test Hash:** — *(no hash — documentation, not testable code)*

---

### Block E: Tests, CI, and Package Verification

**Status:** Complete — self-hosted core published and externally verified

**What:** Frozen automated suite, CI configuration, package/install/entrypoint verification, exact dependency lock and Docker runtime acceptance for the self-hosted core.

**Current State:**
- 125 deterministic frozen tests pass; `test_tools.py` remains an optional network-dependent smoke.
- GitHub Actions CI passes on Python 3.12 and 3.13.
- `tube_bridge.cli:main` is verified locally and from a clean PyPI installation.
- Wheel+sdist, `twine check`, exact SHA-256 lock, SQLite cleanup, public GHCR pull, health/auth and authenticated MCP handshake pass.
- GitHub Release, PyPI and GHCR publication receipts are present.

**Depends on:** Blocks A, B, C

**Exit Criteria:**
- [x] Deterministic unit/contract tests with mocked upstreams (C2, P0)
- [x] CI workflow configured and hosted Python 3.12/3.13 jobs pass (C2, P0)
- [x] Existing `test_tools.py` retained as optional/manual evidence, not the CI gate
- [x] All 16 registered tool schemas/help/dispatch covered
- [x] Isolated wheel install, console entrypoint, installed MCP, artifacts and metadata verified (C3, P0)
- [x] Publication claims are evidence-backed; no invented coverage percentage, SLA, managed-hosting or legal claim

**Test Hash:** `.brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json` (10 files; Station hash verification PASS)

---

### Block F: Disposable Demo Implementation

**Status:** Blocked on implementation

**What:** Disposable try-before-install demo endpoint with: isolated Google Cloud project upstream configuration separate from personal use (D1, P0), exactly 5 Data API operations per client/IP enforcement (D2, P0), counters/errors observability sufficient to enforce the limit and TTL (D3, P0), self-hosted boundary and disposable demo disclosure (D4, P0), and 10-minute corpus auto-deletion (D5, P0). YouTube API Services audit/quota-extension path (D6, conditional P1). No persistent volume, accounts, backups, durable transcripts, SaaS, or managed hosting.

**Depends on:** Blocks A, B, C (demo endpoint exists)

**Evidence:** ADR-001 (accepted 2026-08-08) defines all demo decisions: isolated GCP project, 5 ops/IP, 10-min corpus TTL, no persistence. `PUBLICATION_READINESS.md` P0 items D1–D5 are Decision Resolved / Implementation Open.

**Exit Criteria:**
- [ ] Isolated Google Cloud project provisioned with server-side upstream config (P0, D1)
- [ ] 5 Data API operations per client/IP enforced and tested (P0, D2)
- [ ] Counters/errors observability for limit enforcement and TTL (P0, D3)
- [ ] Self-hosted boundary and disposable demo nature documented (P0, D4)
- [ ] 10-minute corpus auto-deletion implemented and tested (P0, D5)
- [ ] YouTube API Services audit/quota-extension path initiated or documented with timeline (P1 conditional, D6)

**Test Hash:** — *(no hash — operational configuration and implementation, not yet tested)*

---

## Dependency Graph

```
A (Interaction Engine) ──→ B (Transports/Deploy)
│                           │
├──→ C (Corpus Engine)      ├──→ E (Tests/CI/Package)
│                           │
└──→ D (Docs/Station Sync)  └──→ F (Disposable Demo Implementation)
```

- A is foundational — all other blocks depend on it.
- B and C are parallel after A; both shipped.
- D (docs sync) is complete; corrected-model Codex documentation audit passed.
- E (tests/CI/package publication) is complete for the self-hosted core and depends on A, B, C.
- F (disposable demo) depends on B and C; all decisions resolved per ADR-001; implementation open.
- No extension or Grabbit implementation items exist.

## Gates (Mandatory Checkpoints)

After each block:
- [ ] ADR written for architecture decisions made in the block
- [ ] Evidence verified against shipped code or operator decisions
- [ ] Documentation updated if the block changes product scope or boundaries
- [x] Publication readiness checklist reviewed; core closed and remaining demo P0/P1 items retained

## Publication Readiness Authority

The canonical readiness checklist is `docs/planning/PUBLICATION_READINESS.md`. It defines:

- **P0 items** — must resolve before the named surface is accepted as publication-ready. Core library P0 items are C1–C5; disposable demo P0 items are D1–D5.
- **P1 items** — should resolve before a broad announcement; explicitly triageable with owner and timeline. D6 (quota extension) is conditional P1 for the demo. X1–X2 are cross-surface conditional items; X3 is N/A (no persistent volume with ephemeral corpora).
- **P2 items** — do not block publication.
- **No-go gate** — conditions that permanently block publication (bundling secrets, misrepresenting CI/PyPI, inventing metrics).

Tube-bridge is an MIT self-hosted MCP with a disposable try-before-install demo. There is no commercial extension, product gateway, billing, entitlement, or Grabbit connector. The open-core 16 tools are independently installable and MIT-licensed.

---

> **Role owners** (Operator, Architect, Auditor, Executor) are responsible for decisions, not specific agent IDs. The core frozen-test hash is recorded above; demo-specific tests remain absent until WI-00029.
