# Documentation Audit Report — tube-bridge

**Date:** 2026-08-08
**Audit type:** Independent adversarial documentation audit (PUBLICATION_READINESS C4)
**Scope:** 20 files (read_scope) + 5 runtime source files inspected for cross-validation
**Method:** Source inspection (not executed verification). Readonly manifest sha256-hash-verified copies used for scoped docs; live project tree inspected for tube_bridge/ package.

---

## 1. Verdict

**PASS WITH FINDINGS**

The documentation corpus is internally consistent and source-grounded. Zero P0 factual contradictions were found between scoped documents. Two source-drift issues (HELP_TEXT tool count, __init__.py docstring) are correctly and consistently documented as known readiness items across all scoped docs. These are implementation gaps acknowledged by the documentation, not documentation failures. Four P1 imprecisions and two P2 minor issues were identified.

---

## 2. Counts by Severity

| Severity | Count |
|----------|-------|
| P0       | 0     |
| P1       | 4     |
| P2       | 2     |

---

## 3. Findings Table

| ID | Sev | File/Section | Problematic Claim | Source Evidence | Required Correction | Blocks |
|----|-----|-------------|-------------------|-----------------|---------------------|--------|
| F1 | P1 | PROJECT_VISION.md L41 | "zero network surface" for stdio transport | transport.py: stdio has no inbound listening socket, but tools make outbound network calls (yt-dlp subprocess → InnerTube, youtube-transcript-api → TimedText, Data API v3 → Google). 01_SYSTEM_CONTEXT.md L51-52 correctly says "Opens no inbound listening port." | Replace "zero network surface" with "no inbound listening port; outbound network calls still occur for tool operations" to match 01_SYSTEM_CONTEXT.md. | Docs audit only |
| F2 | P1 | README.md L100, AGENTS.md L85 | "fully offline, zero API keys" for embeddings | 02_ARCHITECTURE.md L135-137 and L154: "initial model acquisition may require network" for fastembed model download. 03_DATA_MODEL.md L279: "initial model acquisition may require network." | Add "after model assets are available" qualifier to README.md and AGENTS.md to match constitution docs. | Docs audit only |
| F3 | P1 | docs/planning/WORK_BREAKDOWN.md L104 | Block D exit criterion: "Station references corrected (INDEX.md, OPEN_QUESTIONS stale: reference old project identifiers and agent IDs)" | Current INDEX.md references WI-00027 and DIR-004-publication-productization — no old project identifiers or agent IDs detected. Current OPEN_QUESTIONS.md uses only role-based owners (Operator, Architect), no agent IDs. | Verify whether this exit criterion is already satisfied; if so, mark it [x] and remove the stale claim. If it references issues already fixed in prior sync, update the criterion. | Docs audit only |
| F4 | P1 | docs/planning/WORK_BREAKDOWN.md L98 | "The previous docs/INDEX.md is stale (references old project name and obsolete work item identifiers); this file replaces the old scaffold." | Same as F3 — current INDEX.md shows no stale identifiers. | Remove or update this claim if the stale INDEX.md has already been replaced. | Docs audit only |
| F5 | P2 | README.md L99 | "60–90s windows with overlap" for chunking | corpus.py L84: `window_sec: int = 80, overlap_sec: int = 20`. Constitution docs (02_ARCHITECTURE.md L143, 04_GLOSSARY.md L24) correctly state "80 seconds, 20-second overlap." | Change "60–90s windows" to "80-second windows" for precision. 80s falls within 60-90s range so this is overbroad rather than false. | Docs audit only |
| F6 | P2 | Multiple docs referencing known source drift | HELP_TEXT 11 tools, __init__.py "10 tools" | Source confirms drift: tube_bridge/server.py L20 has `"tools": 11` (numeric) overwritten by L28 `"tools": [...]` (11-item list omitting 5 corpus tools). tube_bridge/__init__.py L3: "10 tools." | Source correction needed as tracked in PUBLICATION_READINESS C1. Docs are already accurate about the drift. Not a documentation failure — implementation gap. | Core (already tracked as PUBLICATION_READINESS C1) |

---

## 4. Consistency Matrix

### 4.1 Tools

