# WI-00057 Claude DCR Refresh-Metadata Compatibility Addendum

## Trigger

Real browser Claude Custom Connector reached the deployed OAuth server but received `POST /oauth/register = 400` (support reference `ofid_e69793e5d46c4cfd`). Railway HTTP evidence shows discovery `200`, authorization-server metadata `200`, then DCR `400`.

The locally installed Anthropic/MCP OAuth client constructs public-client registration metadata with:

```json
{
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none"
}
```

ADR-002 intentionally issues no refresh token and advertises only `authorization_code`. The compatibility defect is registration parsing: `tube_bridge/oauth.py` currently rejects the standard Claude metadata before authorization can begin.

## Bounded Decision

- Accept exactly either `grant_types: ["authorization_code"]` or Claude's ordered `grant_types: ["authorization_code", "refresh_token"]` at DCR.
- Normalize the registration response to the server's actual supported grant list: `["authorization_code"]`.
- Continue to advertise only `authorization_code`, issue no refresh token, and reject refresh-only, reordered, duplicated, or unrelated grant lists.
- Do not change token lifetime, PKCE, invite roles, redirect validation, issuer/resource binding, static Bearer, IP quota, or product boundary.

## Acceptance

1. Separate deterministic test file is RED against current source.
2. Independent test-contract audit PASS and SHA-256 freeze occur before source modification.
3. Minimal DCR parser change makes addendum and cumulative suite GREEN without modifying any prior frozen test.
4. Independent source audit, hosted CI and Railway redeploy pass.
5. Real browser Claude proceeds past registration to the invite authorization page.
