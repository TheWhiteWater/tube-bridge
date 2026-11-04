"""Release contract for the immutable v1.1.7 arm64 container release."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

from tube_bridge.server import HELP_TEXT, TOOL_CATALOG, VERSION, server


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "1.1.7"
REGISTRY_NAME = "io.github.TheWhiteWater/tube-bridge"
PI_SOURCE = "git:github.com/TheWhiteWater/tube-bridge@v1.1.7"


def test_v1_1_7_identity_is_consistent_across_public_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    bundle = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    assert project["project"]["version"] == RELEASE_VERSION
    assert plugin["version"] == RELEASE_VERSION
    assert registry["version"] == RELEASE_VERSION
    assert registry["packages"][0]["version"] == RELEASE_VERSION
    assert package["version"] == RELEASE_VERSION
    assert lock["version"] == RELEASE_VERSION
    assert lock["packages"][""]["version"] == RELEASE_VERSION
    assert bundle["version"] == RELEASE_VERSION
    assert VERSION == HELP_TEXT["version"] == RELEASE_VERSION
    assert server.create_initialization_options().server_version == RELEASE_VERSION


def test_v1_1_7_release_notes_state_platforms_and_preview_boundary() -> None:
    notes = (ROOT / "docs/releases/v1.1.7.md").read_text(encoding="utf-8")

    assert notes.startswith("# tube-bridge v1.1.7\n")
    assert REGISTRY_NAME in notes
    assert "`linux/amd64`" in notes and "`linux/arm64`" in notes
    assert "physical Raspberry Pi" in notes
    assert "17 MCP tools" in notes
    assert "TUBE_BRIDGE_EXPERIMENTAL_RESEARCH_ARTIFACTS=1" in notes
    assert "MCPB" in notes
    assert "pip install tube-bridge==1.1.7" in notes
    assert "ghcr.io/thewhitewater/tube-bridge:1.1.7" in notes
    assert PI_SOURCE in notes


def test_v1_1_7_readme_uses_the_immutable_pi_release_source() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "pip install tube-bridge==1.1.7" in readme
    assert f"pi install {PI_SOURCE}" in readme
    assert f"pi remove {PI_SOURCE}" in readme


def test_v1_1_7_keeps_the_default_runtime_at_17_tools() -> None:
    assert len(TOOL_CATALOG) == 17