| Aspect | Status | Evidence |
|--------|--------|----------|
| Total tool count (16) | CONSISTENT across all 20 scoped docs | PROJECT_VISION, README, AGENTS, 00_MISSION, 01_SYSTEM_CONTEXT, 02_ARCHITECTURE, MVP_SCOPE, INDEX all state 16 |
| Category split (10 + 5 + 1) | CONSISTENT | 10 YouTube interaction + 5 corpus + 1 help documented identically in PROJECT_VISION, README, AGENTS, 00_MISSION, 02_ARCHITECTURE, MVP_SCOPE, INDEX |
| Keyless/Data-API split (13/3) | CONSISTENT | All docs agree: 13 zero-key, 3 require YOUTUBE_API_KEY (comments, channel_search, channel_info) |
| Dual-source tools (3) | CONSISTENT | search, video_info, trending identified as dual-source everywhere |
| HELP_TEXT source drift | CORRECTLY DOCUMENTED | All scoped docs acknowledge 11-tool HELP_TEXT list omitting corpus tools. Source drift = implementation gap, not docs failure. |
| __init__.py "10 tools" drift | CORRECTLY DOCUMENTED | PROJECT_VISION L110, AGENTS L127, 02_ARCHITECTURE L186, PUBLICATION_READINESS C1 all flag this. |

### 4.2 Auth / Transports

| Aspect | Status | Evidence |
|--------|--------|----------|
| 3 transports + /messages + /health | CONSISTENT | All docs agree: stdio, /mcp (Streamable HTTP), /sse (legacy SSE). 01_SYSTEM_CONTEXT L59 correctly notes /messages and /health. |
| Bearer auth scope | CONSISTENT | Every doc states auth protects all remote routes except /health. transport.py L66 verified: `if path != "/health" and not _check_auth(scope)`. |
| /messages POST handler | CONSISTENT | transport.py L77-78 verified: `/messages` behind auth guard. 01_SYSTEM_CONTEXT L59 and MVP_SCOPE L39 and WORK_BREAKDOWN L39 correctly document. |
| /health always open | CONSISTENT | transport.py L43-48 returns tools=16 and auth status. All docs agree. |
| No inbound stdio socket | CONSISTENT (with F1 note) | server.py L26-27 uses stdio_server. 01_SYSTEM_CONTEXT L51-52 correctly: "Opens no inbound listening port." Only PROJECT_VISION "zero network surface" overstates (see F1). |
| Outbound tool network | CONSISTENT | All constitution docs correctly describe outbound calls to TimedText, InnerTube, Data API v3. |

### 4.3 Network / Locality

| Aspect | Status | Evidence |
|--------|--------|----------|
| No external DB/vector/embedding service required | CONSISTENT | 01_SYSTEM_CONTEXT L75, 02_ARCHITECTURE L162, 03_DATA_MODEL L305 all state this clearly. |
| Initial model download needs network | CONSISTENT IN CONSTITUTION | 02_ARCHITECTURE L135-137, L154; 03_DATA_MODEL L279, L301-303; 04_GLOSSARY L21. Only README/AGENTS "fully offline" omits qualifier (see F2). |
| corpus_add fetches transcript over network | CONSISTENT | All docs correctly state this. |
| corpus_list/delete are purely local | CONSISTENT | 03_DATA_MODEL L304 verified. |
| YouTube tools require network to YouTube | CONSISTENT | 01_SYSTEM_CONTEXT L76, 03_DATA_MODEL L300. |

### 4.4 Storage

| Aspect | Status | Evidence |
|--------|--------|----------|
| Separate cache.db and corpus.db | CONSISTENT | All docs agree: distinct files, same directory ($TUBE_BRIDGE_CACHE, default ~/.tube_bridge). Source verified: cache.py L13, corpus.py L15. |
| cache.db tables | CONSISTENT | transcripts + video_info. 03_DATA_MODEL L241-244 matches source. |
| corpus.db tables | CONSISTENT | corpora, corpus_chunks, corpus_added_videos, vec_{corpus_id} virtual tables. 03_DATA_MODEL L249-254 matches source. |
| WAL journal mode | CONSISTENT | Both databases use WAL. 03_DATA_MODEL L239, L247. |
| Chunking: 80s window, 20s overlap | CONSISTENT IN CONSTITUTION | 02_ARCHITECTURE L143, 03_DATA_MODEL L271, 04_GLOSSARY L24. Source verified: corpus.py L84. Only README says "60–90s" (see F5). |
| Embedding model: BGE-small-en-v1.5, 384-dim | CONSISTENT | All docs agree. |
| Model-network boundary at corpus_add | CONSISTENT | All docs note transcript fetch over network; embedding local after model assets available. |

