# Work Breakdown — tube-bridge

> **Decomposition into logical blocks. This is NOT a timeline.** Dates are not fabricated. Status reflects accepted shipped code/evidence plus explicitly conditional, nonblocking operations.

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

**Evidence:** `TOOL_CATALOG`/`list_tools()` in `tube_bridge/server.py` register 16 tools; all 10 YouTube tool names are verified. 13 work keyless; 3 require `YOUTUBE_API_KEY`.

**Exit Criteria:**
- [x] All 10 YouTube tools registered in source (`list_tools()`)
- [x] Dual-source fallback implemented in source (`tube_bridge/tools.py`)
- [x] Cache layer implemented in source (`cache.db` for transcripts and metadata)
- [x] HELP metadata is derived from the single 16-entry `TOOL_CATALOG`

---

### Block B: Transports and Deployment

**Status:** Core transports published; disposable-demo transport, identity, quota and retention controls accepted

**What:** All MCP transports — stdio (child process), Streamable HTTP `/mcp` (recommended for remote), legacy SSE `/sse` with `/messages` POST handler — plus `/health` route and optional Bearer auth. Railway demo deployment.

**Implementation:**
- `tube_bridge/transport.py` — Streamable HTTP session manager, SSE transport, auth/identity middleware, `/messages` and `/health`
- `tube_bridge/cli.py` — argument parsing and stdio-vs-HTTP runtime selection
- `server.py` — source-checkout compatibility wrapper delegating to `tube_bridge.cli:main`
- `pyproject.toml` — verified project metadata and packaged synchronous console entrypoint

**Depends on:** Block A

**Evidence:** `tube_bridge.cli` selects stdio or HTTP; `tube_bridge.transport` wires `/mcp`, `/sse`, `/messages`, `/health`, Bearer auth and request identity. Railway endpoint is deployed at `tube-bridge-production.up.railway.app`.

**Exit Criteria:**
- [x] 3 transports (stdio, `/mcp`, `/sse`) plus `/messages` handler and `/health` route implemented in source
- [x] Bearer auth implemented in `tube_bridge.transport`: protects every remote route except `/health`
- [x] Railway demo endpoint deployed
- [x] Isolated wheel installation and packaged `tube_bridge.cli:main` entrypoint verified (C3, P0)
- [x] Public hardening: Railway-overwritten identity, 5-operation enforcement, privacy-preserving aggregates and 10-minute corpus TTL accepted (D1–D5, P0)

**Test Hash:** `.brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json` (transport/auth/MCP/Docker contracts included)

---

### Block C: Semantic Corpus Engine

**Status:** Self-hosted engine shipped; deterministic dispatch/SQLite lifecycle accepted, live embedding smoke remains environment-dependent

**What:** 5 corpus tools (`corpus_create`, `corpus_add`, `corpus_search`, `corpus_list`, `corpus_delete`) backed by sqlite-vec + fastembed local embedding inference.

**Implementation:**
- `tube_bridge/corpus.py` — corpus management, chunking, embedding via fastembed (BGE-small-en-v1.5, 384-dim)
- `corpus.db` — separate SQLite database in `~/.tube_bridge/` (same directory as `cache.db`)

**Depends on:** Block A (`corpus_add` fetches transcripts over network)

**Evidence:** `tube_bridge.corpus.DB_PATH` resolves to `CACHE_DIR / "corpus.db"`. Five corpus tools are registered by `list_tools()`. Local embedding inference is implemented; initial model acquisition may require network.

**Exit Criteria:**
- [x] All 5 corpus tools registered in source (`list_tools()`)
- [x] Separate `corpus.db` from `cache.db` (source-verified)
- [x] Local embedding inference (fastembed) implemented in source; initial model acquisition remains environment-dependent
- [x] Demo corpus TTL implemented and verified under WI-00029 (D5, P0); self-hosted instances retain persistent storage
- [x] Automated corpus schema/dispatch and SQLite success/miss/early-return/rollback lifecycle contracts pass

**Test Hash:** `.brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json`

---

### Block D: Documentation and Station Synchronization

**Status:** Complete — documentation synchronized with the published core and accepted disposable demo

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
- [x] B1–B4 Operator/Architect decisions and WI-00029 implementation/live evidence resolved per ADR-001
- [x] Historical corrected-model PASS retained; later core lifecycle/publication evidence and demo boundaries synchronized

