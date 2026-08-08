"""Deterministic transport/ASGI contract tests for HTTP auth, health, routing.

Uses httpx AsyncClient with ASGI transport to exercise the raw ASGI app
from tube_bridge.transport.create_app.

KEY DESIGN: No module-scoped app fixture.  Each test sets/un-sets
TUBE_BRIDGE_AUTH_KEY first and only then calls create_app(server, ...).
This prevents stale auth captured at import time.

No live YouTube calls.  No embedding model downloads.
"""

import json
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers — build app AFTER auth env is set
# ---------------------------------------------------------------------------

def _build_app():
    """Build the raw ASGI app.  Must be called AFTER TUBE_BRIDGE_AUTH_KEY
    is set/unset by the test, because create_app captures the key at
    call time (not at import time).
    """
    from tube_bridge.server import server
    from tube_bridge.transport import create_app
    return create_app(server, "127.0.0.1", 8080)


# ---------------------------------------------------------------------------
# /health — public, no auth required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_reports_tools_16_no_auth(monkeypatch):
    """GET /health without auth key → 200, tools=16, auth=disabled.

    Auth key is explicitly unset before app creation.
    """
    monkeypatch.delenv("TUBE_BRIDGE_AUTH_KEY", raising=False)
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["status"] == "ok"
        assert data["server"] == "tube-bridge"
        assert data["tools"] == 16, f"Expected tools=16, got {data.get('tools')}"
        assert data["auth"] == "disabled", (
            f"Expected auth=disabled without TUBE_BRIDGE_AUTH_KEY, got {data.get('auth')}")


@pytest.mark.asyncio
async def test_health_reports_auth_enabled_when_key_set(monkeypatch):
    """GET /health with auth key set → 200, tools=16, auth=enabled.

    Auth key is explicitly set before app creation.
    """
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-token-for-health")
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["status"] == "ok"
        assert data["tools"] == 16
        assert data["auth"] == "enabled", (
            f"Expected auth=enabled with TUBE_BRIDGE_AUTH_KEY set, got {data.get('auth')}")


@pytest.mark.asyncio
async def test_health_always_returns_200_even_with_auth_key(monkeypatch):
    """GET /health with auth key set but no Authorization header → still 200.

    /health is explicitly excluded from auth checks in transport.py.
    """
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-token-for-health")
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # No Authorization header — health should still succeed
        resp = await client.get("/health")
        assert resp.status_code == 200, (
            f"/health should be public even with auth key set, got {resp.status_code}")


# ---------------------------------------------------------------------------
# Protected routes — reject missing/invalid Authorization: Bearer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_protected_route_rejects_missing_auth(monkeypatch):
    """GET /mcp without Authorization header when auth key is set → 401."""
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-auth-token")
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/mcp")
        assert resp.status_code == 401, (
            f"Expected 401 without Authorization, got {resp.status_code}")
        data = resp.json()
        assert "unauthorized" in data.get("error", ""), (
            f"Expected unauthorized error, got: {data}")


@pytest.mark.asyncio
async def test_protected_route_rejects_wrong_auth(monkeypatch):
    """GET /mcp with wrong Authorization header → 401."""
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-auth-token")
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/mcp", headers={"Authorization": "Bearer wrong-value"})
        assert resp.status_code == 401, (
            f"Expected 401 with wrong auth, got {resp.status_code}")


@pytest.mark.asyncio
async def test_protected_route_rejects_wrong_scheme(monkeypatch):
    """GET /mcp with Basic auth → 401 (only Bearer is checked)."""
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-auth-token")
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/mcp", headers={
            "Authorization": "Basic dGVzdDpwYXNz"})
        assert resp.status_code == 401, (
            f"Expected 401 with Basic auth, got {resp.status_code}")


@pytest.mark.asyncio
async def test_sse_rejects_missing_auth(monkeypatch):
    """GET /sse without Authorization header when auth key is set → 401."""
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-auth-token")
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/sse")
        assert resp.status_code == 401, (
            f"Expected 401 on /sse without auth, got {resp.status_code}")


# ---------------------------------------------------------------------------
# Auth-disabled mode — all routes accept no Authorization
# ---------------------------------------------------------------------------

def test_check_auth_permits_all_routes_when_key_unset(monkeypatch):
    """_check_auth returns True for all routes when TUBE_BRIDGE_AUTH_KEY is unset.

    This tests the auth logic directly without requiring the ASGI lifespan
    that /mcp and /sse routes need for StreamableHTTP/SseServerTransport.
    """
    monkeypatch.delenv("TUBE_BRIDGE_AUTH_KEY", raising=False)
    from tube_bridge.transport import _check_auth, _get_auth_key

    assert _get_auth_key() is None, "Auth key should be None when unset"

    # Synthetic scopes for different paths
    for path in ["/mcp", "/sse", "/messages", "/health"]:
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
        }
        assert _check_auth(scope) is True, (
            f"_check_auth should permit {path} when no auth key is set")


# ---------------------------------------------------------------------------
# /messages POST auth check — synthetic scope
# ---------------------------------------------------------------------------

def test_check_auth_rejects_missing_auth_for_protected_routes(monkeypatch):
    """_check_auth returns False for protected routes when auth key is set
    but no Authorization header is present.
    """
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-auth-token")
    from tube_bridge.transport import _check_auth

    for path in ["/mcp", "/sse", "/messages"]:
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
        }
        assert _check_auth(scope) is False, (
            f"_check_auth should reject {path} when auth key is set and "
            f"no Authorization header present")