### 4.5 Tests / Package

| Aspect | Status | Evidence |
|--------|--------|----------|
| test_tools.py: 4 unique tools | CONSISTENT | search, video_info, trending, transcript (5th call is same tool with timestamps). 02_ARCHITECTURE L189, MVP_SCOPE L77, WORK_BREAKDOWN L118 all agree. |
| No automated test suite / CI | CONSISTENT | All docs: "not an automated acceptance suite." README L221, AGENTS L94, WORK_BREAKDOWN L119. |
| PyPI unverified | CONSISTENT | All docs say PyPI not published, entrypoint unverified. pyproject.toml L17 exists with `tube-bridge = "server:main"`. |
| No invented coverage/SLA/CI claims | VERIFIED ABSENT | No scoped doc claims coverage %, SLA, pricing, or CI pipeline. |

### 4.6 Quota

| Aspect | Status | Evidence |
|--------|--------|----------|
| Default allocation wording | CONSISTENT | ADR-001 L17, PROJECT_VISION L79, 04_GLOSSARY L10, 05_NON_GOALS L53, OPEN_QUESTIONS L80 all use same wording: "100 search.list calls/day, 100 videos.insert calls/day, and 10,000 units/day combined for other endpoints, subject to change." |
| No purchasable tier | CONSISTENT | ADR-001 L17, PROJECT_VISION L80, 04_GLOSSARY L33, 05_NON_GOALS L53 all state this. |
| Audit/extension process | CONSISTENT | All docs reference YouTube API Services audit/quota-extension process. |
| Quota subject to change | CONSISTENT | All docs include this caveat. |

### 4.7 Product Boundaries

| Aspect | Status | Evidence |
|--------|--------|----------|
| Core (MIT): 16 tools, all transports, cache/corpus | CONSISTENT | PROJECT_VISION, README, AGENTS, 00_MISSION, 02_ARCHITECTURE, MVP_SCOPE, ADR-001 all agree. |
| Controlled demo: deployed, not yet public | CONSISTENT | All docs state demo endpoint exists but controlled access not yet implemented. |
| Extension: separate commercial product layer, not blocking core | CONSISTENT | All docs: extension has own launch gates. PUBLICATION_READINESS Surface 3 clearly marked "Not This Cycle." |
| Grabbit: optional connector, not blocking core | CONSISTENT | All docs: independent opt-in path. PUBLICATION_READINESS Surface 4 clearly marked "Not This Cycle." |
| Extension does not receive shared upstream credentials | CONSISTENT | PROJECT_VISION L74, ADR-001 L53-54. |
| No-go gate conditions | CONSISTENT | PUBLICATION_READINESS lists 5 no-go conditions. None violated in scoped docs. |

### 4.8 Station Identifiers

| Aspect | Status | Evidence |
|--------|--------|----------|
| WI-00027 (documentation synchronization) | CONSISTENT | INDEX L36, WORK_BREAKDOWN L85, PUBLICATION_READINESS L95 all reference WI-00027. |
| DIR-004-publication-productization | CONSISTENT | INDEX L37, PUBLICATION_READINESS L95. |
| No stale agent IDs in scoped docs | VERIFIED ABSENT | No W-NNNN, A-NNNN, or T-NNNN patterns found. All ownership uses role-based references (Operator, Architect). |
| Role-based ownership | CONSISTENT | 06_ADR_RULES L42-48 defines role-based authority. All docs follow this — no agent IDs used as owners. |

---

## 5. Publication Blockers vs Nonblockers

### Confirmed Blockers (documented correctly, not docs failures)

These are correctly documented as unresolved gates. The documentation accurately reflects their status:

| Item | Surface | Status in Docs |
|------|---------|----------------|
| HELP_TEXT/init.py source drift (C1) | Core | Correctly tracked as P0 Open in PUBLICATION_READINESS |
| Deterministic tests + CI (C2) | Core | Correctly tracked as P0 Open |
| Install/entrypoint/registry (C3) | Core | Correctly tracked as P0 Open |
| Demo budgets + abuse controls (D1-D3) | Demo | Correctly tracked as P0 Proposed |
| Policy/legal/privacy (D4) | Demo | Correctly tracked as P0 Decision Required |
| Corpus persistence choice (D5) | Demo | Correctly tracked as P0 Decision Required |
| B1-B4 in OPEN_QUESTIONS | Core+Demo | Correctly documented as Decision Required |

