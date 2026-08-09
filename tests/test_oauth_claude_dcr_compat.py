"""Frozen addendum for the real Claude DCR registration metadata."""

import hashlib
import json

import httpx
import pytest
from mcp.server import Server

from tube_bridge.oauth import OAuthService
from tube_bridge.transport import create_app


BASE = "https://demo.example"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _app(monkeypatch):
    invite_digest = hashlib.sha256(b"unused-high-entropy-invite").hexdigest()
    monkeypatch.setenv("TUBE_BRIDGE_PUBLIC_BASE_URL", BASE)
    monkeypatch.setenv(
        "TUBE_BRIDGE_OAUTH_SIGNING_KEY",
        "claude-dcr-addendum-signing-key-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
    monkeypatch.setenv(
        "TUBE_BRIDGE_OAUTH_INVITES_JSON",
        json.dumps([
            {"id": "tester", "role": "tester", "secret_sha256": invite_digest},
        ]),
    )
    service = OAuthService.from_env()
    return create_app(Server("claude-dcr-addendum"), "127.0.0.1", 8080, service), service


@pytest.mark.asyncio
async def test_claude_refresh_metadata_registration_is_accepted_but_normalized(monkeypatch):
    app, service = _app(monkeypatch)
    payload = {
        "client_name": "Claude Custom Connector",
        "client_uri": "https://claude.ai",
        "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": "mcp:tools",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        response = await client.post("/oauth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["grant_types"] == ["authorization_code"]
    assert body["response_types"] == ["code"]
    assert body["token_endpoint_auth_method"] == "none"
    assert body["redirect_uris"] == [REDIRECT]
    assert "client_secret" not in body
    assert service.validate_client(body["client_id"])["redirect_uris"] == [REDIRECT]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "grant_types",
    [
        ["refresh_token"],
        ["refresh_token", "authorization_code"],
        ["authorization_code", "refresh_token", "refresh_token"],
        ["authorization_code", "client_credentials"],
    ],
)
async def test_dcr_still_rejects_other_unsupported_grant_metadata(monkeypatch, grant_types):
    app, _ = _app(monkeypatch)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        response = await client.post("/oauth/register", json={
            "redirect_uris": [REDIRECT],
            "grant_types": grant_types,
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        })

    assert response.status_code == 400
    assert "client_id" not in response.json()
