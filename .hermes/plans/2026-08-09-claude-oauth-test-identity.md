# Claude OAuth Test Identity Implementation Plan

> **For Hermes:** Execute with strict frozen TDD. Production source starts only after deterministic RED, independent test-contract PASS, and Station SHA-256 freeze.

**Goal:** Add an optional MCP OAuth Authorization Code + PKCE adapter that lets Claude Custom Connector authenticate with deployment-issued invite codes and records aggregate operator/tester traffic while preserving static Bearer and ADR-001 IP quota behavior.

**Architecture:** Add one standard-library-only `tube_bridge/oauth.py` module. It owns validated environment configuration, RFC metadata, stateless signed DCR client IDs, memory-only authorization requests/codes, invite verification, signed eight-hour access tokens, and aggregate auth metrics. `tube_bridge/transport.py` routes the public OAuth endpoints, accepts either the existing static Bearer or an OAuth token on protected MCP routes, and keeps IP quota identity independent.

**Tech Stack:** Python 3.12+, Starlette ASGI responses/requests already installed, stdlib `hashlib`/`hmac`/`secrets`/`urllib.parse`/`json`, pytest/httpx. No new package or external identity service.

---

## Frozen Contract Matrix

### Configuration

- No OAuth variables: OAuth disabled; current self-host behavior unchanged.
- Any partial OAuth configuration: `create_app()` fails closed.
- Public base URL: HTTPS origin only, no path/query/fragment/userinfo/wildcard; canonical issuer is exact configured origin and resource is `<origin>/mcp`.
- Signing key: at least 32 UTF-8 bytes.
- Invite JSON: list of 1–64 records; unique ID/digest; ID regex; role enum; digest lowercase SHA-256; plaintext-code/unknown malformed record rejected.

### Discovery and challenge

- RFC 9728 root and `/mcp` metadata advertise exact resource/issuer.
- RFC 8414 metadata advertises authorize/token/register, code grant, `S256`, public clients, `mcp:tools`, and `authorization_response_iss_parameter_supported: true`.
- Successful authorization redirects include RFC 9207 `iss` exactly equal to configured issuer plus unchanged `state`; code issuer binding is checked at exchange.
- RFC 7591 DCR is tested and documented only as a deprecated Claude-compatibility path under MCP 2026-07-28, which prefers Client ID Metadata Documents.
- Authorization and token requests each require one RFC 8707 `resource` value exactly equal to the canonical `<origin>/mcp`; pending state and code bind it through exchange.
- Unauthenticated protected route returns 401 plus `WWW-Authenticate` resource metadata; discovery routes remain public.

### Dynamic registration

- JSON only, maximum 16 KiB.
- One to eight exact-unique redirect strings; each maximum 2,048 chars.
- HTTPS or loopback HTTP only; no whitespace/control/userinfo/fragment/wildcard.
- URI strings remain byte-for-byte unchanged; equivalent-but-different variants are distinct registrations.
- Optional client name maximum 128 chars; only public `none` token auth/code grant accepted.
- Signed client ID tampering fails.

### Authorization

- Exact registered redirect; code response with exact RFC 9207 issuer; state present/bounded and returned unchanged; exact canonical RFC 8707 resource; PKCE challenge is 43-char base64url and method exactly `S256`.
- GET creates five-minute pending request and CSRF cookie; response uses no-store/CSP and does not expose invite configuration.
- POST is form-only/max 16 KiB, validates request/CSRF/expiry, and returns generic failure for wrong invite.
- Correct unique invite binds opaque subject and operator/tester role to a five-minute authorization code.

### Token and protected access

- Form-only/max 16 KiB; authorization-code grant only.
- Code is single-use even after failed exchange.
- Exact client/redirect/resource binding and RFC 7636 verifier calculation.
- Access token is HMAC-authenticated, exact `/mcp` audience, role/opaque subject only, eight-hour expiry, no refresh token.
- Tampered, expired, wrong-audience tokens fail closed.
- Existing static Bearer remains operator access; invalid/wrong-scheme auth remains 401.

### Metrics/privacy/quota

- Increment once only for each successfully authenticated `/mcp`, `/sse`, or `/messages` HTTP request immediately before dispatch.
- Static Bearer increments operator only; OAuth uses token role and unique OAuth subject set.
- Public/OAuth/unknown/failed-auth requests do not increment.
- `/health` exposes only OAuth enabled + operator/tester counts + unique subject count.
- No client ID, invite ID/code/digest, token/code, subject, redirect, or IP appears in health/errors.
- OAuth does not alter `demo_policy.extract_client_ip()`, allowance buckets, or operation limit.

---

### Task 1: Freeze configuration and cryptographic contracts

**Files:**
- Create: `tests/test_oauth_contract.py`
- Planned source: `tube_bridge/oauth.py`

1. Write deterministic tests for disabled/partial/invalid/valid configuration.
2. Write tests for client-ID and access-token signatures, expiry, audience, and tampering using injected clock/random values.
3. Import the wished-for OAuth module/API only inside test bodies or fixtures so pytest collects normally.
4. Run `python3 -m pytest tests/test_oauth_contract.py -q`; expect ordinary FAILED assertions/exceptions caused by missing OAuth behavior, never a collection error. Existing static-Bearer/IP regression tests in the file are expected to PASS during RED; the new OAuth contract set must fail and the command must exit nonzero.

### Task 2: Freeze ASGI discovery and DCR contracts

