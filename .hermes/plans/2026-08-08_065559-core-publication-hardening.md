# Core Publication Hardening Implementation Plan

> **For Hermes:** Use Station `methodology.tdd_frozen_tests` and bounded executor packs to implement this plan task-by-task. Do not alter production code before the defect-driving tests have produced the expected RED results and the complete test tree hash has been frozen.

**Goal:** Produce an independently audited release candidate of the self-hosted tube-bridge core that is deterministically tested, installable from wheel/sdist, runnable through a packaged CLI, reproducible in CI/Docker, and honest about publication state.

**Architecture:** Keep the 16-tool MCP behavior stable. Consolidate tool metadata so registration and help cannot drift, move the console entrypoint into the installed package, close every SQLite connection on all public-operation paths, and separate public dependency compatibility bounds from an exact release-build lock. Verify the installed artifact and Docker container through a real MCP `initialize` + `tools/list` handshake, not only `/health`.

**Tech Stack:** Python 3.12+, MCP 1.28.x, pytest/pytest-asyncio, Starlette/Uvicorn, sqlite3/sqlite-vec, `build`, `twine`, GitHub Actions, Docker.

---

## Authority and Scope

- Station WorkItem: `WI-00028`
- Lifecycle: `methodology.tdd_frozen_tests`
- Product authority: `PROJECT_VISION.md`
- Acceptance matrix: `docs/planning/PUBLICATION_READINESS.md`, Core C1/C2/C3/C5
- Demo hardening remains isolated in `WI-00029`.

### Included

1. Frozen deterministic test contract for the 16 tools, dispatch, packaged CLI, transport/auth, SQLite connection lifecycle, build metadata, and installed-artifact behavior.
2. One authoritative tool catalog used by MCP registration/help, or an equivalently drift-proof minimal design.
3. Packaged synchronous CLI entrypoint that calls async runtime through `asyncio.run()`.
4. Wheel/sdist metadata, build, `twine check`, and clean-environment install verification.
5. Bounded dependency compatibility, plus an exact reproducible dependency set for release CI/Docker.
6. GitHub Actions deterministic tests and package verification.
7. Docker build and real MCP handshake (`initialize`, `tools/list`) with auth checks.
8. Narrow SQLite resource-safety fix: every opened cache/corpus connection closes on success, miss, early return, and exception.

### Excluded

- Railway deployment/configuration, demo Google project, demo 5-operation enforcement, demo corpus TTL (`WI-00029`).
- New MCP tools or behavior changes to search, transcript, corpus ranking/chunking, proxy, quota, or embedding algorithms.
- SaaS/accounts, browser extension, Grabbit integration.
- Git push, tag, GitHub Release, PyPI upload, or Docker registry push without explicit Operator approval.
- Broad async/threading refactors beyond defects required by frozen tests.

## Fixed Decisions

- Tool baseline: exactly 16 unique registered names.
- Default automated tests make no live YouTube/proxy/Data API calls and do not download embedding models.
- `test_tools.py` remains optional manual live smoke evidence, never the CI gate.
- Installed CLI must live inside `tube_bridge`, not depend on root `server.py` being packaged.
- Public package metadata uses a tested bounded MCP compatibility range; initial target is MCP 1.28.x because the code imports low-level 1.28.1 transport modules.
- Release CI/Docker additionally use an exact lock/constraints artifact. A broad `<2` cap alone is not considered reproducible.
- PyPI distribution name `tube-bridge` returned 404 on 2026-08-08; availability must be rechecked immediately before upload because a lookup does not reserve the name.

---

## Frozen Test Matrix

### Tool contract and dispatch

Expected test files:

- `tests/test_tool_contract.py`
- `tests/test_tool_dispatch.py`

Required assertions:

1. `list_tools()` returns exactly 16 unique names and valid object schemas.
2. Help tool names equal the registered names; no dead numeric/list duplicate remains.
3. Package description/docstring makes no 10/11-tool claim.
4. All 16 names dispatch to the expected public operation with correct required/default arguments under mocked upstreams.
5. Unknown tool and expected runtime/value errors return controlled MCP text responses.
6. Existing key classification remains 13 zero-setup / 3 Data API required.

Passing characterization tests may capture already-shipped behavior. Defect-driving help/docstring tests must produce RED before implementation.

