"""Frozen RED contracts for WI-00047 Claude OAuth test identity.

Deterministic only: local ASGI, injected clock/token source, no Railway, Claude,
YouTube, proxy credentials, Data API secrets, or embedding downloads.
"""

import base64
from contextlib import asynccontextmanager
import hashlib
import importlib
import json
import re
from urllib.parse import parse_qs, urlparse

import httpx
import pytest


BASE = "https://demo.example"
RESOURCE = f"{BASE}/mcp"
OPERATOR_CODE = "operator-code-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
TESTER_CODE = "tester-code-0123456789-abcdefghijklmnopqrstuvwxyz"
SIGNING_KEY = "oauth-signing-key-material-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class Clock:
    def __init__(self, now=2_000_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


class TokenFactory:
    def __init__(self):
        self.count = 0

    def __call__(self, _nbytes=32):
        self.count += 1
        return f"deterministic-{self.count:04d}-" + ("x" * 48)


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _invites():
    return [
        {"id": "operator-main", "role": "operator", "secret_sha256": _digest(OPERATOR_CODE)},
        {"id": "tester-001", "role": "tester", "secret_sha256": _digest(TESTER_CODE)},
    ]


def _set_oauth_env(monkeypatch, *, base=BASE, signing=SIGNING_KEY, invites=None):
    monkeypatch.setenv("TUBE_BRIDGE_PUBLIC_BASE_URL", base)
    monkeypatch.setenv("TUBE_BRIDGE_OAUTH_SIGNING_KEY", signing)
    monkeypatch.setenv("TUBE_BRIDGE_OAUTH_INVITES_JSON", json.dumps(invites if invites is not None else _invites()))


def _clear_oauth_env(monkeypatch):
    for name in (
        "TUBE_BRIDGE_PUBLIC_BASE_URL",
        "TUBE_BRIDGE_OAUTH_SIGNING_KEY",
        "TUBE_BRIDGE_OAUTH_INVITES_JSON",
    ):
        monkeypatch.delenv(name, raising=False)


def _oauth_module():
    # Import inside tests so RED is an ordinary test failure, never collection failure.
    return importlib.import_module("tube_bridge.oauth")


def _service(monkeypatch, *, clock=None, base=BASE, signing=SIGNING_KEY, invites=None):
    _set_oauth_env(monkeypatch, base=base, signing=signing, invites=invites)
    oauth = _oauth_module()
    config = oauth.OAuthConfig.from_env()
    return oauth.OAuthService(
        config,
        clock=clock or Clock(),
        token_factory=TokenFactory(),
    )


def _app(monkeypatch, service=None):
    from tube_bridge.server import server
    from tube_bridge.transport import create_app
    return create_app(server, "127.0.0.1", 8080, oauth_service=service)


def _pkce(verifier="v" * 43):
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


async def _register(client, redirects=None, **extra):
    body = {
        "client_name": "Claude test connector",
        "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"] if redirects is None else redirects,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        **extra,
    }
    return await client.post("/oauth/register", json=body)


