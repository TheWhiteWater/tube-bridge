"""Frozen MCP contract for the ephemeral youtube_get_frame tool."""

import base64
import json
from pathlib import Path
import tomllib

import pytest
from mcp.types import ImageContent, TextContent

from tube_bridge.youtube.frame import ExtractedFrame


JPEG = b"\xff\xd8public-frame\xff\xd9"


def _artifact(data: bytes = JPEG) -> ExtractedFrame:
    return ExtractedFrame(
        video_id="H6lZ182QaVk",
        requested_timestamp_ms=30_000,
        mime_type="image/jpeg",
        data=data,
        sha256="a" * 64,
    )


def test_frame_tool_minor_version_is_coherent_across_runtime_and_plugin():
    from tube_bridge.server import HELP_TEXT, server

    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    plugin = json.loads((root / "plugin.json").read_text())
    assert project["version"] == plugin["version"] == HELP_TEXT["version"] == "1.1.1"
    assert server.create_initialization_options().server_version == "1.1.1"


def test_frame_tool_schema_is_single_image_and_bounded():
    from tube_bridge.server import TOOL_CATALOG

    tools = {tool.name: tool for tool in TOOL_CATALOG}
    assert len(tools) == 17
    schema = tools["youtube_get_frame"].inputSchema
    assert schema["required"] == ["url", "timestamp_ms"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["timestamp_ms"] == {
        "type": "integer",
        "minimum": 0,
        "description": "Frame timestamp in integer milliseconds",
    }
    assert schema["properties"]["max_width"]["minimum"] == 64
    assert schema["properties"]["max_width"]["maximum"] == 1280
    assert "batch" not in schema["properties"]


@pytest.mark.asyncio
async def test_frame_tool_runs_blocking_extractor_off_event_loop(mocker):
    from tube_bridge import tools

    extract = mocker.patch(
        "tube_bridge.tools.frame_extractor.extract_frame", return_value=_artifact()
    )

    result = await tools.video_frame("H6lZ182QaVk", 30_000, 640)

    assert result == _artifact()
    extract.assert_called_once_with(
        "H6lZ182QaVk", timestamp_ms=30_000, max_width=640
    )


@pytest.mark.asyncio
async def test_frame_tool_rejects_oversize_image_and_public_width(mocker):
    from tube_bridge import tools

    extract = mocker.patch(
        "tube_bridge.tools.frame_extractor.extract_frame",
        return_value=_artifact(b"x" * 1_500_001),
    )
    with pytest.raises(RuntimeError, match="response limit"):
        await tools.video_frame("H6lZ182QaVk", 30_000, 640)
    with pytest.raises(ValueError, match="max_width"):
        await tools.video_frame("H6lZ182QaVk", 30_000, 1281)
    assert extract.call_count == 1


@pytest.mark.asyncio
async def test_frame_base64_payload_has_a_two_million_character_ceiling(mocker):
    from tube_bridge.server import call_tool

    mocker.patch(
        "tube_bridge.server.video_frame", return_value=_artifact(b"x" * 1_500_000)
    )
    content = await call_tool(
        "youtube_get_frame", {"url": "H6lZ182QaVk", "timestamp_ms": 30_000}
    )
    assert isinstance(content[1], ImageContent)
    assert len(content[1].data) == 2_000_000


@pytest.mark.asyncio
async def test_frame_dispatch_returns_metadata_then_mcp_image(mocker):
    from tube_bridge.server import call_tool

    video_frame = mocker.patch(
        "tube_bridge.server.video_frame", return_value=_artifact()
    )

    content = await call_tool(
        "youtube_get_frame",
        {"url": "https://youtu.be/H6lZ182QaVk", "timestamp_ms": 30_000},
    )

    video_frame.assert_awaited_once_with("H6lZ182QaVk", 30_000, 640)
    assert len(content) == 2
    assert isinstance(content[0], TextContent)
    metadata = json.loads(content[0].text)
    assert metadata == {
        "video_id": "H6lZ182QaVk",
        "requested_timestamp_ms": 30_000,
        "actual_timestamp_ms": None,
        "timestamp_accuracy": "best_effort_frame_boundary",
        "mime_type": "image/jpeg",
        "bytes": len(JPEG),
        "sha256": "a" * 64,
        "retention": "ephemeral",
    }
    assert isinstance(content[1], ImageContent)
    assert content[1].mimeType == "image/jpeg"
    assert base64.b64decode(content[1].data) == JPEG
