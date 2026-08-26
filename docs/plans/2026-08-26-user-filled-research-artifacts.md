# User-Filled Research Artifacts Preview Implementation Plan

> **For executor:** Follow strict RED → freeze → GREEN. Do not modify tests after freezing; use addenda for discovered contract defects.

**Goal:** Add an opt-in, self-hosted research-artifact preview that creates machine-prefilled source/corpus scaffolds and lets the user's agent save source-linked research fields, without running any semantic/research model inside Tube Bridge.

**Architecture:** Add a separate local `research-artifacts.db` sidecar plus bundled JSON template definitions. Existing YouTube/corpus code supplies observable machine fields; a generic artifact store owns append-only revisions. Six MCP tools are registered only when `TUBE_BRIDGE_EXPERIMENTAL_RESEARCH_ARTIFACTS=1`, preserving the default immutable v1.1.6 17-tool contract until a future release is separately authorized.

**Tech stack:** Python 3.12, SQLite, stdlib JSON/CSV/importlib.resources, existing jsonschema and MCP SDK.

## Frozen product boundaries

- Tube Bridge fills only `machine_fields`; `agent_fields` begin empty and are supplied by the client agent.
- No LLM/model call exists in scaffold create/save.
- No implicit ASR. Existing caption retrieval may run only because scaffold creation explicitly requests a transcript target.
- Source scaffold machine fields include exact video title; video/channel IDs and URLs; exact observed channel name and channel description; provider/retrieval provenance; transcript track kind/hash; stable segment IDs/timestamps/text.
- Channel description uses Data API when available, with keyless yt-dlp channel-page fallback. Missing descriptions remain explicit `null`; no inference.
- Corpus scaffold uses local corpus membership and cached metadata only by default; it does not fan out hidden network requests across a corpus.
- Research persistence is separate from `cache.db`, `corpus.db`, and the frozen Corpus v2 authority.
- Artifact revisions are append-only; saves require `expected_revision`.
- Existing v1.1.6 public artifacts, package version, release metadata, and default 17-tool catalog remain unchanged.
- No publication, tag, push, deploy, or private operator change.

## Proposed preview tools

1. `research_templates_list`
2. `research_scaffold_create`
3. `research_artifact_get`
4. `research_artifact_save`
5. `research_artifacts_list`
6. `research_artifact_export`

## Task 1 — Freeze template and tool contracts

**Files:**
- Create: `tests/test_research_artifact_contract.py`
- Create: `tests/test_research_artifact_store.py`
- Create: `tests/test_research_scaffold_tools.py`
- Create: `tests/test_research_preview_mcp.py`

**RED contract:**

- bundled definitions contain `structured-source-v1` and `corpus-study-v1`;
- each definition separates machine/agent ownership;
- source scaffold auto-fills video and channel identity/description/provenance;
- transcript source has deterministic version hash, stable segment IDs, and integer-ms ranges;
- all agent fields start empty;
- unavailable transcript/channel description is represented safely without invented data;
- corpus scaffold reflects local membership/cached metadata and does no hidden network fan-out;
- store creates revision 1, saves append revision 2, rejects stale saves, never accepts machine-field updates, lists bindings, and closes SQLite connections;
- complete content maps must cover source segments exactly once in order; drafts may remain incomplete;
- export supports JSON and corpus coding-row CSV;
- preview registry has 23 tools only when explicitly enabled; default registry remains the exact existing 17 tools;
- all six preview tools have correct schemas, annotations, dispatch, and controlled typed errors.

Run targeted tests and record expected failures caused by missing modules/tools, not test defects.

## Task 2 — Freeze test hash

Compute SHA-256 for the four new test files and store an authoritative manifest under `tests/frozen/research-artifacts-preview.sha256`. Re-run the tests and confirm the same RED failures.

## Task 3 — Bundle static template definitions

**Files:**
- Create: `tube_bridge/research_templates/structured-source-v1.json`
- Create: `tube_bridge/research_templates/corpus-study-v1.json`
- Modify: `pyproject.toml` package-data configuration.
- Create: `tube_bridge/research_artifacts.py`

Implement template loading/listing and immutable deep-copy defaults. No persistence or network in this step.

## Task 4 — Implement sidecar append-only store

**File:** `tube_bridge/research_artifacts.py`

Implement `research-artifacts.db` with:

- `artifacts` identity/binding table;
- `artifact_revisions` append-only table;
- transaction/connection context management;
- create/get/list/save;
- optimistic revision checks;
- schema and reference validation;
- JSON and coding-row CSV export.

Do not add delete or in-place update paths.

## Task 5 — Implement observable source assembly

**Files:**
- Modify: `tube_bridge/youtube/models.py`
- Modify: `tube_bridge/youtube/client.py`
- Modify: `tube_bridge/tools.py`
- Modify: `tube_bridge/corpus.py`

Implement:

- preservation of `channel_id` in keyless video info;
- bounded keyless channel-page metadata fetch;
- API-first/channel-page-fallback channel context with safe provenance;
- deterministic transcript source envelope/segment IDs;
- source scaffold assembly with empty agent fields;
- local-only corpus snapshot/scaffold assembly.

## Task 6 — Register preview MCP tools

**File:** `tube_bridge/server.py`

- Add six tool schemas and annotations.
- Gate registration behind `TUBE_BRIDGE_EXPERIMENTAL_RESEARCH_ARTIFACTS=1`.
- Keep default `TOOL_CATALOG`, help, health, and all historical tests at 17.
- Add dispatch branches and wrappers.

## Task 7 — Documentation and package contract

**Files:**
- Add: `docs/design/user-filled-research-artifacts/**`
- Modify the canonical skill only if necessary to point to the optional preview accurately.

Document that the feature is source-preview-only, client-agent-filled, local, and not part of immutable v1.1.6 artifacts. Do not advertise a released capability.

## Task 8 — Verification and audit

Run:

```bash
python3 -m pytest tests/test_research_artifact_contract.py tests/test_research_artifact_store.py tests/test_research_scaffold_tools.py tests/test_research_preview_mcp.py -q
python3 -m pytest tests -q
python3 scripts/check-public-tree.py
```

Also verify:

- default stdio `tools/list` = 17;
- preview-enabled stdio `tools/list` = 23;
- no secrets/private endpoints/raw stderr/local workstation paths in tracked files;
- build includes both JSON templates;
- test hash remains unchanged.

Final acceptance requires independent source audit. A blocked Station executor/auditor route must be recorded and must not be misrepresented as PASS.
