# ADR-002: Demo OAuth Compatibility and Pseudonymous Test Identity

**Status:** Accepted
**Date:** 2026-08-09
**Authority:** Operator/Architect
**WorkItem:** WI-00047
**Implementation state:** Source, deterministic, hosted-CI, and live Railway protocol gates pass; real Claude Custom Connector UI acceptance and final sign-off remain.

## Context

The Railway demo currently protects `/mcp`, `/sse`, and `/messages` with one optional static `TUBE_BRIDGE_AUTH_KEY`. This works for clients that can attach an arbitrary `Authorization: Bearer ...` header. Pi is currently verified through that path. Claude Code CLI supports static headers but its existing local `tube-bridge` entry is stale (`/sse` with no header) and is not current acceptance evidence; it must be corrected separately to `/mcp` with the existing key.

Claude's web **Add custom connector** form accepts a remote MCP URL and standard OAuth client settings, but it has no field for an arbitrary static Bearer header. Its unauthenticated request to the current Railway `/mcp` receives `401`, while OAuth protected-resource and authorization-server discovery also receive `401`. The same deployment was independently proven healthy through an authenticated Pi MCP client, so this is an auth-protocol compatibility gap rather than an MCP or Railway failure.

The disposable demo also needs to distinguish Operator activity from external tester activity without adding user accounts, durable profiles, raw identity logs, billing, or SaaS infrastructure.

## Decision

### 1. Add an optional OAuth compatibility adapter for HTTP deployments

When `TUBE_BRIDGE_OAUTH_INVITES_JSON`, `TUBE_BRIDGE_OAUTH_SIGNING_KEY`, and `TUBE_BRIDGE_PUBLIC_BASE_URL` are configured, the HTTP app exposes:

- `/.well-known/oauth-protected-resource`
- `/.well-known/oauth-protected-resource/mcp`
- `/.well-known/oauth-authorization-server`
- `/oauth/register`
- `/oauth/authorize` (`GET` and form `POST`)
- `/oauth/token`

The adapter follows the current MCP HTTP authorization requirements for OAuth Authorization Code, mandatory PKCE `S256`, RFC 8414 authorization-server metadata, RFC 9728 protected-resource metadata, RFC 8707 resource indicators, and RFC 9207 authorization-server issuer identification. It also implements RFC 7591 dynamic client registration **only as a deprecated compatibility path for Claude clients that still use DCR**. MCP 2026-07-28 prefers Client ID Metadata Documents; ADR-002 does not present DCR as the preferred general integration model and does not add a CIMD hosting service.

The adapter is optional and deployment-level. It does not affect stdio. A self-hosted deployment with no OAuth variables retains its existing behavior.

`TUBE_BRIDGE_PUBLIC_BASE_URL` is the sole canonical authority for OAuth URLs. It must be one HTTPS origin with no path, query, fragment, userinfo, or wildcard. The issuer is that exact origin and the protected resource/audience is exactly `<origin>/mcp`; request `Host`, `Forwarded`, and `X-Forwarded-*` values are never used to construct security metadata. If any OAuth variable is present while the complete configuration is absent or invalid, app creation fails closed instead of silently disabling OAuth.

The signing key must contain at least 32 bytes of high-entropy material. Invite configuration is bounded to 64 unique records. Each record requires a unique opaque ID matching `^[A-Za-z0-9_-]{1,64}$`, role `operator` or `tester`, and a unique lowercase 64-hex SHA-256 digest. Unknown roles, duplicate IDs/digests, malformed JSON, plaintext-code fields, or oversized configuration fail startup.

### 2. Dynamic clients remain public; token issuance requires an invite

Claude may dynamically register a public OAuth client. The registration response returns a stateless HMAC-authenticated client identifier containing the exact registered redirect URI set. Redirects must be HTTPS, except loopback HTTP callbacks used by local MCP clients. Authorization validates exact redirect URI equality against the signed registration; arbitrary prefix matching and open redirects are forbidden.

Dynamic registration alone grants no MCP access. Registration accepts only `application/json` bodies no larger than 16 KiB, one to eight unique redirect URIs, at most 2,048 characters per URI, and an optional client name of at most 128 characters. Redirect URIs must be HTTPS or loopback HTTP (`127.0.0.0/8`, `[::1]`, or case-insensitive `localhost`) with no userinfo, fragment, wildcard host, control character, leading/trailing whitespace, or non-loopback HTTP target. Query strings and explicit ports are allowed.