**Docs Audit:** The corrected-model PASS at `.brainops/methodology/audits/2026-08-08T06-30-02-732Z-f614f821-codex/station-codex-audit.json` is historical documentation evidence. Later lifecycle/external receipts accept core publication. WI-00029 frozen-TDD, hosted CI and live Railway evidence accept B1–B3 demo implementation; B4 core release evidence remains complete.

**Test Hash:** — *(no hash — documentation, not testable code)*

---

### Block E: Tests, CI, and Package Verification

**Status:** Complete — self-hosted core published and externally verified

**What:** Frozen automated suite, CI configuration, package/install/entrypoint verification, exact dependency lock and Docker runtime acceptance for the self-hosted core.

**Current State:**
- The original core freeze remains 125 deterministic tests; the cumulative source/demo suite is 209 deterministic tests. `test_tools.py` remains an optional network-dependent smoke.
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

**Status:** Complete — D1–D5 P0 accepted; D6 remains conditional P1

**What:** Controlled try-before-install demo with isolated server-side upstream configuration, exactly 5 attempted Data API operations per observed IP/process, aggregate observability, a published disposable-data boundary, and transactional 10-minute corpus deletion. No persistent volume, accounts, backups, durable hosting, SaaS, or managed-hosting promise.

**Depends on:** Blocks A, B, C (complete)

**Evidence:** Frozen-TDD manifests for WI-00029 and its bounded race/identity addenda; 209 deterministic tests; hosted Python 3.12/3.13 CI; independent source audits; live Railway one-bucket spoof probe, five-allow/sixth-reject result, restart reset, no-volume deployment manifest, known-IP log absence, and non-invasive SQLite TTL inspection.

**Exit Criteria:**
- [x] Isolated Google Cloud project provisioned with server-side upstream config (P0, D1)
- [x] 5 Data API operations per Railway-overwritten `X-Real-IP` enforced and adversarially tested (P0, D2)
- [x] Aggregate counters and structured errors expose limit/TTL state without raw identity (P0, D3)
- [x] Self-hosted boundary and disposable demo data-handling notice documented (P0, D4)
- [x] 10-minute corpus deletion implemented, race-hardened, deterministically tested and live-observed (P0, D5)
- [ ] YouTube API Services audit/quota-extension path (P1 conditional; non-blocking until the documented threshold is reached)

**Test Hashes:** `.brainops/methodology/frozen-tests/frozen-tdd-wi-00029-demo-hardening-001-python.json` plus WI-00037, WI-00039 and WI-00041 addendum manifests (all Station hash verification PASS).

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
- F (disposable demo) depends on B and C; D1–D5 implementation and acceptance are complete.
- No extension or Grabbit implementation items exist.

## Gates (Mandatory Checkpoints)

Final checkpoint state:
- [x] ADR-001 records the architecture decisions; no additional ADR was triggered by mechanical hardening
- [x] Evidence verified against shipped code, frozen tests, hosted CI, Operator decisions and live Railway probes
- [x] Documentation updated for product scope, implementation and acceptance boundaries
- [x] Publication readiness checklist reviewed; core and demo P0 gates closed, conditional demo P1 items retained

## Publication Readiness Authority

The canonical readiness checklist is `docs/planning/PUBLICATION_READINESS.md`. It defines:

- **P0 items** — must resolve before the named surface is accepted as publication-ready. Core library P0 items are C1–C5; disposable demo P0 items are D1–D5.
- **P1 items** — should resolve before a broad announcement; each has an owner and event-based review trigger. D6 (quota extension) is conditional P1 for the demo. X1–X2 are cross-surface conditional items; X3 is N/A (no persistent volume with ephemeral corpora).
- **P2 items** — do not block publication.
- **No-go gate** — conditions that permanently block publication (bundling secrets, misrepresenting CI/PyPI, inventing metrics).

Tube-bridge is an MIT self-hosted MCP with a disposable try-before-install demo. There is no commercial extension, product gateway, billing, entitlement, or Grabbit connector. The open-core 16 tools are independently installable and MIT-licensed.

---

> **Role owners** (Operator, Architect, Auditor, Executor) are responsible for decisions, not specific agent IDs. Core and cumulative demo frozen-test manifests are recorded above; conditional P1 operations remain role-owned.
