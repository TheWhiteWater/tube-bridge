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
- [ ] Source HELP_TEXT correction needed: its 11-entry list omits five corpus tools and duplicate key overwrites numeric count; must reflect 16 registered tools

---

### Block B: Transports and Deployment

**Status:** Shipped (transports); public hardening open

**What:** All MCP transports — stdio (child process), Streamable HTTP `/mcp` (recommended for remote), legacy SSE `/sse` with `/messages` POST handler — plus `/health` route and optional Bearer auth. Railway demo deployment.

**Implementation:**
- `tube_bridge/transport.py` — StreamableHTTP session manager, SSE transport, auth middleware, `/messages` handler (line 77–78), auth check at line 66
- `server.py` — entrypoint: argument parsing, transport dispatch (stdio vs HTTP)
- `pyproject.toml` — project metadata and console entrypoint (publication unverified)

**Depends on:** Block A

**Evidence:** `tube_bridge/transport.py` lines 1–22 show `_get_auth_key()`, `_check_auth()`, and transport wiring. Line 66 auth check: `if path != "/health" and not _check_auth(scope)` protects `/mcp`, `/sse`, and `/messages`. Railway endpoint deployed at `tube-bridge-production.up.railway.app`.

**Exit Criteria:**
- [x] 3 transports (stdio, `/mcp`, `/sse`) plus `/messages` handler and `/health` route implemented in source
- [x] Bearer auth implemented in source: protects every remote route except `/health` (transport.py line 66)
- [x] Railway demo endpoint deployed
- [ ] Source installation and entrypoint verification: `pip install .` from source checkout and console entrypoint `tube-bridge = "server:main"` not yet verified (C3, P0)
- [ ] Public hardening: demo quota/abuse controls (D1–D5, P0) not yet implemented

**Test Hash:** — *(no hash — tests not written)*

---

### Block C: Semantic Corpus Engine

**Status:** Shipped (engine); persistence and acceptance open

**What:** 5 corpus tools (`corpus_create`, `corpus_add`, `corpus_search`, `corpus_list`, `corpus_delete`) backed by sqlite-vec + fastembed local embedding inference.

**Implementation:**
- `tube_bridge/corpus.py` — corpus management, chunking, embedding via fastembed (BGE-small-en-v1.5, 384-dim)
- `corpus.db` — separate SQLite database in `~/.tube_bridge/` (same directory as `cache.db`)

**Depends on:** Block A (`corpus_add` fetches transcripts over network)

**Evidence:** `tube_bridge/corpus.py` line 15: `DB_PATH = CACHE_DIR / "corpus.db"`. 5 corpus tools registered in `list_tools()`. Local embedding inference implemented in source; initial model acquisition may require network.

**Exit Criteria:**
- [x] All 5 corpus tools registered in source (`list_tools()`)
- [x] Separate `corpus.db` from `cache.db` (source-verified)
- [x] Local embedding inference (fastembed) implemented in source; formal runtime acceptance open
- [ ] Railway persistence: `corpus.db` ephemeral without volume mount; persistence mode gated by D5 and X3 (conditional, P0 only when persistent hosted corpus is selected/advertised)
- [ ] Corpus acceptance: automated corpus tests not written

**Test Hash:** — *(no hash — tests not written)*

---

### Block D: Documentation and Station Synchronization

**Status:** Documentation synchronization and Station/TME reconciliation complete; Operator launch decisions remain pending

**What:** Governance, planning, and station-aligned documentation synchronized with the current product and readiness state. Includes ADR rules, MVP scope, work breakdown, and publication readiness checklist.

**Implementation:**
- `docs/constitution/06_ADR_RULES.md` — ADR governance
- `docs/planning/MVP_SCOPE.md` — retrospective scope
- `docs/planning/WORK_BREAKDOWN.md` — this file
- `docs/planning/PUBLICATION_READINESS.md` — gate checklist
- `docs/adr/001-demo-api-quota-and-product-boundary.md` — accepted architecture direction

**Depends on:** Blocks A, B, C (documents describe shipped state)

**Evidence:** Active Station WorkItem tracks documentation synchronization. The previous `docs/INDEX.md` has been replaced. Current `docs/INDEX.md` and `docs/planning/OPEN_QUESTIONS.md` use only role-based owners (Operator, Architect) and current WorkItem identifiers; no stale project identifiers or agent IDs remain.

