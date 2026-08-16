"""Addendum contract for Glama profile and MCP tool metadata quality."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_glama_manifest_declares_public_maintainer():
    manifest_path = ROOT / "glama.json"

    assert manifest_path.is_file(), "glama.json must exist at the repository root"
    assert json.loads(manifest_path.read_text()) == {
        "$schema": "https://glama.ai/mcp/schemas/server.json",
        "maintainers": ["TheWhiteWater"],
    }


def test_readme_exposes_conservative_weekly_pypi_download_metric():
    readme = (ROOT / "README.md").read_text()

    assert "https://img.shields.io/pypi/dw/tube-bridge.svg" in readme
    assert "https://pypistats.org/packages/tube-bridge" in readme


def test_tool_annotations_disclose_side_effect_and_network_semantics():
    from tube_bridge.server import TOOL_CATALOG

    tools = {tool.name: tool for tool in TOOL_CATALOG}
    external_read = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
    expected = {
        name: external_read
        for name in tools
        if name.startswith("youtube_")
    }
    expected.update({
        "corpus_create": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
        "corpus_add": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "corpus_search": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "corpus_list": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "corpus_delete": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "tube_bridge_help": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    })

    assert set(expected) == set(tools)
    for name, annotations in expected.items():
        assert tools[name].annotations is not None, name
        assert tools[name].annotations.model_dump(exclude_none=True) == annotations


def test_lowest_scored_tool_descriptions_explain_selection_and_behavior():
    from tube_bridge.server import TOOL_CATALOG

    tools = {tool.name: tool for tool in TOOL_CATALOG}
    required_phrases = {
        "youtube_get_playlist": (
            "known youtube playlist",
            "not channel uploads or keyword search",
            "read-only and keyless",
            "ordered video records",
            "private, unavailable, or blocked",
        ),
        "youtube_get_channel_videos": (
            "known youtube channel",
            "not keyword search or channel metadata",
            "read-only and keyless",
            "video records",
            "missing or has no uploads",
        ),
        "youtube_get_comments": (
            "audience reactions",
            "not video metadata or transcripts",
            "read-only and requires `youtube_api_key`",
            "structured comment records",
            "comments are disabled",
        ),
        "youtube_get_trending": (
            "broad discovery",
            "not keyword search",
            "read-only",
            "keyless yt-dlp fallback",
            "results can change over time",
        ),
    }

    for name, phrases in required_phrases.items():
        description = tools[name].description.lower()
        missing = [phrase for phrase in phrases if phrase not in description]
        assert not missing, f"{name} description is missing: {missing}"


def test_corpus_add_description_discloses_forced_replacement_behavior():
    from tube_bridge.server import TOOL_CATALOG

    tool = next(tool for tool in TOOL_CATALOG if tool.name == "corpus_add")
    description = tool.description.lower()

    assert "skips an already-indexed video by default" in description
    assert "`force_reembed=true` deletes and replaces" in description
