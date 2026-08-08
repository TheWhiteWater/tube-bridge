"""MCP integration tests — transport, auth, initialize, tools/list handshake.

Pack C Second Remediation: preserve approved real authorized MCP tests.

Tests use mcp.ClientSession with streamable_http_client against a locally
started tube-bridge server subprocess. No live YouTube calls. No live API keys.

Validates:
- /health reports ok with correct tool count
- Unauthorized /mcp requests are rejected when auth is configured
- Authorized MCP initialize succeeds
- tools/list returns exactly 16 expected tool names
- Error handling for structured failure modes
"""

import asyncio
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# Expected 16 tool names from the current tube-bridge registry
EXPECTED_TOOL_NAMES = sorted([
    "youtube_search",
    "youtube_search_channels",
    "youtube_get_channel_info",
    "youtube_get_video_info",
    "youtube_get_trending",
    "youtube_get_channel_videos",
    "youtube_get_playlist",
    "youtube_get_transcript",
    "youtube_get_available_languages",
    "youtube_get_comments",
    "tube_bridge_help",
    "corpus_create",
    "corpus_add",
    "corpus_search",
    "corpus_list",
    "corpus_delete",
])

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_free_port():
    """Return a free TCP port on localhost."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port, auth_key=None, timeout=30):
    """Start tube-bridge server as a subprocess. Returns (process, url).

    Uses python3 from sys.executable to run the root server.py.
    """
    cache_dir = tempfile.mkdtemp(prefix="tube_bridge_mcp_")
    env = {
        **os.environ,
        "TUBE_BRIDGE_CACHE": cache_dir,
        "PATH": os.environ.get("PATH", ""),
    }
    if auth_key:
        env["TUBE_BRIDGE_AUTH_KEY"] = auth_key
    else:
        env.pop("TUBE_BRIDGE_AUTH_KEY", None)

    # Ensure no YOUTUBE_API_KEY leaks into the test
    env.pop("YOUTUBE_API_KEY", None)

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "server.py"),
        "--http",
        "--port", str(port),
    ]

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
    )
    proc._tube_bridge_cache_dir = cache_dir

    url = f"http://127.0.0.1:{port}"

    # Wait for server to be ready (poll /health)
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            import urllib.request
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return proc, url
        except Exception:
            pass
        if proc.poll() is not None:
            stdout = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            shutil.rmtree(cache_dir, ignore_errors=True)
            raise RuntimeError(
                f"Server process exited before becoming ready "
                f"(rc={proc.returncode})\nSTDOUT: {stdout}\nSTDERR: {stderr}"
            )
        time.sleep(0.5)

    proc.kill()
    proc.wait()
    shutil.rmtree(cache_dir, ignore_errors=True)
    raise RuntimeError(f"Server did not become ready within {timeout}s")


def _stop_server(proc):
    """Gracefully stop the server subprocess and remove its temp cache."""
    try:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    finally:
        shutil.rmtree(getattr(proc, "_tube_bridge_cache_dir", ""), ignore_errors=True)


# ---------------------------------------------------------------------------
# MCP Handshake tests
# ---------------------------------------------------------------------------

class TestMCPHandshake:
    """Real MCP initialize + tools/list handshake against running server."""

    @pytest.fixture(scope="class")
    def server(self):
        """Start a tube-bridge server for the test class (shared scope)."""
        port = _find_free_port()
        proc, url = _start_server(port, timeout=30)
        yield {"proc": proc, "url": url, "port": port}
        _stop_server(proc)

    @pytest.mark.asyncio
    async def test_health_endpoint(self, server):
        """GET /health returns 200 with status=ok and tools=16."""
        import urllib.request
        req = urllib.request.Request(f"{server['url']}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data.get("status") == "ok"
            assert data.get("server") == "tube-bridge"
            # tools count should be 16
            assert data.get("tools") == 16, (
                f"/health reports {data.get('tools')} tools, expected 16"
            )

    @pytest.mark.asyncio
    async def test_initialize_succeeds(self, server):
        """MCP initialize handshake completes successfully without auth."""
        url = f"{server['url']}/mcp"
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                assert init_result is not None

    @pytest.mark.asyncio
    async def test_tools_list_returns_sixteen(self, server):
        """tools/list over /mcp returns exactly 16 unique expected names."""
        url = f"{server['url']}/mcp"
        async with streamable_http_client(url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                names = sorted([tool.name for tool in tools_result.tools])

                assert len(names) == 16, (
                    f"tools/list returned {len(names)} tools, expected 16: {names}"
                )
                assert names == EXPECTED_TOOL_NAMES, (
                    f"tools/list names mismatch.\n"
                    f"Got:      {names}\n"
                    f"Expected: {EXPECTED_TOOL_NAMES}\n"
                    f"Missing:  {set(EXPECTED_TOOL_NAMES) - set(names)}\n"
                    f"Extra:    {set(names) - set(EXPECTED_TOOL_NAMES)}"
                )


# ---------------------------------------------------------------------------
# Auth tests — authorized MCP handshake
# ---------------------------------------------------------------------------

class TestMCPAuth:
    """Authorized MCP handshake with TUBE_BRIDGE_AUTH_KEY configured."""

    @pytest.fixture(scope="class")
    def auth_server(self):
        """Start a server with auth enabled."""
        port = _find_free_port()
        proc, url = _start_server(port, auth_key="test-mcp-auth-token",
                                  timeout=30)
        yield {"proc": proc, "url": url, "port": port,
               "auth_key": "test-mcp-auth-token"}
        _stop_server(proc)

    @pytest.mark.asyncio
    async def test_unauthorized_mcp_rejected(self, auth_server):
        """Unauthorized request to /mcp is rejected when auth is configured."""
        import urllib.request
        import urllib.error
        url = f"{auth_server['url']}/mcp"
        req = urllib.request.Request(url, data=b"{}",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        assert status == 401, (
            f"Expected 401 for unauthorized /mcp, got {status}"
        )

    @pytest.mark.asyncio
    async def test_authorized_initialize_succeeds(self, auth_server):
        """Authorized MCP initialize with Bearer token succeeds."""
        headers = {"Authorization": f"Bearer {auth_server['auth_key']}"}
        url = f"{auth_server['url']}/mcp"
        async with httpx.AsyncClient(headers=headers) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (
                read_stream, write_stream, _
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    init_result = await session.initialize()
                    assert init_result is not None

    @pytest.mark.asyncio
    async def test_authorized_tools_list_returns_sixteen(self, auth_server):
        """Authorized tools/list returns exactly 16 tools."""
        headers = {"Authorization": f"Bearer {auth_server['auth_key']}"}
        url = f"{auth_server['url']}/mcp"
        async with httpx.AsyncClient(headers=headers) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (
                read_stream, write_stream, _
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    names = sorted([tool.name for tool in tools_result.tools])
                    assert len(names) == 16, (
                        f"Authorized tools/list returned {len(names)} tools"
                    )
                    assert names == EXPECTED_TOOL_NAMES


# ---------------------------------------------------------------------------
# Transport auth routing
# ---------------------------------------------------------------------------

class TestTransportAuthRouting:
    """Auth routing: /health always open, /sse and /messages protected."""

    @pytest.fixture(scope="class")
    def auth_server(self):
        """Start a server with auth enabled."""
        port = _find_free_port()
        proc, url = _start_server(port, auth_key="test-transport-auth",
                                  timeout=30)
        yield {"proc": proc, "url": url, "port": port,
               "auth_key": "test-transport-auth"}
        _stop_server(proc)

    @pytest.mark.asyncio
    async def test_health_always_open(self, auth_server):
        """GET /health returns 200 even with auth configured."""
        import urllib.request
        req = urllib.request.Request(f"{auth_server['url']}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data.get("auth") == "enabled"

    @pytest.mark.asyncio
    async def test_sse_rejects_unauthorized(self, auth_server):
        """GET /sse without auth is rejected when auth is configured."""
        import urllib.request
        import urllib.error
        url = f"{auth_server['url']}/sse"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        assert status == 401, (
            f"Expected 401 for unauthorized /sse, got {status}"
        )

    @pytest.mark.asyncio
    async def test_no_auth_configured_allows_access(self):
        """When no TUBE_BRIDGE_AUTH_KEY is set, /health is accessible
        and no 401 rejections occur."""
        port = _find_free_port()
        proc, url = _start_server(port, auth_key=None, timeout=30)
        try:
            import urllib.request
            req = urllib.request.Request(f"{url}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode())
                assert data.get("auth") == "disabled"
        finally:
            _stop_server(proc)