Redirect strings are **not canonicalized, decoded, trimmed, case-folded, or reserialized**. Duplicate detection uses exact string equality. The exact original strings are integrity-bound into the stateless client identifier, and authorize/token `redirect_uri` values must be byte-for-byte equal to one registered string. Thus case, percent-encoding, default-port, path, query, or trailing-slash differences fail unless that exact variant was separately registered.

Authorization and token requests must each contain RFC 8707 `resource` exactly equal to the canonical `<origin>/mcp`; the value is bound into pending authorization state and the one-time code. Missing, duplicate, mismatched, noncanonical, or alternate-resource values fail closed.

Authorization-server metadata advertises `authorization_response_iss_parameter_supported: true`. Every successful authorization redirect includes RFC 9207 `iss` exactly equal to the configured issuer, alongside `code` and the unchanged client `state`; error redirects, when safe to emit after exact redirect validation, also include the same issuer. Token exchange rejects a code whose issuer binding differs from current configuration.

The authorization page requires a deployment-issued invite code. Invite codes are configured only as SHA-256 digests in `TUBE_BRIDGE_OAUTH_INVITES_JSON`; plaintext codes are never stored by the application, committed, logged, or returned after provisioning. Authorization form/request bodies are limited to 16 KiB and wrong/unknown invite responses are generic.

The authorization form is the minimum browser interaction required by OAuth. It is not a product dashboard, account portal, signup flow, or managed identity service.

### 3. Invite records provide pseudonymous roles

Each configured invite record has:

- an opaque deployment-local identifier,
- `role: operator | tester`,
- a SHA-256 digest of a high-entropy invite code.

Successful authorization places only a keyed opaque subject and role into the access-token claims. The application does not persist names, emails, IP-to-subject mappings, or plaintext invite codes.

Separate invite records allow the process to distinguish our own requests from external testers and to count unique tester subjects without publishing those identifiers.

### 4. Codes and tokens are bounded

- Authorization requests and authorization codes are process-memory only, expire after five minutes, and are single-use.
- PKCE `S256` is mandatory at authorize and token exchange.
- Access tokens are HMAC-authenticated, audience-bound to the canonical `/mcp` resource, and expire after eight hours.
- No refresh tokens are issued. Reauthorization after expiry or signing-key rotation is acceptable for a disposable test surface.
- Access tokens, invite codes, authorization codes, client registrations, and subject identifiers must not appear in application logs or `/health`.

### 5. Preserve existing Bearer compatibility

`TUBE_BRIDGE_AUTH_KEY` remains valid and is classified as the `operator` role. Pi requires no migration. Claude Code CLI can use the same mechanism after its stale local entry is corrected to `/mcp` with the header; ADR-002 does not claim that correction is already applied. OAuth Bearer access tokens are accepted alongside the existing static Bearer key.

If neither static Bearer nor OAuth is configured, self-hosted HTTP remains open as before. If either is configured, protected MCP routes remain fail-closed.

Unauthenticated protected-resource responses include a standards-compatible `WWW-Authenticate` challenge pointing at protected-resource metadata.

### 6. Keep quota identity unchanged

ADR-001 remains authoritative: exactly five attempted Data API operations per Railway-observed IP during the process lifetime. OAuth roles do **not** bypass, reset, multiply, or replace that allowance.

OAuth identity is a separate observability dimension. It must not be used as a fallback when Railway client-IP extraction fails.

### 7. Aggregate-only auth observability

`/health` remains public and adds only process-memory aggregates:

- OAuth enabled/disabled,
- Operator protected-request count,
- Tester protected-request count,
- unique OAuth subject count.

One request is counted only after successful authentication of a protected HTTP route and immediately before route dispatch. Static Bearer requests count as Operator; OAuth requests use the token role. `/health`, discovery, registration, authorization, token exchange, unknown routes, and failed authentication do not increment counters. Each authenticated `/mcp`, `/sse`, or `/messages` HTTP request increments once; unique OAuth subjects are counted only on their first successful protected request during the current process. The static Bearer has no OAuth subject and does not increase the unique-subject count.

