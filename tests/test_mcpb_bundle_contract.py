"""Frozen MCPB v0.4 UV bundle contract for tube-bridge.

Grounded in .brainops/references/mcpb-manifest-v0.4.schema.json and the
official hello-world UV example. The repository root is the bundle root.
The RED run fails only because manifest.json and scripts/build-mcpb.py do
not exist yet; every import in this module already resolves.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

from tube_bridge.server import TOOL_CATALOG

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = PROJECT_ROOT / "manifest.json"
BUILDER = PROJECT_ROOT / "scripts" / "build-mcpb.py"

CONFIG_NAMES = ("YOUTUBE_API_KEY", "TUBE_BRIDGE_PROXY", "TUBE_BRIDGE_CACHE")
MASKED_NAMES = ("YOUTUBE_API_KEY", "TUBE_BRIDGE_PROXY")
EXPECTED_CATALOG = {tool.name: tool.description for tool in TOOL_CATALOG}

ROOT_FILES = ("manifest.json", "pyproject.toml", "README.md", "LICENSE", "server.py")
FORBIDDEN_FRAGMENTS = (
    ".brainops", "PROJECT_VISION.md", "operator/", "plugin.json", "mcp.json",
    "skills/", "requirements-release.txt",
)
DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")


def _pyproject_version() -> str:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return project["project"]["version"]


def _load_manifest() -> dict:
    assert MANIFEST.is_file(), "manifest.json does not exist (implementation pending)"
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _build(tmp: Path) -> Path:
    assert BUILDER.is_file(), "scripts/build-mcpb.py does not exist (implementation pending)"
    out = tmp / "out"
    out.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, str(BUILDER), "--output-dir", str(out)],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    archives = sorted(out.glob("*.mcpb"))
    assert len(archives) == 1, f"expected one .mcpb, got {[a.name for a in archives]}"
    return archives[0]


def test_manifest_targets_mcpb_v04_uv_runtime() -> None:
    manifest = _load_manifest()
    assert manifest["manifest_version"] == "0.4"
    assert manifest["version"] == _pyproject_version()
    server = manifest["server"]
    assert server["type"] == "uv"
    assert server["entry_point"] == "server.py"
    mcp_config = server["mcp_config"]
    assert mcp_config["command"] == "uv"
    assert mcp_config["args"] == ["run", "--directory", "${__dirname}", "server.py"]


def test_manifest_tools_match_current_catalog_exactly() -> None:
    tools = _load_manifest().get("tools", [])
    assert len(tools) == 17
    by_name = {tool["name"]: tool for tool in tools}
    assert set(by_name) == set(EXPECTED_CATALOG)
    for name, description in EXPECTED_CATALOG.items():
        assert by_name[name].get("description") == description, name


def test_manifest_user_config_maps_optional_env_refs() -> None:
    manifest = _load_manifest()
    user_config = manifest.get("user_config", {})
    assert set(user_config) == set(CONFIG_NAMES)
    for name in MASKED_NAMES:
        assert user_config[name].get("sensitive") is True, name
    assert user_config["TUBE_BRIDGE_CACHE"].get("sensitive") is not True
    env = manifest["server"]["mcp_config"].get("env", {})
    assert set(env) == set(CONFIG_NAMES)
    for name in CONFIG_NAMES:
        assert re.fullmatch(r"\$\{[^}]+\}", env[name]) and name in env[name], name


def test_manifest_long_description_documents_local_bundle() -> None:
    text = _load_manifest().get("long_description", "").lower()
    assert any(token in text for token in ("self-hosted", "local"))
    assert "ffmpeg" in text
    assert "external" in text
    assert "embedding" in text
    assert "download" in text


def test_build_mcpb_emits_root_level_bundle(tmp_path: Path) -> None:
    archive = _build(tmp_path)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    assert {n.split("/", 1)[0] for n in names} == {*ROOT_FILES, "tube_bridge"}
    for required in ROOT_FILES:
        assert required in names
    assert "tube_bridge/server.py" in names
    assert "tube_bridge/cli.py" in names


def test_build_mcpb_excludes_non_bundle_paths(tmp_path: Path) -> None:
    archive = _build(tmp_path)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
    for name in names:
        assert not any(fragment in name for fragment in FORBIDDEN_FRAGMENTS), name
        assert not name.endswith(DB_SUFFIXES), name
    assert not any("__pycache__" in n or n.endswith((".pyc", ".pyo")) for n in names)


def test_build_mcpb_contains_no_host_specific_literals(tmp_path: Path) -> None:
    archive = _build(tmp_path)
    home = str(Path.home())
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if name.endswith((".py", ".json", ".toml", ".md")):
                assert home not in zf.read(name).decode("utf-8", errors="ignore"), name


def test_build_mcpb_is_deterministic(tmp_path: Path) -> None:
    first = _build(tmp_path / "a")
    second = _build(tmp_path / "b")
    assert first.read_bytes() == second.read_bytes()