### CLI and distribution contract

Expected test files:

- `tests/test_cli_contract.py`
- `tests/test_distribution_contract.py`

Required assertions:

1. Project script resolves to an importable synchronous callable inside `tube_bridge`.
2. Built wheel does not require root checkout modules.
3. In a clean virtual environment, installing the wheel succeeds.
4. `tube-bridge --help` exits 0 without `coroutine was never awaited` or import errors.
5. Importing `tube_bridge` from outside the checkout succeeds.
6. `python -m build` produces wheel and sdist; `twine check` passes.

Build/install tests may be tagged `distribution` and run in the release verification job rather than on every fast unit invocation.

### Transport and container contract

Expected test files/utilities:

- `tests/test_transport_contract.py`
- `scripts/mcp_smoke.py` (only if a reusable network smoke client is needed)

Required assertions:

1. `/health` is public and reports 16 tools.
2. Protected remote routes reject missing/invalid Bearer auth when configured.
3. Streamable HTTP MCP `initialize` succeeds.
4. `tools/list` over `/mcp` returns exactly 16 names.
5. Docker acceptance repeats health, unauthorized request, authorized `initialize`, and authorized `tools/list` against the running container.
6. Container exits cleanly after smoke verification.

### SQLite resource lifecycle

Expected test file:

- `tests/test_sqlite_lifecycle.py`

Required assertions using temporary paths and connection spies/proxies:

1. Cache get hit/miss and set operations close every opened connection.
2. Corpus create/list/delete and representative early-return/error paths close every opened connection.
3. Commit/rollback semantics remain correct.
4. Tests do not initialize/download the embedding model.

The implementation must use an explicit close lifecycle (`try/finally`, `contextlib.closing`, or a custom context manager). Relying only on `with sqlite3.connect(...)` is insufficient because that context manager does not close the connection.

### Dependency/release contract

Expected assertions:

1. `pyproject.toml` has a build backend, README, license, URLs, package discovery, dev test dependencies, and bounded critical runtime dependencies.
2. MCP compatibility does not exceed the tested range silently.
3. Exact release lock/constraints is consumed by Docker/release verification.
4. No credential value is committed or embedded in wheel/image.

---

## Execution Tasks

### Task 1: Record baseline and PyPI/dependency preflight

**Files:**
- Update evidence only; no production files.

**Steps:**
1. Record Python, pip, MCP, Docker, and OS versions.
2. Record current PyPI `tube-bridge` lookup (404 observed; recheck).
3. Run current smoke/test commands without modifying code.
4. Capture current wheel/build failure or missing tooling as baseline evidence.
5. Do not claim CI/package acceptance from this baseline.

### Task 2: Write tool/help RED tests

**Files:**
- Create `tests/test_tool_contract.py`
- Create `tests/test_tool_dispatch.py`

**Steps:**
1. Write the smallest help/registry equality test.
2. Run it and confirm expected RED from missing corpus entries/dead metadata.
3. Add characterization coverage for all 16 registered names and schemas.
4. Add mocked dispatch matrix without live network.
5. Record RED/pass classification per test.

### Task 3: Write CLI/distribution RED tests

**Files:**
- Create `tests/test_cli_contract.py`
- Create `tests/test_distribution_contract.py`

**Steps:**
1. Assert project script resolves to a packaged synchronous callable.
2. Confirm RED against current `server:main` async/root-module target.
3. Add build/clean-install/`--help` release tests.
4. Keep distribution tests selectable via pytest marker.

### Task 4: Write SQLite lifecycle RED tests

**Files:**
- Create `tests/test_sqlite_lifecycle.py`

**Steps:**
1. Add connection spy around public cache operations.
2. Confirm expected RED because current operations never call `close()`.
3. Add corpus success/early-return/error lifecycle cases without model download.
4. Assert exactly one close for each successfully opened connection.

### Task 5: Write transport/container contract tests

**Files:**
- Create `tests/test_transport_contract.py`
- Optionally create `scripts/mcp_smoke.py`

**Steps:**
1. Test health and auth routing deterministically.
2. Define real MCP initialize/tools-list smoke behavior.
3. Confirm current tests either characterize working source transport or RED on missing package/container integration.
4. Do not use live YouTube.

