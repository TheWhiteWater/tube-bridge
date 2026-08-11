"""Frozen public contract for the operator-authorized v1.1.1 patch release.

This release publishes the already-audited Corpus v1 ranking/result hardening.
It does not implement Corpus v2 or authorize a Railway deployment.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

from tube_bridge.server import HELP_TEXT, TOOL_CATALOG, VERSION, server


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_v1_1_1_identity_is_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    plugin = json.loads((ROOT / "plugin.json").read_text())

    assert project["project"]["version"] == "1.1.1"
    assert plugin["version"] == "1.1.1"
    assert VERSION == HELP_TEXT["version"] == "1.1.1"
    assert server.create_initialization_options().server_version == "1.1.1"
    assert len(TOOL_CATALOG) == 17


def test_v1_1_0_release_history_remains_immutable() -> None:
    notes = ROOT / "docs/releases/v1.1.0.md"
    receipt = json.loads(
        (
            ROOT
            / ".brainops/methodology/verification/verification-v1.1.0-publication.json"
        ).read_text()
    )

    assert hashlib.sha256(notes.read_bytes()).hexdigest() == (
        "97d3a75f350895616fe11543e356e19e6a0f6993e5220824da379bdcca064535"
    )
    assert _sha256(
        ".brainops/methodology/verification/verification-v1.1.0-publication.json"
    ) == "0025df3bfb32a49d6a9097340d99863b8ca46ab8efe69c88b544a4467ac2c32e"
    assert receipt["release"] == "v1.1.0"
    assert receipt["tag_commit"] == "f7afa9cce0c59753be8105c7931ec3a44f8ea59d"
    assert receipt["status"] == "passed"
    assert receipt["github_release"]["assets"] == {
        "tube_bridge-1.1.0-py3-none-any.whl": "sha256:ffad2bc8f30ddc2d8cd3b40b4535c8ecab1310697e4c03c99a5b4283bf0349de",
        "tube_bridge-1.1.0.tar.gz": "sha256:058686fa6ddcd98f0a08ba67d2e233eedc2f5fa50e2116430ffa6e1009051a6f",
        "tube-bridge-agent-plugin-1.1.0.zip": "sha256:e76accc86e6576464f360e80defda07821a198e21e15b6f3fbe13b004b02a2e3",
        "SHA256SUMS": "sha256:5c96404224b1234f67da95f52811d92c850c333ab42b10d3566093f54cd9aa6e",
    }


def test_audited_ranking_behavior_is_the_release_payload() -> None:
    assert _sha256("tests/test_corpus_search_ranking.py") == (
        "d831c0ed077ea0ee12bfe934a09c9b014b11ca6884b99fe6999f73d856d1a031"
    )
    assert _sha256("tests/test_corpus_search_ranking_addendum.py") == (
        "15d1520fbf42bd97345a58f6e4368c16415a8598a8ae2dbc0141d93be86bda0e"
    )


def test_release_scope_remains_self_hosted_only() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text().lower()
    runtime_source = "\n".join(
        path.read_text() for path in sorted((ROOT / "tube_bridge").rglob("*.py"))
    )

    railway_lines = [
        line.strip() for line in workflow.splitlines() if "railway" in line
    ]
    assert "publish-pypi:" in workflow
    assert "publish-container:" in workflow
    assert "github-release:" in workflow
    assert len(railway_lines) == 2
    assert any('"railway.toml"' in line for line in railway_lines)
    assert any(r"\.railway\.app" in line for line in railway_lines)
    assert _sha256("tests/test_self_hosted_only_contract.py") == (
        "db8be8841c43d945e6736980155b240fa17fc4afe994c3a7ab2c28284613927c"
    )
    assert _sha256("tests/test_private_endpoint_not_distributed.py") == (
        "13f0ca65d6bf11b651af669f266f22e263370a20c889a1708a90824f94a1b41d"
    )
    assert _sha256("scripts/verify-release-artifacts.py") == (
        "51d9fc8b0ff9bf342b3cee4e7d6cdab8ef09b50d5b2056cfcb8f5c8ff4791370"
    )
    assert "CorpusV2Store" not in runtime_source
    assert "corpus-v2.db" not in runtime_source


def test_release_test_supersession_is_explicit() -> None:
    decision = (ROOT / "docs/adr/005-v1.1.1-release-contract.md").read_text()

    assert "**Status:** Accepted" in decision
    assert (
        "Supersedes the current-version assertions in "
        "`tests/test_v1_0_3_release_contract.py`, "
        "`tests/test_agent_plugin_contract.py`, and "
        "`tests/test_frame_tool_contract.py`"
    ) in decision
    assert "tests/test_v1_1_1_release_contract.py" in decision
    assert "Historical v1.1.0 artifacts remain immutable" in decision


def test_v1_1_1_release_notes_state_the_exact_boundary() -> None:
    notes = (ROOT / "docs/releases/v1.1.1.md").read_text()

    assert notes.startswith("# tube-bridge v1.1.1\n")
    assert "tube-bridge-agent-plugin-1.1.1.zip" in notes
    assert "suppresses strict same-video temporal overlap" in notes
    assert "deterministic source-aware per-video caps with refill" in notes
    assert "cached titles and canonical YouTube timestamp URLs" in notes
    assert "Corpus v2 is not implemented by this release." in notes
    assert (
        "The private Railway service was not deployed or modified for this release."
        in notes
    )
    assert (
        "Public distribution is limited to GitHub Release, PyPI, and GHCR."
        in notes
    )
    assert "pip install tube-bridge==1.1.1" in notes
    assert "ghcr.io/thewhitewater/tube-bridge:1.1.1" in notes


def test_public_docs_mark_ranking_as_released_not_future() -> None:
    readme = (ROOT / "README.md").read_text()
    vision = (ROOT / "PROJECT_VISION.md").read_text()
    retrieval = (
        ROOT / "skills/tube-bridge-research/references/50-retrieval.md"
    ).read_text()

    assert "**Current release: v1.1.1**" in readme
    assert "future separately authorized patch release" not in readme
    assert "included in public v1.1.1" in retrieval
    assert "Current public release: `v1.1.1`" in vision
    assert "Current public release: `v1.1.0`" not in vision
