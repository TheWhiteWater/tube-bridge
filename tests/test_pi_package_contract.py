"""Public Pi package contract for the canonical tube-bridge capability root."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_JSON = PROJECT_ROOT / "package.json"
PI_EXTENSION = PROJECT_ROOT / "extensions" / "pi.ts"
NODE_SMOKE = PROJECT_ROOT / "tests" / "pi_package_smoke.test.mjs"


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_pi_package_loads_the_canonical_extension_and_skill() -> None:
    package = _json(PACKAGE_JSON)
    plugin = _json(PROJECT_ROOT / "plugin.json")
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert package["name"] == "tube-bridge"
    assert package["private"] is True
    assert package["version"] == plugin["version"] == project["project"]["version"] == "1.1.6"
    assert "pi-package" in package["keywords"]
    assert package["pi"] == {
        "extensions": ["./extensions/pi.ts"],
        "skills": ["./skills"],
    }
    assert package["dependencies"] == {"@modelcontextprotocol/sdk": "1.30.0"}
    assert package["peerDependencies"] == {
        "@earendil-works/pi-coding-agent": "*",
        "typebox": "*",
    }
    assert package["peerDependenciesMeta"] == {
        "@earendil-works/pi-coding-agent": {"optional": True},
        "typebox": {"optional": True},
    }
    assert package["scripts"]["test:pi"] == (
        "node --import tsx --test tests/pi_package_smoke.test.mjs"
    )
    assert package["devDependencies"] == {
        "tsx": "4.23.12",
        "typebox": "1.1.38",
    }
    assert (PROJECT_ROOT / "package-lock.json").is_file()


def test_pi_extension_uses_canonical_manifests_and_package_relative_paths() -> None:
    source = PI_EXTENSION.read_text(encoding="utf-8")

    assert 'new URL("..", import.meta.url)' in source
    assert 'new URL("../plugin.json", import.meta.url)' in source
    assert 'new URL("../mcp.json", import.meta.url)' in source
    assert "StdioClientTransport" in source
    assert "loadPortableServerConfig" in source
    assert "cwd: server.cwd" in source
    assert "command: server.command" in source
    assert "args: server.args" in source
    assert "tube_bridge_status" in source
    assert "tube-bridge-reconnect" in source
    assert "tube-bridge-selftest" in source
    assert "session_shutdown" in source
    assert "MAX_IMAGE_DATA_CHARS" in source
    assert "MAX_TEXT_BYTES" in source
    assert "MAX_TEXT_LINES" in source

    forbidden = {
        "absolute Linux user path": r"/home/[A-Za-z0-9._-]+/",
        "absolute macOS user path": r"/Users/[A-Za-z0-9._-]+/",
        "private Railway host": r"[A-Za-z0-9.-]+\.railway\.app",
        "private Railway control": r"\brailway\b",
        "private static bearer": r"TUBE_BRIDGE_AUTH_KEY",
        "private operator surface": r"operator/claude-gateway",
        "local orchestration": r"BRAINOPS_[A-Z0-9_]+",
        "whole environment spread": r"\.\.\.process\.env",
    }
    for label, pattern in forbidden.items():
        assert not re.search(pattern, source, re.IGNORECASE), label


def test_pi_adapter_has_a_real_host_smoke() -> None:
    smoke = NODE_SMOKE.read_text(encoding="utf-8")

    assert "expected status plus 17 MCP tools" in smoke
    assert "tube_bridge_tube_bridge_help" in smoke
    assert "tube-bridge-reconnect" in smoke
    assert "tube-bridge-selftest" in smoke
    assert "1.1.6" in smoke
    assert "session_shutdown" in smoke