### Task 6: Freeze test tree

**Files:**
- Entire `tests/` tree plus any test-only smoke utility included by lifecycle policy.

**Steps:**
1. Run the complete deterministic suite and record expected RED failures separately from baseline passes.
2. Reject syntax/import/setup errors as invalid RED; fix test code only until failures express missing behavior.
3. Execute Station `runner.compute_test_hash` in lifecycle `freeze_hash` phase.
4. Persist hash receipt.
5. No later test edits without explicit thaw/re-freeze and audit trail.

### Task 7: Minimal tool catalog and CLI implementation

**Files likely modified/created:**
- Modify `tube_bridge/server.py`
- Modify `tube_bridge/__init__.py`
- Create `tube_bridge/cli.py`
- Modify root `server.py` only as a compatibility launcher if required

**Steps:**
1. Implement only enough catalog/help change for frozen tests.
2. Run focused test, then full fast suite.
3. Add synchronous packaged `main()` calling an async runner via `asyncio.run()`.
4. Preserve root launcher compatibility.
5. Run focused CLI tests, then full suite.

### Task 8: Close SQLite connections

**Files:**
- Modify `tube_bridge/cache.py`
- Modify `tube_bridge/corpus.py`

**Steps:**
1. Introduce one explicit connection lifecycle helper per minimal design.
2. Migrate cache operations; run focused lifecycle tests.
3. Migrate corpus operations without changing queries/schema/algorithms.
4. Run focused and full deterministic tests.

### Task 9: Package and dependency hardening

**Files likely modified/created:**
- Modify `pyproject.toml`
- Add exact release constraints/lock artifact
- Modify `.gitignore` only if release artifacts need exclusion

**Steps:**
1. Add build backend/package discovery and metadata grounded in existing repository facts.
2. Set tested MCP 1.28.x compatibility bound.
3. Generate exact release dependency set; do not hand-invent unverified transitive versions.
4. Build wheel/sdist and run `twine check`.
5. Install wheel in clean environment outside checkout.
6. Run CLI/import smoke.

### Task 10: CI and Docker release rehearsal

**Files likely modified/created:**
- Create `.github/workflows/ci.yml`
- Modify `Dockerfile`
- Reuse/create `scripts/mcp_smoke.py`

**Steps:**
1. Add deterministic test/package jobs for Python 3.12 and a bounded compatibility job where supported.
2. Build Docker image from package installation path using exact release dependencies.
3. Start container with a temporary auth value.
4. Verify health, unauthorized `/mcp`, authorized initialize, and tools/list=16.
5. Inspect image/repository inputs for accidental credentials.
6. Do not push image or repository.

### Task 11: Verification and independent audit

**Commands/evidence:**

```bash
pytest tests/ -q
python -m build
python -m twine check dist/*
# clean-venv wheel install and tube-bridge --help
# docker build/run plus scripts/mcp_smoke.py
```

**Steps:**
1. Station verifies frozen test hash unchanged.
2. Run fast tests, distribution tests, clean install, and Docker MCP handshake.
3. Record command outputs and environment versions.
4. Independent auditor checks scope, frozen hash, dependency policy, artifact install, SQLite closure, MCP handshake, and publication-claim honesty.
5. Move `WI-00028` to `ready_for_gate` only on PASS. Actual publication remains a separate Operator gate.

---

## Final Acceptance Checklist

- [ ] Frozen test hash predates production changes and remains unchanged.
- [ ] Defect-driving tests were observed RED for the expected reasons.
- [ ] Deterministic suite passes without live YouTube/model download/credentials.
- [ ] Exactly 16 tool names agree across registry/help/package contract.
- [ ] Installed wheel CLI works outside checkout without coroutine warnings.
- [ ] Wheel and sdist build; `twine check` passes; clean install passes.
- [ ] Cache/corpus connections close on success, miss, early return, and exception.
- [ ] Dependency compatibility is bounded; release CI/Docker consume exact versions.
- [ ] Docker health, auth rejection, MCP initialize, and tools/list=16 all pass.
- [ ] CI workflow expresses the same commands locally verified.
- [ ] No source claim says PyPI/Docker/GitHub release already exists before publication.
- [ ] Independent audit PASS.
- [ ] No `WI-00029` demo behavior entered this scope.