It exposes no invite IDs, client IDs, subject values, tokens, authorization codes, redirect URIs, or IP addresses. Existing demo quota aggregates remain unchanged.

## Alternatives Considered

| Alternative | Disposition |
|---|---|
| Remove `TUBE_BRIDGE_AUTH_KEY` and make `/mcp` public | Rejected: restores connector compatibility by discarding access control and tester distinction. |
| Paste `TUBE_BRIDGE_AUTH_KEY` into Claude's OAuth Client Secret field | Rejected: static Bearer and OAuth client authentication are different protocols. |
| Add accounts, email login, or a hosted identity database | Rejected: outside the disposable-demo boundary and unnecessary for test identity. |
| Use only fixed confidential OAuth clients | Rejected for Claude web interoperability: callback registration is client-specific and dynamic registration is the standard low-friction MCP path. |
| Treat every dynamically registered client as authorized | Rejected: registration is not proof of invite possession. |
| Change the five-operation allowance to per OAuth subject | Rejected: conflicts with accepted ADR-001 and is not required to distinguish traffic. |
| Persist OAuth sessions/clients/tokens in Railway volume | Rejected: conflicts with no-volume/no-backup disposable-demo design. |

## Consequences

### Positive

- The Railway MCP exposes the native OAuth protocol flow required for Claude Custom Connector compatibility; real Claude UI acceptance remains a separate gate.
- Pi and header-capable clients continue using the existing static Bearer key.
- Operator and external tester traffic are distinguishable through privacy-preserving aggregates.
- Unique invite codes can be issued and revoked by changing Railway configuration without adding accounts.
- No new database, external identity vendor, durable volume, or package dependency is required.

### Negative

- Invite entry must be repeated after access-token expiry or deployment signing-key rotation.
- A process restart invalidates in-flight authorization requests/codes.
- This is intentionally a small deployment-level authorization server, not a general-purpose identity platform.
- Public dynamic registration creates inert client IDs; possession of a valid invite remains the access boundary.

## Security and Acceptance Gates

Implementation is not accepted until deterministic frozen tests prove:

1. both metadata documents advertise only the canonical HTTPS endpoints, PKCE `S256`, and RFC 9207 authorization-response issuer support;
2. DCR rejects missing, malformed, non-HTTPS/non-loopback, exact-duplicate, whitespace/control-bearing, or oversized redirect registrations; enforces the documented 16-KiB/8-URI/2,048-character/128-character bounds; and preserves registered URI strings without normalization;
3. authorization rejects unknown/tampered clients, redirect mismatch, missing/duplicate/wrong RFC 8707 resource, absent/non-S256 PKCE, expired request state, and wrong invite codes; successful redirects include exact RFC 9207 `iss`, `code`, and unchanged `state`;
4. token exchange enforces one-time code use, exact client/redirect/resource binding, PKCE, expiry, and audience;
5. access-token tampering, wrong audience, and expiry fail closed;
6. existing static Bearer, auth-disabled self-host, `/health`, `/mcp`, `/sse`, and `/messages` contracts regress neither behavior nor scope;
7. auth metrics are aggregate-only and quota remains IP-bound;
8. canonical issuer/resource URLs come only from valid `TUBE_BRIDGE_PUBLIC_BASE_URL`, and partial/malformed OAuth/invite configuration fails startup;
9. exact aggregate metric counting semantics pass without exposing a client, subject, invite, redirect, token, code, or IP;
10. no secret or raw identity appears in source, response errors, health, or application logs;
11. an independent source audit and live Railway/Claude-compatible OAuth handshake pass.

## Sources

- MCP authorization specification: <https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization>
- OAuth Resource Indicators, RFC 8707
- OAuth Authorization Server Issuer Identification, RFC 9207
- OAuth Authorization Server Metadata, RFC 8414
- OAuth Dynamic Client Registration, RFC 7591
- OAuth Protected Resource Metadata, RFC 9728
- OAuth PKCE, RFC 7636 / OAuth 2.1 profile
- `tube_bridge/transport.py` — current static Bearer routing
- `tube_bridge/demo_policy.py` — accepted IP-only demo allowance
- ADR-001 — accepted quota, privacy, and disposable-demo boundaries
