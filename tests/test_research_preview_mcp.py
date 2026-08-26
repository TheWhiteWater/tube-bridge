"""Frozen MCP registration, dispatch, and process-level preview-gate contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

from tube_bridge.server import _handle_tool


@pytest.mark.parametrize(
    ("tool_name", "arguments", "handler_name", "expected_args"),
    [
        ("research_templates_list", {}, "research_templates", ()),
        (
            "research_scaffold_create",
            {
                "template_id": "structured-source-v1",
                "target": {"type": "video", "video_id": "abcdefghijk"},
            },
            "research_scaffold_create",
            (
                "structured-source-v1",
                {"type": "video", "video_id": "abcdefghijk"},
            ),
        ),
        (
            "research_artifact_get",
            {"artifact_id": "rart_123", "revision": 2},
            "research_artifact_get",
            ("rart_123", 2),
        ),
        (
            "research_artifact_save",
            {
                "artifact_id": "rart_123",
                "expected_revision": 2,
                "agent_fields": {"metadata_annotation": {"completion": "unfilled"}},
                "author": {"type": "agent", "name": "client"},
            },
            "research_artifact_save",
            (
                "rart_123",
                2,
                {"metadata_annotation": {"completion": "unfilled"}},
                {"type": "agent", "name": "client"},
            ),
        ),
        (
            "research_artifacts_list",
            {"target_type": "video", "target_id": "abcdefghijk"},
            "research_artifacts_list",
            ("video", "abcdefghijk", None),
        ),
        (
            "research_artifact_export",
            {"artifact_id": "rart_123", "format": "json"},
            "research_artifact_export",
            ("rart_123", "json"),
        ),
    ],
)
@pytest.mark.asyncio
async def test_research_tool_dispatch(
    monkeypatch, tool_name, arguments, handler_name, expected_args
) -> None:
    import tube_bridge.server as server_mod

    handler = AsyncMock(return_value={"ok": tool_name})
    monkeypatch.setattr(server_mod, handler_name, handler)
    result = await _handle_tool(tool_name, arguments)
    assert result == {"ok": tool_name}
    handler.assert_awaited_once_with(*expected_args)


def _subprocess_tool_names(preview: bool) -> list[str]:
    env = dict(os.environ)
    if preview:
        env["TUBE_BRIDGE_EXPERIMENTAL_RESEARCH_ARTIFACTS"] = "1"
    else:
        env.pop("TUBE_BRIDGE_EXPERIMENTAL_RESEARCH_ARTIFACTS", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import asyncio,json; "
                "from tube_bridge.server import list_tools; "
                "print(json.dumps([t.name for t in asyncio.run(list_tools())]))"
            ),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_process_level_preview_gate_preserves_release_default() -> None:
    default_names = _subprocess_tool_names(preview=False)
    preview_names = _subprocess_tool_names(preview=True)
    assert len(default_names) == 17
    assert len(preview_names) == 23
    assert set(default_names) < set(preview_names)
    assert {
        "research_templates_list",
        "research_scaffold_create",
        "research_artifact_get",
        "research_artifact_save",
        "research_artifacts_list",
        "research_artifact_export",
    } == set(preview_names) - set(default_names)
