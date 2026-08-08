# WI-00029 — Disposable Railway Demo Hardening Plan

**Status:** Proposed for independent review before tests are frozen  
**Method:** frozen-test TDD (`plan_tests → freeze_hash → implement → verify → gate → persist`)  
**Product boundary:** Railway try-before-install demo only. The published self-hosted core remains unrestricted and persistent.

## 1. Goal

Harden the Railway demo so that it:

1. permits exactly five attempted official YouTube Data API v3 operations per observed client IP during the current process lifetime;
2. rejects the sixth and later operations with a stable structured MCP error;
3. keeps the allowance entirely in process memory, with no time reset and a reset only when the process restarts;
4. never stores raw client IPs or allowance counters in SQLite/files;
5. deletes every corpus created in demo mode no later than ten minutes after creation;
6. preserves unrestricted, persistent self-hosted behavior when demo mode is disabled.

## 2. Non-goals

- Accounts, sessions, cookies, billing, SaaS, or managed hosting.
- Durable or cross-replica rate limits.
- A global allowance shared by multiple Railway processes.
- Durable IP hashes or raw-IP logging.
- Changes to the 16-tool public MCP catalog.
- Changes to self-hosted corpus retention.
- Grabbit integration, browser extensions, or a product gateway.
- Live YouTube, Data API credentials, proxy calls, or embedding-model downloads in deterministic tests.

## 3. Fixed contracts

### 3.1 Demo mode

- Enabled only by `TUBE_BRIDGE_DEMO_MODE=1`.
- Disabled by default in PyPI, source, stdio, and ordinary Docker use.
- Demo mode requires HTTP transport. Starting demo mode under stdio fails closed with a clear configuration error.

### 3.2 Client identity

- ASGI transport extracts one observed client IP for `/mcp`, `/sse`, and `/messages`.
- Proxy headers are trusted only when the explicit demo proxy setting is enabled.
- `X-Forwarded-For` is interpreted from the right using a configured trusted-proxy-hop count; user-controlled prefix values cannot change the selected address.
- Values are parsed and normalized with `ipaddress.ip_address`; malformed or missing identity fails closed for Data API operations.
- The selected IP is propagated through a `ContextVar`. A throwaway spike proved the context survives MCP SDK stateless task creation and `asyncio.to_thread` propagation.
- The quota map uses a per-process random keyed digest, not raw IP strings. No raw IP or digest is emitted in logs or health responses.

### 3.3 Data API allowance

- Enforcement occurs immediately before each actual `urllib.request.urlopen` attempt in `tube_bridge/youtube/api.py::api_call`.
- Calls that do not reach `api_call` consume nothing: cache hits, yt-dlp, transcript API, local corpus operations, help, and failed missing-key validation.
- Attempted Data API requests consume allowance even when Google/network later returns an error or quota exhaustion.
- Multi-request tools consume once per actual official API operation. `youtube_search_channels` may consume two operations (search plus enrichment).
- A dedicated policy exception must not be swallowed by fallback or enrichment handlers.
- Updates are atomic under concurrent thread execution.
- Limit is hard-coded to five for demo mode. It has no clock and therefore no time reset.
- Process restart creates a new random salt and empty counter map.

### 3.4 Structured failure

MCP response for exhausted allowance is stable and contains no IP:

```json
{
  "error": "demo_data_api_limit_exceeded",
  "message": "Disposable demo allowance exhausted for this process lifetime.",
  "limit": 5,
  "reset": "process_restart"
}
```

Missing identity in demo mode uses `demo_client_identity_unavailable` and also fails closed.

### 3.5 Corpus expiry

- Add nullable `expires_at REAL` to the `corpora` table using an idempotent migration.
- Self-hosted corpus rows always use `expires_at = NULL` and are never TTL-deleted.
- Demo corpus creation stores `expires_at = created_at + 600` in the same committed row.
- A process-local expiry worker waits for the nearest database deadline and deletes at that deadline.
- Creating a corpus wakes/reschedules the worker.
- Startup reconciliation assigns/deletes legacy demo rows and purges rows already past deadline.
- Corpus list/add/search paths purge expired rows before returning or mutating data, so expired corpora cannot remain observable if a timer is delayed.
- Deletion removes the corpus row, added-video rows, chunks, and per-corpus sqlite-vec table transactionally.
- Shutdown stops the worker without deleting self-hosted data.

### 3.6 Minimal observability and privacy

`/health` may expose only aggregate demo policy state:

- demo enabled/disabled;
- fixed Data API limit (`5`);
- aggregate allowed/rejected operation counts;
- number of in-memory client buckets;
- corpus TTL (`600` seconds).

No IP, digest, corpus content, auth value, or credential is exposed. Uvicorn application access logging is disabled in demo mode to avoid app-level raw-IP logging.

## 4. Planned files

### New source modules

