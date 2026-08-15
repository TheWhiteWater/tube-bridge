"""Public contract for official MCP Registry publication."""

from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib

from tube_bridge.server import HELP_TEXT, VERSION, server


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_NAME = "io.github.TheWhiteWater/tube-bridge"
RELEASE_VERSION = "1.1.4"
PUBLISHER_VERSION = "1.8.1"
PUBLISHER_SHA256 = "a06c9096dcb9727c13555b6be26c7effa707b01f06a4c561ba7a3635443cf2cc"


def test_registry_release_identity_is_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))

    assert project["project"]["version"] == RELEASE_VERSION
    assert plugin["version"] == RELEASE_VERSION
    assert registry["version"] == RELEASE_VERSION
    assert VERSION == HELP_TEXT["version"] == RELEASE_VERSION
    assert server.create_initialization_options().server_version == RELEASE_VERSION


def test_server_json_describes_the_pypi_stdio_distribution() -> None:
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))

    assert registry == {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": REGISTRY_NAME,
        "title": "tube-bridge",
        "description": (
            "YouTube MCP server for search, transcripts, frames, comments, "
            "channels, and local semantic corpora."
        ),
        "repository": {
            "url": "https://github.com/TheWhiteWater/tube-bridge",
            "source": "github",
        },
        "websiteUrl": "https://github.com/TheWhiteWater/tube-bridge#readme",
        "version": RELEASE_VERSION,
        "packages": [
            {
                "registryType": "pypi",
                "registryBaseUrl": "https://pypi.org",
                "identifier": "tube-bridge",
                "version": RELEASE_VERSION,
                "runtimeHint": "uvx",
                "transport": {"type": "stdio"},
                "environmentVariables": [
                    {
                        "name": "YOUTUBE_API_KEY",
                        "description": (
                            "Optional YouTube Data API v3 key for comments, "
                            "channel tools, and higher-quality search."
                        ),
                        "isRequired": False,
                        "isSecret": True,
                    },
                    {
                        "name": "TUBE_BRIDGE_PROXY",
                        "description": (
                            "Optional HTTP(S) or SOCKS proxy URL for yt-dlp "
                            "and transcript requests."
                        ),
                        "isRequired": False,
                        "isSecret": True,
                    },
                    {
                        "name": "TUBE_BRIDGE_CACHE",
                        "description": "Optional directory for cache and corpus databases.",
                        "isRequired": False,
                        "format": "filepath",
                    },
                ],
            }
        ],
    }
    assert "remotes" not in registry


def test_package_and_container_prove_registry_ownership() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert f"<!-- mcp-name: {REGISTRY_NAME} -->" in readme
    assert (
        f'LABEL io.modelcontextprotocol.server.name="{REGISTRY_NAME}"'
        in dockerfile
    )


def test_readme_auth_example_cannot_be_mistaken_for_a_bearer_secret() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    bearer_literal = re.compile(
        r"Bearer\s+[A-Za-z0-9._~+/-]{20,}",
        re.IGNORECASE,
    )

    assert bearer_literal.search(readme) is None
    assert '"Authorization": "Bearer <your-key>"' in readme


def test_release_workflow_publishes_registry_metadata_after_pypi() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "publish-mcp-registry:" in workflow
    assert "needs: publish-pypi" in workflow
    assert "id-token: write" in workflow
    assert f"releases/download/v{PUBLISHER_VERSION}/mcp-publisher_linux_amd64.tar.gz" in workflow
    assert PUBLISHER_SHA256 in workflow
    assert "./mcp-publisher login github-oidc" in workflow
    assert "./mcp-publisher publish server.json" in workflow
    assert "MCP_GITHUB_TOKEN" not in workflow


def test_release_notes_describe_typed_error_security_scope() -> None:
    notes = (ROOT / "docs/releases/v1.1.4.md").read_text(encoding="utf-8")

    assert notes.startswith("# tube-bridge v1.1.4\n")
    assert REGISTRY_NAME in notes
    assert "CallToolResult(isError=True)" in notes
    assert "raw yt-dlp stderr" in notes
    assert "pip install tube-bridge==1.1.4" in notes