**Exit Criteria:**
- [x] ADR-001 accepted and documented as active architecture direction
- [x] MVP scope grounded in shipped code, not forward-looking speculation
- [x] Work breakdown blocks A–H defined with evidence-based statuses
- [x] Station references corrected — INDEX.md and OPEN_QUESTIONS use only role-based owners and current WorkItem identifiers; no stale project identifiers or agent IDs remain
- [x] checklist classified/triaged by launch surface
- [ ] four B1-B4 Operator/Architect decisions and associated implementation/evidence remain unresolved

**Docs Audit:** Independent audit report exists at `docs/audits/2026-08-08-publication-document-audit.md` (verdict: PASS WITH FINDINGS). Documentation-audit remediation packs applied: P1/P2 imprecisions resolved across PROJECT_VISION.md, README.md, AGENTS.md, and this file. Classification/triage of documentation issues is complete. **Official Station Codex document audit at `.brainops/methodology/audits/2026-08-08T05-16-06-772Z-64150819-codex/station-codex-audit.json` returned PASS: all planning ID/priority contradictions resolved.** C4 documentation coherence is now resolved. Prior FAIL receipt (`.brainops/methodology/audits/2026-08-08T05-04-04-265Z-2951ec8e-codex/station-codex-audit.json`) was remediated and is retained as audit trail. Documentation audit/reconciliation exit is complete; this does not close publication gates or mark implementation complete. Four decision blockers B1-B4 (from OPEN_QUESTIONS.md) remain unresolved. Operator launch decisions (D1-D6) remain pending.

**Test Hash:** — *(no hash — documentation, not testable code)*

---

### Block E: Tests, CI, and Package Verification

**Status:** Open

**What:** Automated test suite, CI pipeline, and source-install/entrypoint verification for the open-core library.

**Current State:**
- `test_tools.py` is a 4-unique-tool live smoke script (exercises `youtube_search`, `youtube_get_video_info`, `youtube_get_trending`, `youtube_get_transcript`) against real YouTube. It is network-dependent and NOT suitable as a deterministic PR CI gate.
- No CI pipeline is configured.
- No coverage metrics exist.
- `pyproject.toml` exists with console entrypoint `tube-bridge = "server:main"`; source installation and entrypoint are unverified. Package-registry route (PyPI vs source-only vs both) requires an Operator/Architect decision, then verification of the chosen route.

**Depends on:** Blocks A, B, C

**Exit Criteria:**
- [ ] Deterministic unit/contract tests with mocked upstreams (must not depend on live YouTube/network) (C2, P0)
- [ ] CI pipeline running deterministic tests on PRs (C2, P0)
- [ ] Existing `test_tools.py` 4-tool live smoke retained as optional/manual integration evidence or separately scheduled; not the sole CI gate
- [ ] Full tool coverage test suite (current 4/16 tools exercised in smoke; remainder untested)
- [ ] Source installation and entrypoint verification: `pip install .` from source checkout, console entrypoint `tube-bridge` verified, and Operator/Architect registry-route decision recorded (source-only, PyPI, or both) (C3, P0)
- [ ] No invented coverage percentages, SLAs, or CI claims

**Test Hash:** — *(no hash — automated test suite not yet written)*

---

### Block F: Demo Quota, Security, and Policy Gate

**Status:** Blocked on operator decisions and implementation

**What:** Controlled public demo access: dedicated GCP project (D1, P0), per-user/IP and global daily budgets with abuse controls and access controls (D2, P0), observability and monitoring (D3, P0), policy/legal decisions covering privacy, copyright, retention, and deletion (D4, P0), corpus persistence and retention mode choice (D5, P0), and YouTube API Services audit/quota-extension path (D6, conditional P1).

**Depends on:** Blocks A, B, C (demo endpoint exists)

**Evidence:** ADR-001 defines the architecture direction. `PUBLICATION_READINESS.md` P0 items D1–D5 and conditional P1 item D6 require operator decision or implementation. None are yet resolved.

**Exit Criteria:**
- [ ] Dedicated Google Cloud project provisioned for demo (P0, D1)
- [ ] Per-user/IP and global daily budgets, rate limits, abuse controls, and access controls set and enforced (P0, D2)
- [ ] Monitoring and observability deployed — structured logging, metrics, alerting (P0, D3)
- [ ] Policy/privacy/copyright/retention/deletion documented (P0, D4)
- [ ] Corpus exposure, persistence, and retention mode chosen — ephemeral, persistent, or disabled (P0, D5)
- [ ] YouTube API Services audit/quota-extension path initiated or documented with timeline (P1 conditional, D6)

**Note:** Product gateway (E1) and CWS compliance (E3) belong to extension Block G, not this block. See Block G exit criteria.