**Files:**
- Modify: `tests/test_oauth_contract.py`
- Planned source: `tube_bridge/oauth.py`, `tube_bridge/transport.py`

1. Add ASGI tests for metadata, 401 challenge, body/content-type limits, redirect validation, exact URI preservation and signed DCR client IDs.
2. Keep network fully local through `httpx.ASGITransport`; no Railway, Claude, YouTube, proxy, API key, or embedding download.
3. Re-run targeted tests and capture expected RED failures.

### Task 3: Freeze authorize/token/invite contracts

**Files:**
- Modify: `tests/test_oauth_contract.py`

1. Add deterministic GET/POST authorization tests with CSRF, state, exact RFC 8707 resource, PKCE and unique invite roles.
2. Add token tests for one-use codes, exact client/redirect/resource binding, verifier, signed claims, expiry/tampering/audience and no refresh token.
3. Add health privacy and exact metric semantics tests.
4. Add regression tests proving static Bearer and OAuth coexist and IP quota code remains unchanged.
5. Run targeted tests; pytest must collect normally and exit nonzero because the new OAuth behavior contracts fail. The static Bearer/IP regression cases must already PASS during RED and must remain green throughout implementation.

### Task 4: Independent test-contract audit and Station freeze

1. Run `methodology.test_contract_audit` against ADR-002, this plan, and `tests/test_oauth_contract.py`.
2. Require independent PASS.
3. Freeze the exact test file through Station `methodology/freeze-tests`; store the Python-aware SHA-256 manifest under `.brainops/methodology/frozen-tests/`.
4. Verify the frozen file byte hash before source work.

### Task 5: Implement the OAuth core minimally

**Files:**
- Create: `tube_bridge/oauth.py`

1. Implement `OAuthConfig`, `AuthPrincipal`, and `OAuthService` with injected clock/random hooks.
2. Implement strict configuration and redirect validation.
3. Implement public ASGI handlers for metadata, DCR, authorize GET/POST and token POST.
4. Implement HMAC client IDs/access tokens and memory-only pending/code state.
5. Run targeted tests until core tests turn GREEN; never change frozen tests.

### Task 6: Integrate transport auth and metrics

**Files:**
- Modify: `tube_bridge/transport.py`

1. Preserve `_get_auth_key()` and `_check_auth()` compatibility.
2. Add optional injected/default `OAuthService` to `create_app()`.
3. Route OAuth public endpoints before protected-route authentication.
4. Authenticate existing static Bearer or OAuth token; emit standards challenge on failure.
5. Record aggregate role metrics only on successful protected dispatch.
6. Keep `policy.bind_request_identity(scope)` unchanged around MCP/SSE handlers.
7. Run `tests/test_oauth_contract.py`, then complete suite.

### Task 7: Independent source audit and packaging verification

1. Run post-apply targeted OAuth tests and the full deterministic suite against the exact frozen hash.
2. Run wheel/sdist, `twine check`, clean install, stdio regression, Bearer MCP handshake and Docker runtime.
3. Only after those post-apply verification results exist, run independent conformance/source audit against the frozen manifest, ADR-002, new module, transport diff, and verification receipt.
4. Remediate findings only with separate frozen addenda if behavior contracts are missing.
5. Re-run post-remediation verification and audit as required; commit source only after a valid final PASS.

### Task 8: Synchronize public documentation

**Files:**
- Modify in maximum-three-file audit packs: `README.md`, `docs/constitution/01_SYSTEM_CONTEXT.md`, `docs/constitution/02_ARCHITECTURE.md`, `docs/constitution/05_NON_GOALS.md`, `docs/planning/MVP_SCOPE.md`, `docs/planning/PUBLICATION_READINESS.md`, `docs/planning/OPEN_QUESTIONS.md`, `docs/INDEX.md`, `PROJECT_VISION.md`.

1. Change planned claims to implemented only after source acceptance.
2. Document Claude connector URL, invite authorization behavior, static Bearer compatibility, eight-hour/no-refresh/restart semantics, aggregate metrics and unchanged IP quota.
3. Audit each pack independently; maximum three documents per audit.

### Task 9: Railway provisioning and live acceptance

1. Generate a high-entropy OAuth signing key plus separate high-entropy Operator and tester invite codes without printing them.
2. Store only signing key and invite-code digests in Railway variables; no plaintext invite in repository/log/Memory.
3. Put the Operator invite code in the local clipboard for the user; do not display it in chat/tool output.
4. Deploy accepted source and verify health, discovery, DCR, browser authorization, PKCE token exchange, OAuth MCP initialize/tools=16, existing Pi static Bearer, and aggregate role counts.
5. Enter Claude Custom Connector with name `tube-bridge`, URL `https://tube-bridge-production.up.railway.app/mcp`, OAuth fields blank; complete invite form and verify tool discovery.
6. Issue external tester invites separately when needed; each gets a unique digest/opaque subject.
7. Persist live receipt, final audit, WorkItem/lifecycle/TME status and handoff.

## Explicit Non-Goals

- No accounts, email login, public signup, profiles, durable sessions, database, volume, backup, billing, entitlement, OAuth vendor, Google/GitHub identity, admin dashboard, quota bypass, per-subject quota, or new MCP tools.
- No change to the 16-tool catalog, tool schemas, stdio, corpus TTL, Data API accounting boundary, Railway `X-Real-IP`, published PyPI `v1.0.2`, or existing static Bearer secret.
