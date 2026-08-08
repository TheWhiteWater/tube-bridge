"""Frozen RED integration/configuration contracts for WI-00029 demo mode."""

import argparse
import asyncio
import importlib
import json
from pathlib import Path

import pytest


def policy_module():
    return importlib.import_module("tube_bridge.demo_policy")


def ttl_module():
    return importlib.import_module("tube_bridge.demo_ttl")


@pytest.mark.asyncio
async def test_demo_mode_stdio_fails_closed(monkeypatch):
    policy_module()
    cli = importlib.import_module("tube_bridge.cli")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    args = argparse.Namespace(http=False, host="127.0.0.1", port=8080)
    with pytest.raises(RuntimeError, match="demo mode requires HTTP"):
        await cli._run(args)


@pytest.mark.asyncio
async def test_demo_http_disables_uvicorn_access_log(monkeypatch):
    policy_module()
    cli = importlib.import_module("tube_bridge.cli")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    captured = {}

    class FakeConfig:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    class FakeServer:
        def __init__(self, config):
            self.config = config

        async def serve(self):
            return None

    monkeypatch.setattr(cli, "create_app", lambda *a, **k: object())
    monkeypatch.setattr(cli.uvicorn, "Config", FakeConfig)
    monkeypatch.setattr(cli.uvicorn, "Server", FakeServer)
    args = argparse.Namespace(http=True, host="127.0.0.1", port=8080)
    await cli._run(args)
    assert captured["access_log"] is False


@pytest.mark.asyncio
async def test_self_hosted_http_keeps_normal_access_log_setting(monkeypatch):
    policy_module()
    cli = importlib.import_module("tube_bridge.cli")
    monkeypatch.delenv("TUBE_BRIDGE_DEMO_MODE", raising=False)
    captured = {}

    class FakeConfig:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    class FakeServer:
        def __init__(self, config):
            pass

        async def serve(self):
            return None

    monkeypatch.setattr(cli, "create_app", lambda *a, **k: object())
    monkeypatch.setattr(cli.uvicorn, "Config", FakeConfig)
    monkeypatch.setattr(cli.uvicorn, "Server", FakeServer)
    await cli._run(argparse.Namespace(http=True, host="127.0.0.1", port=8080))
    assert captured["access_log"] is True


@pytest.mark.asyncio
async def test_server_serializes_limit_error_without_ip(monkeypatch):
    policy = policy_module()
    server_mod = importlib.import_module("tube_bridge.server")

    async def raise_limit(name, args):
        raise policy.DemoDataApiLimitExceeded()

    monkeypatch.setattr(server_mod, "_handle_tool", raise_limit)
    content = await server_mod.call_tool("youtube_get_comments", {"url": "id"})
    payload = json.loads(content[0].text)
    assert payload == {
        "error": "demo_data_api_limit_exceeded",
        "message": "Disposable demo allowance exhausted for this process lifetime.",
        "limit": 5,
        "reset": "process_restart",
    }
    assert "ip" not in json.dumps(payload).lower()


@pytest.mark.asyncio
async def test_server_serializes_missing_identity_error(monkeypatch):
    policy = policy_module()
    server_mod = importlib.import_module("tube_bridge.server")

    async def raise_missing(name, args):
        raise policy.DemoClientIdentityUnavailable()

    monkeypatch.setattr(server_mod, "_handle_tool", raise_missing)
    content = await server_mod.call_tool("youtube_get_comments", {"url": "id"})
    payload = json.loads(content[0].text)
    assert payload["error"] == "demo_client_identity_unavailable"
    assert payload["reset"] == "send_request_through_demo_http_transport"


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"items": []}'


