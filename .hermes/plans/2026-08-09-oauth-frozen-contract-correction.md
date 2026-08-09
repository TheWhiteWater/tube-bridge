# WI-00049 OAuth Frozen Contract Correction

**Parent:** WI-00047  
**Superseded manifest:** `.brainops/methodology/frozen-tests/frozen-20260809012157-test_oauth_contract.py.json`  
**Production source state:** `tube_bridge/oauth.py` absent; `tube_bridge/transport.py` byte-identical to `HEAD` before correction.

## Why correction is mandatory

The first post-freeze implementation attempt was not committed. Its targeted GREEN run exposed three defects in the frozen test harness rather than in ADR-002 behavior:

1. `test_authorize_requires_exact_redirect_state_resource_and_s256` required HTTP `400` for all invalid downstream authorization fields, while the later frozen RFC 9207 test correctly required a safe OAuth error redirect with `error`, unchanged `state`, and `iss` after client and exact redirect validation. Both expectations cannot hold for the same request class.
2. The authorization page correctly had to set a `Secure` CSRF cookie, but most flow helpers used `base_url="http://test"`. A conforming HTTP client must not return a Secure cookie over HTTP, making every successful frozen invite flow impossible.
3. `json.dumps(response.headers)` attempted to serialize `httpx.Headers`, which is not JSON serializable for any ASGI implementation. The privacy assertion intended to serialize header values, not require an impossible third-party object mutation.
4. After the first corrected refreeze reached deeper runtime branches, the installed `httpx.AsyncClient` rejected `data=[(key, value), ...]` with `RuntimeError: Attempted to send a sync request with an AsyncClient instance` before invoking ASGI. The duplicate-resource contract must encode the same ordered pairs explicitly as form content.

An independent pre-freeze audit had PASSed the old bytes but did not identify these internal contradictions. Production code must not be distorted to satisfy them.

## Exact permitted corrections

Only `tests/test_oauth_contract.py` may change:

- use HTTPS `https://test` as the local ASGI base so Secure-cookie behavior is real;
- require `400` only when the client/redirect cannot be trusted, and require RFC 9207 error redirects for invalid fields after exact redirect validation;
- serialize `dict(response.headers)` for the privacy check;
- encode ordered duplicate-resource form pairs with `urlencode(fields)` plus the form content type so the request reaches ASGI under the installed async client.

No security requirement, OAuth endpoint, bound, role, TTL, PKCE/resource/issuer rule, Bearer regression, quota rule, or production API may be removed or weakened.

## Gate

1. Confirm no production OAuth source/diff exists.
2. Apply only the three corrections above.
3. Re-run targeted and Station RED; collection must succeed, existing regressions pass, OAuth behavior remains RED.
4. Obtain an independent correction audit PASS.
5. Freeze a new SHA-256 manifest and explicitly mark the old manifest superseded in WI-00049/WI-00047 evidence.
6. Only then resume WI-00047 implementation from a source-clean state.