async def _authorization_request(client, client_id, redirect_uri, *, state="state-123", resource=RESOURCE, verifier="v" * 43):
    _, challenge = _pkce(verifier)
    response = await client.get("/oauth/authorize", params={
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "resource": resource,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    match = re.search(r'name="request_id" value="([^"]+)"', response.text)
    return response, match.group(1) if match else None


async def _complete_authorization(client, request_id, invite_code):
    return await client.post("/oauth/authorize", data={
        "request_id": request_id,
        "access_code": invite_code,
    }, follow_redirects=False)


async def _token_exchange(client, code, client_id, redirect_uri, verifier="v" * 43, resource=RESOURCE):
    return await client.post("/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
        "resource": resource,
    })


async def _oauth_flow(client, invite_code=TESTER_CODE, redirect_uri="https://claude.ai/api/mcp/auth_callback"):
    registered = await _register(client, [redirect_uri])
    assert registered.status_code == 201
    client_id = registered.json()["client_id"]
    authorized, request_id = await _authorization_request(client, client_id, redirect_uri)
    assert authorized.status_code == 200 and request_id
    callback = await _complete_authorization(client, request_id, invite_code)
    assert callback.status_code in (302, 303, 307)
    query = parse_qs(urlparse(callback.headers["location"]).query)
    token = await _token_exchange(client, query["code"][0], client_id, redirect_uri)
    assert token.status_code == 200
    return token.json(), query, client_id


# ---------------------------------------------------------------------------
# Configuration contracts
# ---------------------------------------------------------------------------


def test_oauth_disabled_only_when_all_three_variables_absent(monkeypatch):
    _clear_oauth_env(monkeypatch)
    oauth = _oauth_module()
    config = oauth.OAuthConfig.from_env()
    assert config.enabled is False


@pytest.mark.parametrize("present", [
    {"TUBE_BRIDGE_PUBLIC_BASE_URL": BASE},
    {"TUBE_BRIDGE_OAUTH_SIGNING_KEY": SIGNING_KEY},
    {"TUBE_BRIDGE_OAUTH_INVITES_JSON": "[]"},
    {"TUBE_BRIDGE_PUBLIC_BASE_URL": BASE, "TUBE_BRIDGE_OAUTH_SIGNING_KEY": SIGNING_KEY},
])
def test_partial_oauth_configuration_fails_closed(monkeypatch, present):
    _clear_oauth_env(monkeypatch)
    for key, value in present.items():
        monkeypatch.setenv(key, value)
    oauth = _oauth_module()
    with pytest.raises(ValueError, match="OAuth configuration"):
        oauth.OAuthConfig.from_env()


@pytest.mark.parametrize("base", [
    "http://demo.example", "https://demo.example/mcp", "https://demo.example?q=1",
    "https://demo.example/#x", "https://user@demo.example", "https://*.example",
    "not-a-url", "https://demo.example/",
])
def test_public_base_url_must_be_exact_https_origin(monkeypatch, base):
    _set_oauth_env(monkeypatch, base=base)
    oauth = _oauth_module()
    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        oauth.OAuthConfig.from_env()


def test_signing_key_requires_at_least_32_utf8_bytes(monkeypatch):
    _set_oauth_env(monkeypatch, signing="too-short")
    oauth = _oauth_module()
    with pytest.raises(ValueError, match="SIGNING_KEY"):
        oauth.OAuthConfig.from_env()


@pytest.mark.parametrize("invites", [
    [],
    [{"id": "bad id", "role": "tester", "secret_sha256": "0" * 64}],
    [{"id": "x", "role": "admin", "secret_sha256": "0" * 64}],
    [{"id": "x", "role": "tester", "secret_sha256": "ABC" + "0" * 61}],
    [{"id": "x", "role": "tester", "secret_sha256": "0" * 64, "secret": "plaintext"}],
    [
        {"id": "same", "role": "operator", "secret_sha256": "0" * 64},
        {"id": "same", "role": "tester", "secret_sha256": "1" * 64},
    ],
    [
        {"id": "one", "role": "operator", "secret_sha256": "0" * 64},
        {"id": "two", "role": "tester", "secret_sha256": "0" * 64},
    ],
])
def test_invite_configuration_is_strict_and_contains_no_plaintext(monkeypatch, invites):
    _set_oauth_env(monkeypatch, invites=invites)
    oauth = _oauth_module()
    with pytest.raises(ValueError, match="invite"):
        oauth.OAuthConfig.from_env()


def test_invite_configuration_is_bounded_to_64(monkeypatch):
    invites = [
        {"id": f"tester-{i}", "role": "tester", "secret_sha256": f"{i:064x}"}
        for i in range(65)
    ]
    _set_oauth_env(monkeypatch, invites=invites)
    oauth = _oauth_module()
    with pytest.raises(ValueError, match="64"):
        oauth.OAuthConfig.from_env()


def test_valid_config_has_exact_issuer_resource_and_eight_hour_ttl(monkeypatch):
    service = _service(monkeypatch)
    assert service.enabled is True
    assert service.config.issuer == BASE
    assert service.config.resource == RESOURCE
    assert service.config.access_token_ttl_seconds == 8 * 60 * 60
    assert service.config.authorization_ttl_seconds == 5 * 60


# ---------------------------------------------------------------------------
# Discovery, challenge, and DCR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discovery_metadata_is_public_canonical_and_current(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        root = await client.get("/.well-known/oauth-protected-resource")
        path = await client.get("/.well-known/oauth-protected-resource/mcp")
        auth = await client.get("/.well-known/oauth-authorization-server")
    assert root.status_code == path.status_code == auth.status_code == 200
    assert root.json() == path.json() == {
        "resource": RESOURCE,
        "authorization_servers": [BASE],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["mcp:tools"],
    }
    assert auth.json() == {
        "issuer": BASE,
        "authorization_endpoint": f"{BASE}/oauth/authorize",
        "token_endpoint": f"{BASE}/oauth/token",
        "registration_endpoint": f"{BASE}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["mcp:tools"],
        "authorization_response_iss_parameter_supported": True,
    }


@pytest.mark.asyncio
async def test_default_create_app_builds_oauth_from_environment(monkeypatch):
    _set_oauth_env(monkeypatch)
    app = _app(monkeypatch, None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        metadata = await client.get("/.well-known/oauth-protected-resource")
        health = await client.get("/health")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == RESOURCE
    assert health.json()["auth_oauth"]["enabled"] is True


def test_default_create_app_fails_closed_on_partial_oauth_env(monkeypatch):
    _clear_oauth_env(monkeypatch)
    monkeypatch.setenv("TUBE_BRIDGE_PUBLIC_BASE_URL", BASE)
    with pytest.raises(ValueError, match="OAuth configuration"):
        _app(monkeypatch, None)


@pytest.mark.asyncio
async def test_oauth_routes_are_404_when_adapter_disabled(monkeypatch):
    _clear_oauth_env(monkeypatch)
    app = _app(monkeypatch, None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for path in (
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-authorization-server",
            "/oauth/register", "/oauth/authorize", "/oauth/token",
        ):
            response = await client.get(path)
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_protected_401_advertises_resource_metadata_without_counting(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/mcp")
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge == f'Bearer resource_metadata="{BASE}/.well-known/oauth-protected-resource", scope="mcp:tools"'
    assert service.metrics() == {"operator_requests": 0, "tester_requests": 0, "unique_oauth_subjects": 0}


@pytest.mark.asyncio
async def test_dcr_returns_stateless_public_client_and_preserves_exact_redirects(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirects = ["https://Claude.AI:443/api/mcp/auth_callback?x=%2F", "http://localhost:49152/callback/"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await _register(client, redirects)
    assert response.status_code == 201
    body = response.json()
    assert body["redirect_uris"] == redirects
    assert body["token_endpoint_auth_method"] == "none"
    assert body["grant_types"] == ["authorization_code"]
    assert body["response_types"] == ["code"]
    assert body["client_id"].startswith("tbmc1.")
    assert service.validate_client(body["client_id"])["redirect_uris"] == redirects


@pytest.mark.asyncio
@pytest.mark.parametrize("redirect", [
    "http://example.com/callback", "https://user@example.com/callback",
    "https://*.example.com/callback", "https://example.com/callback#fragment",
    " https://example.com/callback", "https://example.com/callback\n",
    "ftp://example.com/callback", "not-a-uri",
])
async def test_dcr_rejects_unsafe_redirects(monkeypatch, redirect):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await _register(client, [redirect])
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


@pytest.mark.asyncio
async def test_dcr_rejects_exact_duplicates_but_does_not_canonicalize(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        duplicate = await _register(client, ["https://example.com/cb", "https://example.com/cb"])
        variants = await _register(client, ["https://example.com/cb", "https://EXAMPLE.com:443/cb/"])
    assert duplicate.status_code == 400
    assert variants.status_code == 201
    assert variants.json()["redirect_uris"] == ["https://example.com/cb", "https://EXAMPLE.com:443/cb/"]


@pytest.mark.asyncio
async def test_dcr_enforces_content_type_body_uri_count_uri_length_and_name_bounds(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        wrong_type = await client.post("/oauth/register", content="{}", headers={"content-type": "text/plain"})
        oversized = await client.post("/oauth/register", content=b"{" + b" " * 16_385, headers={"content-type": "application/json"})
        no_uris = await _register(client, [])
        too_many = await _register(client, [f"https://example.com/{i}" for i in range(9)])
        long_uri = await _register(client, ["https://example.com/" + "x" * 2030])
        long_name = await _register(client, ["https://example.com/cb"], client_name="x" * 129)
    assert wrong_type.status_code == 415
    assert oversized.status_code == 413
    assert no_uris.status_code == too_many.status_code == long_uri.status_code == long_name.status_code == 400


@pytest.mark.asyncio
async def test_tampered_client_id_is_rejected_without_redirect(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        registered = await _register(client, [redirect])
        client_id = registered.json()["client_id"] + "x"
        response, _ = await _authorization_request(client, client_id, redirect)
    assert response.status_code == 400
    assert "location" not in response.headers


# ---------------------------------------------------------------------------
# Authorization, token exchange, and cryptographic enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authorize_requires_exact_redirect_state_resource_and_s256(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        _, challenge = _pkce()
        common = {
            "response_type": "code", "client_id": client_id, "redirect_uri": redirect,
            "state": "state", "resource": RESOURCE,
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        cases = [
            {**common, "redirect_uri": redirect + "/"},
            {**common, "state": ""},
            {k: v for k, v in common.items() if k != "resource"},
            {**common, "resource": BASE},
            {**common, "code_challenge_method": "plain"},
            {**common, "code_challenge": "short"},
        ]
        responses = [await client.get("/oauth/authorize", params=params) for params in cases]
        duplicate_resource = await client.get("/oauth/authorize", params=list(common.items()) + [("resource", RESOURCE)])
    assert all(response.status_code == 400 for response in responses)
    assert duplicate_resource.status_code == 400


@pytest.mark.asyncio
async def test_authorize_page_has_csrf_no_store_csp_and_no_invite_material(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        response, request_id = await _authorization_request(client, client_id, redirect)
    assert response.status_code == 200 and request_id
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "secure" in cookie
    serialized = response.text + json.dumps(response.headers)
    assert OPERATOR_CODE not in serialized and TESTER_CODE not in serialized
    assert _digest(OPERATOR_CODE) not in serialized and "operator-main" not in serialized


@pytest.mark.asyncio
async def test_authorize_post_requires_matching_csrf_cookie(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        _, request_id = await _authorization_request(client, client_id, redirect)
        saved_cookie = client.cookies.get("tb_oauth_csrf")
        client.cookies.clear()
        missing = await _complete_authorization(client, request_id, TESTER_CODE)
        client.cookies.set("tb_oauth_csrf", "wrong-cookie")
        wrong = await _complete_authorization(client, request_id, TESTER_CODE)
        client.cookies.clear()
        client.cookies.set("tb_oauth_csrf", saved_cookie)
        correct = await _complete_authorization(client, request_id, TESTER_CODE)
    assert missing.status_code == wrong.status_code == 401
    assert correct.status_code in (302, 303, 307)


@pytest.mark.asyncio
async def test_authorize_post_enforces_form_content_type_and_16k_limit(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        wrong = await client.post("/oauth/authorize", json={})
        large = await client.post(
            "/oauth/authorize",
            content=b"x" * 16_385,
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    assert wrong.status_code == 415
    assert large.status_code == 413


@pytest.mark.asyncio
async def test_safe_authorization_error_redirect_includes_iss_and_state(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    _, challenge = _pkce()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        response = await client.get("/oauth/authorize", params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect,
            "state": "unchanged-state",
            "resource": BASE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }, follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    location = urlparse(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == redirect
    query = parse_qs(location.query)
    assert query["error"] == ["invalid_request"]
    assert query["state"] == ["unchanged-state"]
    assert query["iss"] == [BASE]
    assert "code" not in query


@pytest.mark.asyncio
async def test_wrong_invite_is_generic_and_pending_request_can_retry(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        _, request_id = await _authorization_request(client, client_id, redirect)
        wrong = await _complete_authorization(client, request_id, "wrong-code")
        correct = await _complete_authorization(client, request_id, TESTER_CODE)
    assert wrong.status_code == 401
    assert wrong.json() == {"error": "access_denied", "message": "Invalid or expired authorization request."}
    assert correct.status_code in (302, 303, 307)


@pytest.mark.asyncio
async def test_successful_operator_flow_returns_iss_state_and_bounded_token(monkeypatch):
    clock = Clock()
    service = _service(monkeypatch, clock=clock)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token, query, _ = await _oauth_flow(client, OPERATOR_CODE, redirect)
    assert query["state"] == ["state-123"]
    assert query["iss"] == [BASE]
    assert token["token_type"] == "Bearer"
    assert token["expires_in"] == 8 * 60 * 60
    assert token["scope"] == "mcp:tools"
    assert "refresh_token" not in token
    principal = service.authenticate_bearer(token["access_token"])
    assert principal.role == "operator"
    assert principal.method == "oauth"
    assert principal.subject and principal.subject not in ("operator-main", OPERATOR_CODE, _digest(OPERATOR_CODE))


@pytest.mark.asyncio
async def test_tester_flow_has_distinct_pseudonymous_subject(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        operator, _, _ = await _oauth_flow(client, OPERATOR_CODE, "https://claude.ai/api/mcp/operator")
        tester, _, _ = await _oauth_flow(client, TESTER_CODE, "https://claude.ai/api/mcp/tester")
    operator_principal = service.authenticate_bearer(operator["access_token"])
    tester_principal = service.authenticate_bearer(tester["access_token"])
    assert operator_principal.role == "operator"
    assert tester_principal.role == "tester"
    assert operator_principal.subject != tester_principal.subject


@pytest.mark.asyncio
async def test_authorization_request_and_code_expire_at_five_minutes(monkeypatch):
    clock = Clock()
    service = _service(monkeypatch, clock=clock)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        _, request_id = await _authorization_request(client, client_id, redirect)
        clock.now += 301
        expired_request = await _complete_authorization(client, request_id, TESTER_CODE)
        clock.now -= 301
        _, request_id = await _authorization_request(client, client_id, redirect)
        callback = await _complete_authorization(client, request_id, TESTER_CODE)
        code = parse_qs(urlparse(callback.headers["location"]).query)["code"][0]
        clock.now += 301
        expired_code = await _token_exchange(client, code, client_id, redirect)
    assert expired_request.status_code == 401
    assert expired_code.status_code == 400
    assert expired_code.json()["error"] == "invalid_grant"


@pytest.mark.asyncio
async def test_code_is_single_use_even_after_wrong_verifier(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        _, request_id = await _authorization_request(client, client_id, redirect)
        callback = await _complete_authorization(client, request_id, TESTER_CODE)
        code = parse_qs(urlparse(callback.headers["location"]).query)["code"][0]
        wrong = await _token_exchange(client, code, client_id, redirect, verifier="w" * 43)
        retry = await _token_exchange(client, code, client_id, redirect)
    assert wrong.status_code == retry.status_code == 400
    assert wrong.json()["error"] == retry.json()["error"] == "invalid_grant"


@pytest.mark.asyncio
async def test_token_requires_exact_client_redirect_and_resource_binding(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for field, value in (
            ("client_id", "tampered"),
            ("redirect_uri", redirect + "/"),
            ("resource", BASE),
        ):
            client_id = (await _register(client, [redirect])).json()["client_id"]
            _, request_id = await _authorization_request(client, client_id, redirect)
            callback = await _complete_authorization(client, request_id, TESTER_CODE)
            code = parse_qs(urlparse(callback.headers["location"]).query)["code"][0]
            form = {
                "grant_type": "authorization_code", "code": code, "client_id": client_id,
                "redirect_uri": redirect, "code_verifier": "v" * 43, "resource": RESOURCE,
            }
            form[field] = value
            response = await client.post("/oauth/token", data=form)
            assert response.status_code == 400
            assert response.json()["error"] == "invalid_grant"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["missing", "duplicate"])
async def test_token_rejects_missing_or_duplicate_resource(monkeypatch, mode):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        client_id = (await _register(client, [redirect])).json()["client_id"]
        _, request_id = await _authorization_request(client, client_id, redirect)
        callback = await _complete_authorization(client, request_id, TESTER_CODE)
        code = parse_qs(urlparse(callback.headers["location"]).query)["code"][0]
        fields = [
            ("grant_type", "authorization_code"), ("code", code),
            ("client_id", client_id), ("redirect_uri", redirect),
            ("code_verifier", "v" * 43),
        ]
        if mode == "duplicate":
            fields += [("resource", RESOURCE), ("resource", RESOURCE)]
        response = await client.post("/oauth/token", data=fields)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


@pytest.mark.asyncio
async def test_token_endpoint_enforces_form_content_type_and_16k_limit(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        wrong = await client.post("/oauth/token", json={})
        large = await client.post("/oauth/token", content=b"x" * 16_385, headers={"content-type": "application/x-www-form-urlencoded"})
    assert wrong.status_code == 415
    assert large.status_code == 413


@pytest.mark.asyncio
async def test_access_token_tamper_expiry_and_wrong_audience_fail_closed(monkeypatch):
    clock = Clock()
    service = _service(monkeypatch, clock=clock)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token, _, _ = await _oauth_flow(client)
    value = token["access_token"]
    assert service.authenticate_bearer(value + "x") is None
    clock.now += 8 * 60 * 60 + 1
    assert service.authenticate_bearer(value) is None
    other_clock = Clock(now=2_000_000_000.0)
    other = _service(monkeypatch, clock=other_clock, base="https://other.example")
    assert other.authenticate_bearer(value) is None


# ---------------------------------------------------------------------------
# Existing Bearer compatibility, aggregate metrics, privacy, and IP quota
# ---------------------------------------------------------------------------


def test_preexisting_static_bearer_boolean_regression_is_green_during_red(monkeypatch):
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "existing-static-key")
    from tube_bridge.transport import _check_auth
    assert _check_auth({"headers": [(b"authorization", b"Bearer existing-static-key")]}) is True
    assert _check_auth({"headers": [(b"authorization", b"Bearer wrong")]}) is False


def test_preexisting_ip_bucket_regression_is_green_during_red():
    policy = importlib.import_module("tube_bridge.demo_policy")
    allowance = policy.DemoAllowance(salt=b"preexisting-ip-regression-salt-32b")
    allowance.consume("198.51.100.44")
    allowance.consume("198.51.100.44")
    assert allowance.metrics()["client_buckets"] == 1


def test_existing_static_bearer_contract_remains_operator(monkeypatch):
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "existing-static-key")
    service = _service(monkeypatch)
    from tube_bridge.transport import _check_auth
    scope = {"headers": [(b"authorization", b"Bearer existing-static-key")]}
    assert _check_auth(scope) is True
    principal = service.authenticate_request(scope, static_key="existing-static-key")
    assert principal.role == "operator" and principal.method == "static_bearer"


@pytest.mark.asyncio
async def test_health_auth_metrics_are_aggregate_only(monkeypatch):
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "existing-static-key")
    service = _service(monkeypatch)
    service.record_authenticated(service.authenticate_request(
        {"headers": [(b"authorization", b"Bearer existing-static-key")]},
        static_key="existing-static-key",
    ))
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        token, _, _ = await _oauth_flow(client, TESTER_CODE)
        principal = service.authenticate_bearer(token["access_token"])
        service.record_authenticated(principal)
        service.record_authenticated(principal)
        health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["auth_oauth"] == {
        "enabled": True,
        "operator_requests": 1,
        "tester_requests": 2,
        "unique_oauth_subjects": 1,
    }
    serialized = json.dumps(health.json())
    for forbidden in (
        OPERATOR_CODE, TESTER_CODE, _digest(OPERATOR_CODE), _digest(TESTER_CODE),
        "operator-main", "tester-001", principal.subject, token["access_token"],
        "claude.ai", "client_id", "redirect_uri",
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_all_three_protected_routes_count_once_after_auth(monkeypatch):
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "existing-static-key")
    service = _service(monkeypatch)
    transport = importlib.import_module("tube_bridge.transport")

    async def respond(send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    class FakeManager:
        def __init__(self, app, stateless):
            pass

        @asynccontextmanager
        async def run(self):
            yield

        async def handle_request(self, scope, receive, send):
            await respond(send)

    class FakeSSE:
        def __init__(self, path):
            pass

        @asynccontextmanager
        async def connect_sse(self, scope, receive, send):
            yield object(), object()
            await respond(send)

        async def handle_post_message(self, scope, receive, send):
            await respond(send)

    class FakeServer:
        async def run(self, read, write, options):
            return

        def create_initialization_options(self):
            return None

    monkeypatch.setattr(transport, "StreamableHTTPSessionManager", FakeManager)
    monkeypatch.setattr(transport, "SseServerTransport", FakeSSE)
    app = transport.create_app(FakeServer(), "127.0.0.1", 8080, oauth_service=service)
    headers = {"authorization": "Bearer existing-static-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = [
            await client.post("/mcp", headers=headers),
            await client.get("/sse", headers=headers),
            await client.post("/messages", headers=headers),
        ]
    assert [response.status_code for response in responses] == [204, 204, 204]
    assert service.metrics() == {
        "operator_requests": 3,
        "tester_requests": 0,
        "unique_oauth_subjects": 0,
    }


@pytest.mark.asyncio
async def test_only_successful_protected_dispatch_counts(monkeypatch):
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "existing-static-key")
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/health")
        await client.get("/.well-known/oauth-protected-resource")
        await _register(client)
        await client.get("/unknown", headers={"authorization": "Bearer existing-static-key"})
        await client.post("/messages")
        before = service.metrics()
        static_dispatch = await client.post("/messages", headers={"authorization": "Bearer existing-static-key"})
        token, _, _ = await _oauth_flow(client, TESTER_CODE)
        oauth_dispatch = await client.post("/messages", headers={"authorization": f"Bearer {token['access_token']}"})
        after = service.metrics()
    assert before == {"operator_requests": 0, "tester_requests": 0, "unique_oauth_subjects": 0}
    assert static_dispatch.status_code != 401 and oauth_dispatch.status_code != 401
    assert after == {"operator_requests": 1, "tester_requests": 1, "unique_oauth_subjects": 1}


@pytest.mark.asyncio
async def test_oauth_roles_do_not_change_ip_allowance_identity(monkeypatch):
    policy = importlib.import_module("tube_bridge.demo_policy")
    allowance = policy.DemoAllowance(salt=b"oauth-independent-ip-salt-32bytes!!")
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        operator_token, _, _ = await _oauth_flow(client, OPERATOR_CODE, "https://claude.ai/api/mcp/operator-ip")
        tester_token, _, _ = await _oauth_flow(client, TESTER_CODE, "https://claude.ai/api/mcp/tester-ip")
    principals = [
        service.authenticate_bearer(operator_token["access_token"]),
        service.authenticate_bearer(tester_token["access_token"]),
    ]
    for principal in principals:
        service.record_authenticated(principal)
        with policy.bind_client_ip("198.51.100.44"):
            allowance.consume(policy.get_current_client_ip())
    assert service.metrics() == {
        "operator_requests": 1,
        "tester_requests": 1,
        "unique_oauth_subjects": 2,
    }
    metrics = allowance.metrics()
    assert metrics["allowed_total"] == 2
    assert metrics["client_buckets"] == 1
    assert metrics["limit"] == 5


@pytest.mark.asyncio
async def test_auth_failures_and_invite_flow_do_not_log_secrets(monkeypatch, caplog):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    redirect = "https://claude.ai/api/mcp/auth_callback"
    with caplog.at_level("DEBUG"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            client_id = (await _register(client, [redirect])).json()["client_id"]
            _, request_id = await _authorization_request(client, client_id, redirect)
            await _complete_authorization(client, request_id, "wrong-secret-invite")
            unauthorized = await client.post(
                "/messages",
                headers={"authorization": "Bearer secret-access-token-value"},
            )
    assert unauthorized.status_code == 401
    app_logs = "\n".join(
        record.getMessage() for record in caplog.records
        if record.name.startswith("tube_bridge")
    )
    serialized = app_logs + unauthorized.text
    for forbidden in (
        "wrong-secret-invite", "secret-access-token-value", client_id,
        "operator-main", "tester-001", _digest(OPERATOR_CODE), _digest(TESTER_CODE),
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_oauth_only_mode_is_auth_enabled_and_selfhost_no_auth_stays_open(monkeypatch):
    service = _service(monkeypatch)
    app = _app(monkeypatch, service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        oauth_health = await client.get("/health")
    assert oauth_health.json()["auth"] == "enabled"
    assert oauth_health.json()["auth_oauth"]["enabled"] is True

    _clear_oauth_env(monkeypatch)
    monkeypatch.delenv("TUBE_BRIDGE_AUTH_KEY", raising=False)
    open_app = _app(monkeypatch, None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=open_app), base_url="http://test") as client:
        open_health = await client.get("/health")
    assert open_health.json()["auth"] == "disabled"
    assert open_health.json()["auth_oauth"] == {
        "enabled": False,
        "operator_requests": 0,
        "tester_requests": 0,
        "unique_oauth_subjects": 0,
    }
