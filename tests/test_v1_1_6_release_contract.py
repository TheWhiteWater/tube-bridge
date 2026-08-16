"""Release contract for the immutable v1.1.6 native Pi packaging patch."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

from tube_bridge.server import HELP_TEXT, TOOL_CATALOG, VERSION, server


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "1.1.6"
REGISTRY_NAME = "io.github.TheWhiteWater/tube-bridge"
PI_SOURCE = "git:github.com/TheWhiteWater/tube-bridge@v1.1.6"


def test_v1_1_6_identity_is_consistent_across_public_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))

    assert project["project"]["version"] == RELEASE_VERSION
    assert plugin["version"] == RELEASE_VERSION
    assert registry["version"] == RELEASE_VERSION
    assert registry["packages"][0]["version"] == RELEASE_VERSION
    assert package["version"] == RELEASE_VERSION
    assert lock["version"] == RELEASE_VERSION
    assert lock["packages"][""]["version"] == RELEASE_VERSION
    assert VERSION == HELP_TEXT["version"] == RELEASE_VERSION
    assert server.create_initialization_options().server_version == RELEASE_VERSION


def test_v1_1_6_release_notes_define_the_bounded_packaging_scope() -> None:
    notes = (ROOT / "docs/releases/v1.1.6.md").read_text(encoding="utf-8")

    assert notes.startswith("# tube-bridge v1.1.6\n")
    assert REGISTRY_NAME in notes
    assert PI_SOURCE in notes
    assert "17 MCP tools" in notes
    assert "pip install tube-bridge==1.1.6" in notes
    assert "ghcr.io/thewhitewater/tube-bridge:1.1.6" in notes
    assert "does not install Python or ffmpeg" in notes
    assert "does not add or rename MCP tools" in notes
    assert "hosted service" in notes


def test_v1_1_6_readme_uses_the_immutable_pi_release_source() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert f"pi install {PI_SOURCE}" in readme
    assert f"pi remove {PI_SOURCE}" in readme
    assert "does not install Python or ffmpeg" in readme


def test_v1_1_6_preserves_the_public_runtime_and_native_pi_boundary() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    names = sorted(tool.name for tool in TOOL_CATALOG)

    assert len(names) == 17
    assert package["private"] is True
    assert package["pi"] == {
        "extensions": ["./extensions/pi.ts"],
        "skills": ["./skills"],
    }
    assert package["dependencies"] == {"@modelcontextprotocol/sdk": "1.30.0"}
    assert (ROOT / "extensions/pi.ts").is_file()
    assert (ROOT / "skills/tube-bridge-research/SKILL.md").is_file()