### Nonblockers (verified as not blocking core/demo)

| Item | Docs Claim | Verified |
|------|-----------|----------|
| Extension (Surface 3) | "Must not block core" | PUBLICATION_READINESS L63, L84 |
| Grabbit (Surface 4) | "Must not block core" | PUBLICATION_READINESS L74, L84 |
| C3: Extension economics | "Do not block core" | OPEN_QUESTIONS L93 |
| C4: Grabbit timing | "Do not block core" | OPEN_QUESTIONS L98 |

---

## 6. Recommended Minimal Correction Pack

### Pack 1: PROJECT_VISION.md (1 file)

**F1 fix — "zero network surface" imprecision (L41):**
```
- **stdio** — MCP client spawns `python3 server.py` as a child process; no inbound listening port; tools still make outbound network calls to YouTube upstreams.
```

### Pack 2: README.md + AGENTS.md (2 files)

**F2 fix — "fully offline" embeddings qualification:**

README.md L100:
```
- **Embeddings:** fastembed (BGE-small-en-v1.5, 384-dim), local inference after model assets are available; initial model download may require network. Zero API keys.
```

AGENTS.md L85:
```
- **Embeddings:** fastembed (BGE-small-en-v1.5), local inference after model assets are available; initial model download may require network. Zero API keys.
```

**F5 fix — chunking window precision:**

README.md L99:
```
- **Chunking:** by transcript segments, 80-second windows with 20-second overlap
```

### Pack 3: WORK_BREAKDOWN.md (1 file)

**F3/F4 fix — stale claim about old IDs (L98, L104):**

Verify whether the stale INDEX.md/OPEN_QUESTIONS claims have been resolved during the prior sync (current INDEX.md and OPEN_QUESTIONS show no old project identifiers or agent IDs). If resolved:
- Mark Block D exit criterion L104 as [x] completed
- Remove or update L98 claim about "previous INDEX.md is stale"

---

## Verification Notes

- **No verification commands were provided** in the executor task brief.
- All claims are grounded in source inspection of readonly manifest copies (sha256-hash verified) and live project files (tube_bridge/ package).
- Tools not exercised at runtime; claims about runtime behavior (auth guard, HELP_TEXT dict resolution, cached field behavior) are grounded in static source analysis.
- No invented runtime tests, metrics, legal conclusions, SLAs, package publication, or deployment guarantees.

---

**Auditor:** Independent adversarial audit (executor run RUN-1786164196830-978623a6)
**Method:** Source inspection against readonly manifest copies + live tube_bridge/ package
**Files inspected:** 20 readonly manifest copies + 5 live project files (tube_bridge/server.py, __init__.py, transport.py, tools.py, corpus.py) + pyproject.toml

---

## 7. Remediation and Official Codex Audit Trail — 2026-08-08

The original independent verdict was **PASS WITH FINDINGS**. Findings F1–F5 were remediated across PROJECT_VISION.md, README.md, AGENTS.md, and WORK_BREAKDOWN.md. Two subsequent official Station Codex methodology audits found planning-consistency failures, both since fully remediated in the current PUBLICATION_READINESS, WORK_BREAKDOWN, MVP_SCOPE, and ADR rules:

1. `.brainops/methodology/audits/2026-08-08T05-04-04-265Z-2951ec8e-codex/station-codex-audit.json`: **FAIL** — C4 pending/resolved contradiction and WORK_BREAKDOWN obsolete IDs/priorities. Remediated.
2. `.brainops/methodology/audits/2026-08-08T05-10-33-514Z-7e856e67-codex/station-codex-audit.json`: **FAIL** — MVP_SCOPE stale priorities and combined core/demo gate. Remediated.

**Final official receipt:** `.brainops/methodology/audits/2026-08-08T05-16-06-772Z-64150819-codex/station-codex-audit.json`: **PASS.** Conclusion: canonical C1–C5, D1–D6/X1–X3, E1–E4, G1–G2 and per-surface sign-off are consistent; B1–B4 remain bounded/deferred without authorizing implementation.

**Current documentation-gate status:** C4 is resolved. This does NOT resolve: source drift C1, tests/CI C2, install/package C3, release review C5, demo D1–D6, or any product launch acceptance. HELP_TEXT/package docstring source drift remains a Core blocker, not a docs contradiction.