- `tube_bridge/demo_policy.py`
  - configuration checks;
  - IP extraction/normalization and request `ContextVar`;
  - random-digest, thread-safe five-operation allowance;
  - structured policy exceptions;
  - aggregate metrics.
- `tube_bridge/demo_ttl.py`
  - startup reconciliation;
  - nearest-deadline worker;
  - wake/stop lifecycle.

### Existing source changes

- `tube_bridge/transport.py` — bind request identity, start/stop TTL worker, health aggregates.
- `tube_bridge/youtube/api.py` — consume immediately before official network attempt; preserve policy exceptions.
- `tube_bridge/server.py` — serialize structured demo policy errors.
- `tube_bridge/corpus.py` — `expires_at` migration, expiry queries/deletion, demo-only expiry assignment and pre-operation purge.
- `tube_bridge/cli.py` — reject demo stdio and disable application access logging in demo HTTP mode.
- `README.md` and bounded planning/status docs — replace “target not active” language only after deployed evidence passes.

### New deterministic tests only

Old WI-00028 frozen files remain byte-identical. New tests:

- `tests/test_demo_policy.py`
- `tests/test_demo_transport_context.py`
- `tests/test_demo_ttl.py`
- `tests/test_demo_integration.py`

## 5. RED contract matrix

### Allowance and privacy

1. Demo disabled: no identity required, no operation limit.
2. Demo enabled: first five API attempts for one IP pass; sixth raises the exact structured error.
3. Different IP receives an independent five-operation allowance.
4. No time-based reset exists, even when a fake wall clock advances.
5. New policy/process instance starts empty.
6. Ten concurrent attempts yield exactly five allowed and five rejected.
7. Internal counter keys do not contain the raw IPv4/IPv6 value.
8. Missing/malformed client identity fails closed.
9. A missing YouTube API key does not consume allowance.
10. API/network/Google failures after an attempted request do consume allowance.
11. Keyless/cache/transcript/corpus/help paths consume nothing.
12. Multi-operation channel search cannot swallow the sixth-operation rejection.

### Transport context

1. Direct ASGI client fallback is normalized.
2. Trusted-hop XFF selection resists spoofed prefix values.
3. Proxy headers are ignored outside explicit trusted-proxy mode.
4. Context reaches a real stateless MCP tool handler.
5. Context survives `asyncio.to_thread` into `api_call`.
6. SSE identity binds to the original SSE connection; `/messages` cannot replace it.
7. Health output contains aggregate values only.

### Corpus TTL

1. Migration is idempotent on existing four-column databases.
2. Self-hosted create stores no expiration.
3. Demo create stores a deadline exactly 600 seconds after creation.
4. Purge before 600 seconds keeps all rows/vector tables.
5. Purge at the deadline deletes corpus, chunks, added-video rows, and vector table.
6. Startup reconciliation deletes expired legacy demo rows.
7. Restart reconstruction uses database deadlines, not prior process timers.
8. List/add/search cannot observe or mutate an expired corpus.
9. Manual delete cancels/reschedules worker state safely.
10. Worker shutdown is bounded and leaves self-hosted corpora untouched.

### Configuration and regression

1. Demo mode plus stdio fails closed.
2. HTTP demo mode disables app access logging.
3. Existing 16-tool catalog and all WI-00028 tests remain green.
4. Deterministic suite performs no live YouTube, proxy, Data API, Railway, or embedding-model operation.
5. Running tests leaves the git tree and build directories unchanged.

## 6. Freeze and implementation sequence

1. Add only the four new test files and test-local fixtures.
2. Run the complete suite and demonstrate only expected RED failures.
3. Run independent test-contract audit.
4. Compute and persist a Python SHA-256 manifest; verify old WI-00028 frozen files are unchanged.
5. Implement in bounded packs:
   - Pack A: request identity + in-memory allowance + API boundary;
   - Pack B: corpus schema/deadlines + worker lifecycle;
   - Pack C: transport/CLI health/privacy wiring;
   - Pack D: deployment/docs notice.
6. Re-run frozen hash and full deterministic suite after every pack.
7. Run independent source/conformance audit.

## 7. Railway acceptance

After local acceptance:

1. Set demo-only environment configuration on the Railway service; do not change self-hosted defaults.
2. Confirm no Railway persistent volume/backups are attached.
3. Deploy the accepted commit.
4. From one external client identity, verify five real Data API operations are allowed and the sixth is rejected.
5. Repeat requests with spoofed XFF prefixes to prove they cannot obtain fresh allowance.
6. Restart the process and verify allowance resets.
7. Create a disposable corpus and verify it is absent by the ten-minute deadline.
8. Verify `/health` shows aggregates only and no raw IP appears in application logs.
9. Record deployment SHA, Railway receipt, live evidence, and final independent audit.

## 8. Completion criterion

WI-00029 is complete only when frozen deterministic tests, hash verification, independent audit, deployed Railway checks, quota behavior, TTL behavior, privacy checks, and bounded documentation all pass. Core v1.0.2 publication remains unchanged.