def test_api_boundary_counts_exact_real_urlopen_attempts(monkeypatch):
    policy = policy_module()
    api = importlib.import_module("tube_bridge.youtube.api")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")
    allowance = policy.DemoAllowance(salt=b"api-boundary-salt" * 2)
    monkeypatch.setattr(policy, "_allowance", allowance)
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(api.urllib.request, "urlopen", fake_urlopen)
    with policy.bind_client_ip("198.51.100.70"):
        for _ in range(5):
            assert api.api_call("videos", {"part": "snippet"}) == {"items": []}
        with pytest.raises(policy.DemoDataApiLimitExceeded):
            api.api_call("videos", {"part": "snippet"})
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_transport_lifespan_starts_and_stops_ttl_worker(monkeypatch):
    policy_module()
    ttl = ttl_module()
    transport = importlib.import_module("tube_bridge.transport")
    from tube_bridge.server import server
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    events = []
    monkeypatch.setattr(ttl, "start_demo_ttl_worker", lambda: events.append("start"))
    monkeypatch.setattr(ttl, "stop_demo_ttl_worker", lambda: events.append("stop"))
    app = transport.create_app(server, "127.0.0.1", 8080)
    received = iter([
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ])
    sent = []

    async def receive():
        return next(received)

    async def send(message):
        sent.append(message["type"])

    await app({"type": "lifespan"}, receive, send)
    assert events == ["start", "stop"]
    assert sent == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


@pytest.mark.asyncio
async def test_self_hosted_lifespan_never_starts_demo_ttl_worker(monkeypatch):
    policy_module()
    ttl = ttl_module()
    transport = importlib.import_module("tube_bridge.transport")
    from tube_bridge.server import server
    monkeypatch.delenv("TUBE_BRIDGE_DEMO_MODE", raising=False)
    events = []
    monkeypatch.setattr(ttl, "start_demo_ttl_worker", lambda: events.append("start"))
    monkeypatch.setattr(ttl, "stop_demo_ttl_worker", lambda: events.append("stop"))
    app = transport.create_app(server, "127.0.0.1", 8080)
    received = iter([
        {"type": "lifespan.startup"},
        {"type": "lifespan.shutdown"},
    ])

    async def receive():
        return next(received)

    async def send(message):
        return None

    await app({"type": "lifespan"}, receive, send)
    assert events == []


def test_demo_corpus_create_and_delete_wake_worker(monkeypatch, tmp_path):
    policy_module()
    ttl = ttl_module()
    corpus = importlib.import_module("tube_bridge.corpus")
    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setattr(corpus, "DB_PATH", tmp_path / "corpus.db")
    monkeypatch.setattr(corpus, "_get_embedding_model", lambda: (object(), 2))
    wakes = []
    monkeypatch.setattr(ttl, "wake_demo_ttl_worker", lambda: wakes.append("wake"))
    corpus.corpus_create("wake_contract")
    corpus.corpus_delete("wake_contract")
    assert wakes == ["wake", "wake"]


def test_help_describes_demo_policy_as_process_local_and_demo_only():
    policy_module()
    from tube_bridge.server import HELP_TEXT
    demo = HELP_TEXT["demo_policy"]
    assert demo["enabled_by"] == "TUBE_BRIDGE_DEMO_MODE=1"
    assert demo["data_api_operations_per_ip"] == 5
    assert demo["allowance_reset"] == "process_restart"
    assert demo["corpus_ttl_seconds"] == 600
    assert demo["self_hosted_affected"] is False


def test_tool_catalog_remains_exactly_sixteen():
    policy_module()
    from tube_bridge.server import TOOL_CATALOG
    assert len(TOOL_CATALOG) == 16
    assert len({tool.name for tool in TOOL_CATALOG}) == 16


def test_demo_policy_has_no_sqlite_or_file_persistence_code():
    source = Path("tube_bridge/demo_policy.py").read_text()
    assert "sqlite3" not in source
    assert "pathlib" not in source
    assert "open(" not in source
    assert "write_text" not in source
    assert "write_bytes" not in source


def test_demo_policy_does_not_log_identity_material():
    source = Path("tube_bridge/demo_policy.py").read_text().lower()
    forbidden = (
        "logger.info(client_ip",
        "logger.debug(client_ip",
        "print(client_ip",
        "logger.info(digest",
        "logger.debug(digest",
    )
    assert not any(value in source for value in forbidden)


