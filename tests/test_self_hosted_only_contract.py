"""Frozen retirement contract for ADR-003 self-hosted-only product state."""

from contextlib import asynccontextmanager
import importlib.util
from pathlib import Path
import sqlite3

import httpx
import pytest
from mcp.server import Server

from tube_bridge import corpus as corpus_module
from tube_bridge import transport as transport_module
from tube_bridge.youtube import transcript as transcript_module
from youtube_transcript_api import TranscriptsDisabled


ROOT = Path(__file__).resolve().parents[1]
RETIRED_MODULES = ("oauth", "demo_policy", "demo_ttl")
RETIRED_ENV_NAMES = (
    "TUBE_BRIDGE_PUBLIC_BASE_URL",
    "TUBE_BRIDGE_OAUTH_SIGNING_KEY",
    "TUBE_BRIDGE_OAUTH_INVITES_JSON",
    "TUBE_BRIDGE_DEMO_MODE",
    "TUBE_BRIDGE_TRUST_PROXY_HEADERS",
    "TUBE_BRIDGE_TRUSTED_PROXY_HOPS",
    "TUBE_BRIDGE_CLIENT_IP_HEADER",
)


def test_retired_demo_and_oauth_modules_are_absent():
    for module in RETIRED_MODULES:
        assert importlib.util.find_spec(f"tube_bridge.{module}") is None
        assert not (ROOT / "tube_bridge" / f"{module}.py").exists()


def test_active_package_source_has_no_retired_deployment_configuration():
    source = "\n".join(
        path.read_text()
        for path in sorted((ROOT / "tube_bridge").rglob("*.py"))
    )
    for name in RETIRED_ENV_NAMES:
        assert name not in source
    assert "from .oauth import" not in source
    assert "from . import demo_policy" not in source
    assert "from . import demo_ttl" not in source


@pytest.mark.asyncio
async def test_private_http_keeps_static_bearer_and_has_no_demo_or_oauth_surface(monkeypatch):
    class FakeManager:
        def __init__(self, app, stateless):
            pass

        @asynccontextmanager
        async def run(self):
            yield

        async def handle_request(self, scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

    monkeypatch.setattr(transport_module, "StreamableHTTPSessionManager", FakeManager)
    monkeypatch.setenv("TUBE_BRIDGE_AUTH_KEY", "private-operator-key")
    app = transport_module.create_app(
        Server("self-hosted-only-contract"), "127.0.0.1", 8080
    )
    auth = {"authorization": "Bearer private-operator-key"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        health = await client.get("/health")
        unauthorized = await client.post("/mcp")
        authenticated = await client.post("/mcp", headers=auth)
        retired_oauth = [
            await client.get("/.well-known/oauth-protected-resource", headers=auth),
            await client.get("/.well-known/oauth-protected-resource/mcp", headers=auth),
            await client.get("/.well-known/oauth-authorization-server", headers=auth),
            await client.post("/oauth/register", headers=auth, json={}),
            await client.get("/oauth/authorize", headers=auth),
            await client.post("/oauth/authorize", headers=auth, data={}),
            await client.post("/oauth/token", headers=auth, data={}),
        ]

    assert health.status_code == 200
    body = health.json()
    assert body["auth"] == "enabled"
    assert "demo" not in body
    assert "auth_oauth" not in body
    assert unauthorized.status_code == 401
    assert authenticated.status_code == 204
    assert all(response.status_code == 404 for response in retired_oauth)


def test_existing_corpus_schema_remains_compatible_without_demo_mode(monkeypatch, tmp_path):
    database = tmp_path / "corpus.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE corpora ("
            "corpus_id TEXT PRIMARY KEY, label TEXT, embedding_model TEXT, created_at REAL)"
        )
    monkeypatch.setattr(corpus_module, "DB_PATH", database)
    monkeypatch.setattr(corpus_module, "_get_embedding_model", lambda: (object(), 384))

    created = corpus_module.corpus_create("personal", "Personal corpus")

    assert created["status"] == "created"
    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(corpora)")]
        row = connection.execute(
            "SELECT corpus_id, label, embedding_model, created_at, expires_at "
            "FROM corpora WHERE corpus_id='personal'"
        ).fetchone()
    assert columns == ["corpus_id", "label", "embedding_model", "created_at", "expires_at"]
    assert row[:3] == ("personal", "Personal corpus", "BAAI/bge-small-en-v1.5")
    assert isinstance(row[3], float)
    assert row[4] is None


def test_transcript_network_failure_remains_distinct_from_missing_captions(monkeypatch):
    class BrokenApi:
        def __init__(self):
            self.fetch_calls = 0

        def list(self, video_id):
            raise OSError("upstream unavailable")

        def fetch(self, video_id, languages=None):
            self.fetch_calls += 1
            raise AssertionError("implicit-language retry is unsafe")

    broken_api = BrokenApi()
    monkeypatch.setattr(transcript_module, "_api", broken_api)

    with pytest.raises(RuntimeError, match="OSError: upstream unavailable"):
        transcript_module.get_transcript("abcdefghijk")
    assert broken_api.fetch_calls == 0

    class MissingCaptionsApi:
        def list(self, video_id):
            raise TranscriptsDisabled(video_id)

        def fetch(self, video_id, languages=None):
            raise TranscriptsDisabled(video_id)

    monkeypatch.setattr(transcript_module, "_api", MissingCaptionsApi())
    with pytest.raises(RuntimeError) as error:
        transcript_module.get_transcript("abcdefghijk")
    assert str(error.value) == "No transcript found for video abcdefghijk"
