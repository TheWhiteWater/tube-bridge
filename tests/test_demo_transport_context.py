"""Frozen RED contracts for demo client identity propagation and health privacy."""

import asyncio
import importlib
import json
import socket

import pytest


def policy_module():
    return importlib.import_module("tube_bridge.demo_policy")


def scope(client="10.0.0.2", headers=()):
    return {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "client": (client, 43123) if client is not None else None,
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers],
    }


def test_direct_client_fallback_when_proxy_headers_not_trusted(monkeypatch):
    policy = policy_module()
    monkeypatch.delenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", raising=False)
    observed = policy.extract_client_ip(scope(
        client="192.0.2.10",
        headers=(("x-forwarded-for", "198.51.100.1"),),
    ))
    assert observed == "192.0.2.10"


def test_rightmost_trusted_hop_resists_spoofed_prefix(monkeypatch):
    policy = policy_module()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "1")
    observed = policy.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "192.0.2.200, 198.51.100.42"),
    )))
    assert observed == "198.51.100.42"


def test_configured_two_proxy_hops_selects_second_from_right(monkeypatch):
    policy = policy_module()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "2")
    observed = policy.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "192.0.2.1, 198.51.100.5, 203.0.113.9"),
    )))
    assert observed == "198.51.100.5"


def test_malformed_selected_proxy_identity_fails_closed(monkeypatch):
    policy = policy_module()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "1")
    assert policy.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "203.0.113.4, not-an-ip"),
    ))) is None


def test_missing_trusted_hop_fails_closed(monkeypatch):
    policy = policy_module()
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "3")
    assert policy.extract_client_ip(scope(headers=(
        ("x-forwarded-for", "203.0.113.4, 203.0.113.5"),
    ))) is None


def test_ipv6_is_canonically_normalized(monkeypatch):
    policy = policy_module()
    monkeypatch.delenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", raising=False)
    observed = policy.extract_client_ip(scope(client="2001:0db8:0:0:0:0:0:1"))
    assert observed == "2001:db8::1"


@pytest.mark.asyncio
async def test_context_propagates_through_asyncio_to_thread():
    policy = policy_module()
    with policy.bind_client_ip("198.51.100.55"):
        observed = await asyncio.to_thread(policy.get_current_client_ip)
    assert observed == "198.51.100.55"
    assert policy.get_current_client_ip() is None


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.asyncio
async def test_real_stateless_mcp_handler_inherits_asgi_identity(monkeypatch, tmp_path):
    """Exercise the real MCP SDK task boundary, not a direct helper call."""
    policy = policy_module()
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    transport = importlib.import_module("tube_bridge.transport")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setattr(ttl, "start_demo_ttl_worker", lambda: None)
    monkeypatch.setattr(ttl, "stop_demo_ttl_worker", lambda: None)

    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    import httpx
    import uvicorn

    test_server = Server("demo-context-contract")

    @test_server.list_tools()
    async def list_tools():
        return [Tool(
            name="observed_identity",
            description="Return test identity",
            inputSchema={"type": "object", "properties": {}},
        )]

    @test_server.call_tool()
    async def call_tool(name, arguments):
        observed = await asyncio.to_thread(policy.get_current_client_ip)
        return [TextContent(type="text", text=json.dumps({"observed": observed}))]

    app = transport.create_app(test_server, "127.0.0.1", 0)
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started
    try:
        headers = {"x-forwarded-for": "192.0.2.250, 198.51.100.42"}
        async with httpx.AsyncClient(headers=headers) as http_client:
            async with streamable_http_client(
                f"http://127.0.0.1:{port}/mcp", http_client=http_client,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool("observed_identity", {})
                    payload = json.loads(result.content[0].text)
        assert payload == {"observed": "198.51.100.42"}
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)


@pytest.mark.asyncio
async def test_demo_health_contains_aggregates_and_no_identity(monkeypatch):
    policy = policy_module()
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    allowance = policy.DemoAllowance(salt=b"health-contract-salt" * 2)
    allowance.consume("198.51.100.60")
    monkeypatch.setattr(policy, "_allowance", allowance)
    monkeypatch.setattr(ttl, "start_demo_ttl_worker", lambda: None)
    monkeypatch.setattr(ttl, "stop_demo_ttl_worker", lambda: None)

    from tube_bridge.server import server
    from tube_bridge.transport import create_app
    import httpx

    app = create_app(server, "127.0.0.1", 8080)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    demo = response.json()["demo"]
    assert demo == {
        "enabled": True,
        "data_api_limit": 5,
        "allowed_total": 1,
        "rejected_total": 0,
        "client_buckets": 1,
        "corpus_ttl_seconds": 600,
    }
    serialized = json.dumps(response.json())
    assert "198.51.100.60" not in serialized


@pytest.mark.asyncio
async def test_sse_messages_request_cannot_replace_connection_identity(monkeypatch):
    """The MCP server task inherits identity from the initial SSE GET.

    The POST to /messages deliberately carries a different forwarded address;
    it must not replace the identity already bound to the SSE server task.
    """
    policy = policy_module()
    ttl = importlib.import_module("tube_bridge.demo_ttl")
    transport = importlib.import_module("tube_bridge.transport")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setattr(ttl, "start_demo_ttl_worker", lambda: None)
    monkeypatch.setattr(ttl, "stop_demo_ttl_worker", lambda: None)

    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    import httpx
    import uvicorn

    test_server = Server("demo-sse-context-contract")

    @test_server.list_tools()
    async def list_tools():
        return [Tool(
            name="observed_identity",
            description="Return test identity",
            inputSchema={"type": "object", "properties": {}},
        )]

    @test_server.call_tool()
    async def call_tool(name, arguments):
        return [TextContent(
            type="text",
            text=json.dumps({"observed": policy.get_current_client_ip()}),
        )]

    class SplitRequestIdentity(httpx.Auth):
        def auth_flow(self, request):
            if request.url.path == "/sse":
                request.headers["x-forwarded-for"] = "198.51.100.80"
            else:
                request.headers["x-forwarded-for"] = "203.0.113.200"
            yield request

    app = transport.create_app(test_server, "127.0.0.1", 0)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="error",
    ))
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started
    try:
        async with sse_client(
            f"http://127.0.0.1:{port}/sse",
            auth=SplitRequestIdentity(),
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("observed_identity", {})
                payload = json.loads(result.content[0].text)
        assert payload == {"observed": "198.51.100.80"}
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)
