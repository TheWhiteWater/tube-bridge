"""Addendum contract for the immutable v1.1.5 metadata-quality patch."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

from tube_bridge.server import HELP_TEXT, TOOL_CATALOG, VERSION, server


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "1.1.5"
REGISTRY_NAME = "io.github.TheWhiteWater/tube-bridge"


def test_v1_1_5_identity_is_consistent_across_public_metadata():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    plugin = json.loads((ROOT / "plugin.json").read_text())
    registry = json.loads((ROOT / "server.json").read_text())

    assert project["project"]["version"] == RELEASE_VERSION
    assert plugin["version"] == RELEASE_VERSION
    assert registry["version"] == RELEASE_VERSION
    assert registry["packages"][0]["version"] == RELEASE_VERSION
    assert VERSION == HELP_TEXT["version"] == RELEASE_VERSION
    assert server.create_initialization_options().server_version == RELEASE_VERSION


def test_v1_1_5_ships_the_public_tool_metadata_quality_contract():
    tools = {tool.name: tool for tool in TOOL_CATALOG}

    assert len(tools) == 17
    assert all(tool.annotations is not None for tool in tools.values())
    assert tools["youtube_get_playlist"].annotations.readOnlyHint is True
    assert tools["youtube_get_playlist"].annotations.openWorldHint is True
    assert tools["corpus_add"].annotations.destructiveHint is True
    assert tools["corpus_add"].annotations.idempotentHint is False
    assert tools["corpus_delete"].annotations.destructiveHint is True
    assert "not channel uploads or keyword search" in tools["youtube_get_playlist"].description
    assert "audience reactions" in tools["youtube_get_comments"].description


def test_v1_1_5_glama_and_download_metadata_remain_public_and_credential_free():
    glama = json.loads((ROOT / "glama.json").read_text())
    readme = (ROOT / "README.md").read_text()

    assert glama == {
        "$schema": "https://glama.ai/mcp/schemas/server.json",
        "maintainers": ["TheWhiteWater"],
    }
    assert "https://img.shields.io/pypi/dw/tube-bridge.svg" in readme
    assert "https://pypistats.org/packages/tube-bridge" in readme
    assert "token" not in json.dumps(glama).lower()


def test_v1_1_5_release_notes_are_bounded_and_do_not_claim_an_external_score():
    notes = (ROOT / "docs/releases/v1.1.5.md").read_text()

    assert notes.startswith("# tube-bridge v1.1.5\n")
    assert REGISTRY_NAME in notes
    assert "ToolAnnotations" in notes
    assert "17 tools" in notes
    assert "pip install tube-bridge==1.1.5" in notes
    assert "does not guarantee a particular Glama score" in notes
    assert "hosted service" in notes


def test_v1_1_4_release_notes_remain_immutable_history():
    previous = (ROOT / "docs/releases/v1.1.4.md").read_text()

    assert previous.startswith("# tube-bridge v1.1.4\n")
    assert REGISTRY_NAME in previous
    assert "CallToolResult(isError=True)" in previous
    assert "raw yt-dlp stderr" in previous
    assert "pip install tube-bridge==1.1.4" in previous
