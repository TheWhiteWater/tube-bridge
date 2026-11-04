"""Historical contract retained from the immutable v1.1.6 native Pi packaging patch."""

from __future__ import annotations

import json
from pathlib import Path

from tube_bridge.server import TOOL_CATALOG


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_NAME = "io.github.TheWhiteWater/tube-bridge"
PI_SOURCE = "git:github.com/TheWhiteWater/tube-bridge@v1.1.6"


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