def test_check_auth_permits_health_even_with_key_set(monkeypatch):
    """_check_auth is not called for /health in the app, but at the
    _check_auth level, a health path still passes because the app
    short-circuits before auth.  The key assertion is that /health
    returns 200 regardless (tested in test_health_always_returns_200_...).
    This test documents the _check_auth function's own behaviour.
    """
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "test-auth-token")
    from tube_bridge.transport import _check_auth

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [],
    }
    # _check_auth returns False for /health too when key is set
    # but the app short-circuits before calling _check_auth for /health
    assert _check_auth(scope) is False, (
        "_check_auth returns False for /health when key set (app bypasses it)")


# ---------------------------------------------------------------------------
# Routing: 404 for unknown paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unknown_path_returns_404(monkeypatch):
    """GET /nonexistent → 404 regardless of auth state."""
    monkeypatch.delenv("TUBE_BRIDGE_AUTH_KEY", raising=False)
    app = _build_app()

    import httpx
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/nonexistent")
        assert resp.status_code == 404, (
            f"Expected 404, got {resp.status_code}")


# ---------------------------------------------------------------------------
# mcp_client_smoke.py import and parser validation (deterministic, no network)
# ---------------------------------------------------------------------------

MCP_SMOKE_PATH = Path(__file__).resolve().parent / "mcp_client_smoke.py"


def _load_smoke_module():
    """Import mcp_client_smoke as a module for deterministic tests."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "mcp_client_smoke", str(MCP_SMOKE_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for {MCP_SMOKE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mcp_smoke_file_exists():
    """mcp_client_smoke.py must be present in the tests directory."""
    assert MCP_SMOKE_PATH.exists(), (
        f"tests/mcp_client_smoke.py not found at {MCP_SMOKE_PATH}")


def test_mcp_smoke_imports_without_error():
    """mcp_client_smoke.py must import without syntax/import errors."""
    try:
        mod = _load_smoke_module()
    except Exception as e:
        pytest.fail(f"mcp_client_smoke.py import failed: {e}")


def test_mcp_smoke_expected_tools_is_16_unique():
    """EXPECTED_TOOLS must contain exactly 16 unique names."""
    mod = _load_smoke_module()
    expected = mod.EXPECTED_TOOLS
    assert len(expected) == 16, (
        f"EXPECTED_TOOLS has {len(expected)} entries, expected 16")
    assert len(set(expected)) == len(expected), (
        "EXPECTED_TOOLS has duplicate names")
    assert "youtube_search" in expected
    assert "corpus_delete" in expected
    assert "tube_bridge_help" in expected


def test_mcp_smoke_parse_args_valid():
    """parse_args with valid --url returns correct namespace."""
    mod = _load_smoke_module()
    args = mod.parse_args(["--url", "http://localhost:8080/mcp"])
    assert args.url == "http://localhost:8080/mcp"
    assert args.auth is None


def test_mcp_smoke_parse_args_with_auth():
    """parse_args with --url and --auth."""
    mod = _load_smoke_module()
    args = mod.parse_args([
        "--url", "http://localhost:8080/mcp",
        "--auth", "my-secret-token",
    ])
    assert args.url == "http://localhost:8080/mcp"
    assert args.auth == "my-secret-token"


def test_mcp_smoke_emit_result_success():
    """emit_result with success=True produces valid JSON result."""
    mod = _load_smoke_module()
    result_str = mod.emit_result(True, 16, mod.EXPECTED_TOOLS)
    result = json.loads(result_str)
    assert result["ok"] is True
    assert result["tool_count"] == 16
    assert len(result["tool_names"]) == 16


def test_mcp_smoke_emit_result_failure():
    """emit_result with ok=False produces valid JSON with error fields."""
    mod = _load_smoke_module()
    result_str = mod.emit_result(
        False, 10, ["a", "b", "c"],
        error_type="ConnectionError",
        error_message="Connection refused",
    )
    result = json.loads(result_str)
    assert result["ok"] is False
    assert result["tool_count"] == 10
    assert len(result["tool_names"]) == 3
    assert result["error_type"] == "ConnectionError"
    assert result["error_message"] == "Connection refused"


# ---------------------------------------------------------------------------
# Deterministic monkeypatched failure test for mcp_client_smoke
# ---------------------------------------------------------------------------

def test_mcp_smoke_main_catches_exception_and_emits_json(monkeypatch, capsys):
    """When run_smoke raises an exception, main() catches it and emits
    structured JSON with ok=false, error_type, error_message, and returns
    nonzero exit code.  This is the deterministic monkeypatched failure
    test required by the audit remediation.
    """
    mod = _load_smoke_module()

    # Monkeypatch run_smoke to simulate a transport/session exception
    async def _failing_run_smoke(url, auth_token=None):
        raise ConnectionRefusedError("Simulated connection refused for test")

    monkeypatch.setattr(mod, "run_smoke", _failing_run_smoke)

    exit_code = None
    try:
        mod.main(["--url", "http://localhost:9999/mcp"])
    except SystemExit as e:
        exit_code = e.code

    captured = capsys.readouterr()
    result = json.loads(captured.out.strip())

    assert exit_code == 1, f"Expected exit code 1, got {exit_code}"
    assert result["ok"] is False
    assert "ConnectionRefusedError" in result["error_type"], (
        f"Expected ConnectionRefusedError in error_type, got {result.get('error_type')}")
    assert "Simulated connection refused" in result["error_message"], (
        f"Expected error message about refused, got {result.get('error_message')}")