**Test Hash:** — *(no hash — operational configuration, not testable code in this block)*

---

### Block G: Commercial Transcript Extension

**Status:** Planned (not started)

**What:** Proposed commercial extension as a separate product layer reusing the tube-bridge engine behind a server-side product gateway. Trial/paid transcript and research capabilities with per-user quota, billing, and support. Has its own launch gates independent of core library publication.

**Depends on:** Blocks A, B, C, F (policy and gateway decisions must precede extension launch)

**Evidence:** Defined in `PROJECT_VISION.md` "Proposed Extension" section, ADR-001 decision #5, and `PUBLICATION_READINESS.md` items E1–E4. No implementation exists.

**Exit Criteria:**
- [ ] Product gateway design — auth, entitlements, usage enforcement (extension-only, E1)
- [ ] Entitlement model, billing integration, trial/pricing structure, support SLAs (extension-only, E2)
- [ ] CWS compliance plan — Chrome Web Store compliance if extension uses CWS distribution (extension-only, E3)
- [ ] Deployment architecture decision — whether extension deploys on same or separate Railway services (extension-only, E4)

**Must not block core library use.** The open-core 16 tools remain MIT-licensed and independently installable. Commercial extension launch gates are separate from core library publication gates unless the Operator explicitly changes the gate.

---

### Block H: Optional Grabbit Connector

**Status:** Deferred (not started)

**What:** Optional connector for batch video-link collection into Grabbit, transcript/research attachment to Grabbit items, and cross-promotion between the tube-bridge extension and Grabbit. Has its own launch gates independent of core library publication.

**Depends on:** Block G (extension gateway must be established first)

**Evidence:** Defined in `PROJECT_VISION.md` "Grabbit Integration" section, ADR-001 decision #6, and `PUBLICATION_READINESS.md` G1–G2. No implementation exists.

**Exit Criteria:**
- [ ] Integration contract for batch video-link collections defined (connector-only, G1)
- [ ] Batch video-link collection workflow implemented
- [ ] Transcript and research attachment operational
- [ ] Cross-promotion terms agreed (connector-only, G2)

**Must not block core library use.** Grabbit is an independent opt-in path; tube-bridge operates fully without it. Grabbit launch gates are separate from core library publication gates unless the Operator explicitly changes the gate.

---

## Dependency Graph

```
A (Interaction Engine) ──→ B (Transports/Deploy)
│                           │
├──→ C (Corpus Engine)      ├──→ F (Demo/Policy Gate) ──→ G (Commercial Extension) ──→ H (Grabbit)
│                           │
└──→ D (Docs/Station Sync)  └──→ E (Tests/CI/PyPI)
```

- A is foundational — all other blocks depend on it.
- B and C are parallel after A; both shipped.
- D (docs sync) documentation synchronization complete; operator decisions pending.
- E (tests/CI) is open and depends on A, B, C.
- F (demo/policy gate) is blocked on operator decisions; depends on B.
- G (commercial extension) is planned; depends on F. Has own launch gates separate from core.
- H (Grabbit) is deferred; depends on G. Has own launch gates separate from core.

## Gates (Mandatory Checkpoints)

After each block:
- [ ] ADR written for architecture decisions made in the block
- [ ] Evidence verified against shipped code or operator decisions
- [ ] Documentation updated if the block changes product scope or boundaries
- [ ] Publication readiness checklist reviewed for new P0/P1 items

## Publication Readiness Authority

The canonical readiness checklist is `docs/planning/PUBLICATION_READINESS.md`. It defines:

- **P0 items** — must resolve before the named surface is accepted as publication-ready. Core library P0 items are C1–C5; controlled demo P0 items are D1–D5; extension and Grabbit items (E1–E4, G1–G2) are extension/connector-only and must not block core library or demo release.
- **P1 items** — should resolve before a broad announcement; explicitly triageable with owner and timeline. D6 (quota extension) is conditional P1 for the controlled demo. X1–X3 are cross-surface conditional items.
- **P2 items** — do not block publication.
- **No-go gate** — conditions that permanently block publication (bundling secrets, misrepresenting CI/PyPI, inventing metrics).

Commercial extension (Block G) and Grabbit connector (Block H) must not block core library use. Each has its own launch gates independent of core library publication. The open-core 16 tools are independently installable and MIT-licensed.

---

> **Role owners** (Operator, Architect, Auditor, Executor) are responsible for decisions, not specific agent IDs. Test hashes are absent because automated tests have not been written; do not invent hashes.