async def _start_demo_server(monkeypatch, response_factory):
    import socket
    import uvicorn
    policy = policy_module()
    ttl = ttl_module()
    api = importlib.import_module("tube_bridge.youtube.api")
    transport = importlib.import_module("tube_bridge.transport")
    from tube_bridge.server import server as production_server

    monkeypatch.setenv("TUBE_BRIDGE_DEMO_MODE", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUST_PROXY_HEADERS", "1")
    monkeypatch.setenv("TUBE_BRIDGE_TRUSTED_PROXY_HOPS", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "deterministic-test-key")
    monkeypatch.setattr(ttl, "start_demo_ttl_worker", lambda: None)
    monkeypatch.setattr(ttl, "stop_demo_ttl_worker", lambda: None)
    monkeypatch.setattr(api.urllib.request, "urlopen", response_factory)
    monkeypatch.setattr(policy, "_allowance", policy.DemoAllowance(salt=b"real-mcp-api-salt" * 2))

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    app = transport.create_app(production_server, "127.0.0.1", port)
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="error",
    ))
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started
    return server, task, port, policy


class JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


@pytest.mark.asyncio
async def test_real_mcp_data_api_tool_allows_five_and_rejects_sixth(monkeypatch):
    calls = []

    def response_factory(request, timeout):
        calls.append(request.full_url)
        return JsonResponse({"items": []})

    server, task, port, policy = await _start_demo_server(monkeypatch, response_factory)
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    import httpx
    try:
        async with httpx.AsyncClient(headers={"x-forwarded-for": "198.51.100.90"}) as client:
            async with streamable_http_client(
                f"http://127.0.0.1:{port}/mcp", http_client=client,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    for _ in range(5):
                        result = await session.call_tool(
                            "youtube_get_comments", {"url": "dQw4w9WgXcQ"},
                        )
                        assert json.loads(result.content[0].text)["total_comments"] == 0
                    rejected = await session.call_tool(
                        "youtube_get_comments", {"url": "dQw4w9WgXcQ"},
                    )
        payload = json.loads(rejected.content[0].text)
        assert payload["error"] == "demo_data_api_limit_exceeded"
        assert len(calls) == 5
        assert policy.demo_metrics()["allowed_total"] == 5
        assert policy.demo_metrics()["rejected_total"] == 1
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)


@pytest.mark.asyncio
async def test_real_mcp_channel_search_success_consumes_two_operations(monkeypatch):
    calls = []

    def response_factory(request, timeout):
        calls.append(request.full_url)
        if "/search?" in request.full_url:
            return JsonResponse({
                "items": [{
                    "id": {"channelId": "UC_TEST"},
                    "snippet": {"title": "Channel", "description": "", "thumbnails": {}},
                }],
            })
        if "/channels?" in request.full_url:
            return JsonResponse({
                "items": [{
                    "id": "UC_TEST",
                    "statistics": {"subscriberCount": "10", "videoCount": "2", "viewCount": "30"},
                    "snippet": {"country": "NZ"},
                }],
            })
        raise AssertionError(request.full_url)

    server, task, port, policy = await _start_demo_server(monkeypatch, response_factory)
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    import httpx
    try:
        async with httpx.AsyncClient(headers={"x-forwarded-for": "198.51.100.91"}) as client:
            async with streamable_http_client(
                f"http://127.0.0.1:{port}/mcp", http_client=client,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "youtube_search_channels", {"query": "test", "limit": 1},
                    )
        payload = json.loads(result.content[0].text)
        assert payload["total_results"] == 1
        assert payload["channels"][0]["subscriber_count"] == 10
        assert len(calls) == 2
        assert policy.demo_metrics()["allowed_total"] == 2
        assert policy.demo_metrics()["rejected_total"] == 0
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)


def test_old_frozen_test_files_remain_byte_identical():
    import hashlib
    manifest = json.loads(Path(
        ".brainops/methodology/frozen-tests/"
        "frozen-tdd-wi-00028-core-publication-001-python.json"
    ).read_text())
    mismatches = []
    for item in manifest["test_files"]:
        actual = hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        if actual != item["sha256"]:
            mismatches.append(item["path"])
    assert mismatches == []
