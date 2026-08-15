"""Portable Agent Plugins v1.0.0 package contract.

The repository root is the plugin root. These tests intentionally exercise the
portable files and a real stdio MCP handshake; they do not call YouTube.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
import zipfile

import pytest
import yaml

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tube_bridge.server import TOOL_CATALOG


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
EXPECTED_SKILLS = {"tube-bridge-research"}
EXPECTED_REFERENCES = {
    "START_HERE.md",
    "00-operating-model.md",
    "10-tool-selection.md",
    "20-source-capture.md",
    "30-corpus-storage.md",
    "40-corpus-processing.md",
    "50-retrieval.md",
    "60-evaluation.md",
    "FAQ.md",
    "GLOSSARY.md",
}
EXPECTED_METHODOLOGY = {
    "00-research-method.md",
    "01-evidence-protocol.md",
    "02-adversary-gates.md",
}
EXPECTED_EXAMPLES = {
    "01-one-video-source-capture.md",
    "02-shared-origin-is-not-independence.md",
    "03-absence-is-not-negative-evidence.md",
}
EXPECTED_CONTRACTS = {"corpus-v2-schema.sql"}
EXPECTED_TEMPLATES = {
    "research-brief.md",
    "research-state.md",
    "evidence-ledger.md",
    "hypothesis-matrix.md",
    "adversary-gate.md",
    "update-record.md",
    "final-synthesis.md",
    "source-comparison.md",
    "corpus-evaluation.md",
}
EXPECTED_TOOL_NAMES = sorted(tool.name for tool in TOOL_CATALOG)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def _load_json(name: str) -> dict:
    with (PROJECT_ROOT / name).open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def _parse_skill_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path} must start with YAML frontmatter"
    result = yaml.safe_load(match.group(1))
    assert isinstance(result, dict), f"{path} frontmatter must be a YAML object"
    return result


def test_plugin_manifest_targets_portable_v1_contract() -> None:
    manifest = _load_json("plugin.json")

    assert set(manifest) <= {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
    assert manifest["$schema"] == PLUGIN_SCHEMA
    assert manifest["name"] == "tube-bridge"
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["version"] == project["project"]["version"] == "1.1.4"
    assert manifest["license"] == "MIT"


def test_mcp_config_is_portable_secret_free_stdio() -> None:
    config = _load_json("mcp.json")

    assert set(config) == {"$schema", "mcpServers"}
    assert config["$schema"] == MCP_SCHEMA
    assert set(config["mcpServers"]) == {"tube-bridge"}

    server = config["mcpServers"]["tube-bridge"]
    assert set(server) == {"type", "command", "args", "env", "cwd"}
    assert server == {
        "type": "stdio",
        "command": "python3",
        "args": ["-m", "tube_bridge.cli"],
        "env": {"TUBE_BRIDGE_CACHE": "${PLUGIN_DATA}/cache"},
        "cwd": "${PLUGIN_ROOT}",
    }

    serialized = json.dumps(config)
    assert not any(pattern.search(serialized) for pattern in SECRET_PATTERNS)


def test_single_entry_skill_has_explicit_internal_information_architecture() -> None:
    skills_root = PROJECT_ROOT / "skills"
    discovered = {
        child.name
        for child in skills_root.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    }
    assert discovered == EXPECTED_SKILLS

    skill_root = skills_root / "tube-bridge-research"
    skill_path = skill_root / "SKILL.md"
    frontmatter = _parse_skill_frontmatter(skill_path)
    assert frontmatter["name"] == "tube-bridge-research"
    assert frontmatter.get("description")

    references = skill_root / "references"
    methodology = references / "methodology"
    examples = references / "examples"
    templates = skill_root / "assets" / "templates"
    contracts = skill_root / "assets" / "contracts"
    assert {path.name for path in references.glob("*.md")} == EXPECTED_REFERENCES
    assert {path.name for path in methodology.glob("*.md")} == EXPECTED_METHODOLOGY
    assert {path.name for path in examples.glob("*.md")} == EXPECTED_EXAMPLES
    assert {path.name for path in contracts.glob("*.sql")} == EXPECTED_CONTRACTS
    assert {path.name for path in templates.glob("*.md")} == EXPECTED_TEMPLATES

    entrypoint = skill_path.read_text(encoding="utf-8")
    required_paths = [
        *(references / filename for filename in sorted(EXPECTED_REFERENCES)),
        *(methodology / filename for filename in sorted(EXPECTED_METHODOLOGY)),
        *(examples / filename for filename in sorted(EXPECTED_EXAMPLES)),
        *(contracts / filename for filename in sorted(EXPECTED_CONTRACTS)),
        *(templates / filename for filename in sorted(EXPECTED_TEMPLATES)),
    ]
    for path in required_paths:
        assert path.read_text(encoding="utf-8").strip()
        assert path.relative_to(skill_root).as_posix() in entrypoint


def test_methodology_preserves_required_epistemic_contracts() -> None:
    root = PROJECT_ROOT / "skills" / "tube-bridge-research" / "references" / "methodology"
    required_terms = {
        "00-research-method.md": {
            "FRAME-LOCK", "frame_id", "prospectively", "evidence standard",
            "FACT", "SOURCE-CLAIM", "INFERENCE", "UNKNOWN",
            "distinguishing", "synthesis",
        },
        "01-evidence-protocol.md": {
            "source lineage", "independence", "timestamp", "negative evidence",
            "observation contract", "tool-observed", "probable semantic content",
            "authenticated verbatim", "registered_at", "achieved coverage",
            "resolved-claim ledger", "canonical source URI",
            "as_of", "review_due", "corpus", "retrieval",
        },
        "02-adversary-gates.md": {
            "arithmetic", "alternatives", "physical", "incentives",
            "PASS", "FAIL", "INCONCLUSIVE", "NOT APPLICABLE", "roll-up",
            "F1", "E1", "H1", "A1", "S1", "PASS with limitations",
            "mandatory-material", "preflight", "review_due", "fallback",
            "plausible", "repairable", "update",
        },
    }
    for filename, terms in required_terms.items():
        text = (root / filename).read_text(encoding="utf-8")
        lowered = text.lower()
        for term in terms:
            assert term.lower() in lowered, f"{filename} is missing {term!r}"


def test_all_relative_markdown_links_resolve_inside_the_skill() -> None:
    skill_root = PROJECT_ROOT / "skills" / "tube-bridge-research"
    for path in skill_root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for raw_target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            target = raw_target.split("#", 1)[0]
            if not target or "://" in target:
                continue
            resolved = (path.parent / target).resolve()
            assert resolved.is_relative_to(skill_root.resolve()), (path, raw_target)
            assert resolved.is_file(), (path, raw_target)


def test_portable_package_files_contain_no_secret_literals() -> None:
    files = [PROJECT_ROOT / "plugin.json", PROJECT_ROOT / "mcp.json"]
    files.extend(
        path
        for path in (PROJECT_ROOT / "skills").rglob("*")
        if path.is_file() and path.suffix in {".md", ".sql"}
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not any(pattern.search(text) for pattern in SECRET_PATTERNS), path


def test_dependency_contract_remains_co_located_with_plugin() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    lock = PROJECT_ROOT / "requirements-release.txt"
    assert lock.is_file()
    assert "--hash=sha256:" in lock.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_configured_stdio_server_exposes_unchanged_tool_catalog(tmp_path: Path) -> None:
    config = _load_json("mcp.json")
    server = config["mcpServers"]["tube-bridge"]

    env = dict(os.environ)
    env.pop("YOUTUBE_API_KEY", None)
    env.pop("TUBE_BRIDGE_AUTH_KEY", None)
    env["PLUGIN_ROOT"] = str(PROJECT_ROOT)
    env["PLUGIN_DATA"] = str(tmp_path)
    for key, value in server["env"].items():
        env[key] = value.replace("${PLUGIN_ROOT}", str(PROJECT_ROOT)).replace(
            "${PLUGIN_DATA}", str(tmp_path)
        )

    cwd = server["cwd"].replace("${PLUGIN_ROOT}", str(PROJECT_ROOT)).replace(
        "${PLUGIN_DATA}", str(tmp_path)
    )
    parameters = StdioServerParameters(
        command=server["command"],
        args=server["args"],
        env=env,
        cwd=cwd,
    )

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            response = await session.list_tools()

    assert sorted(tool.name for tool in response.tools) == EXPECTED_TOOL_NAMES
    assert len(response.tools) == 17


def test_release_builder_emits_complete_bounded_plugin_zip(tmp_path: Path) -> None:
    builder = PROJECT_ROOT / "scripts" / "build-agent-plugin.py"
    completed = subprocess.run(
        [sys.executable, str(builder), "--output-dir", str(tmp_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    archive_path = tmp_path / "tube-bridge-agent-plugin-1.1.4.zip"
    assert archive_path.is_file()
    root = "tube-bridge-agent-plugin-1.1.4"
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(f"{root}/plugin.json"))

    assert manifest["version"] == "1.1.4"
    assert {
        f"{root}/LICENSE",
        f"{root}/README.md",
        f"{root}/plugin.json",
        f"{root}/mcp.json",
        f"{root}/pyproject.toml",
        f"{root}/requirements-release.txt",
        f"{root}/skills/tube-bridge-research/SKILL.md",
        f"{root}/skills/tube-bridge-research/assets/contracts/corpus-v2-schema.sql",
        f"{root}/tube_bridge/cli.py",
        f"{root}/tube_bridge/server.py",
    } <= names
    assert not any("docs/methodology-inbox" in name for name in names)
    assert not any("/.brainops/" in name or "/.tme/" in name for name in names)
    assert not any(name.endswith((".pyc", ".pyo")) or "__pycache__" in name for name in names)

    scanner = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "verify-release-artifacts.py"), str(archive_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert scanner.returncode == 0, scanner.stderr
