"""Parameterized dispatch tests for all 17 MCP tools with exact call-argument
verification.

Every operation handler (16 handlers + 1 help branch) is tested with mocked
upstreams. Each test asserts:
- The handler was called exactly once
- The exact awaited call arguments match the dispatch code, including defaults
  and extract_video_id transformation where applicable

All tests are offline — no live YouTube, embedding models, or Data API v3.
"""

import asyncio
from unittest.mock import AsyncMock

from mcp.types import CallToolResult
import pytest


# ---------------------------------------------------------------------------
# Helper: mock a handler at its server import path, dispatch, verify args
# ---------------------------------------------------------------------------

async def _dispatch_and_assert(
    mocker, tool_name, dispatch_args, patch_path, expected_handler_args,
    expected_extract_video_id_arg=None,
):
    """Patch handler (and optionally extract_video_id), dispatch, assert calls.

    Args:
        mocker: pytest-mock fixture
        tool_name: tool name for _handle_tool
        dispatch_args: dict of args to pass to _handle_tool
        patch_path: "tube_bridge.server.<handler_name>" to mock
        expected_handler_args: tuple of expected positional args to handler
        expected_extract_video_id_arg: if set, also mock extract_video_id
            and assert it was called with this arg
    """
    from tube_bridge.server import _handle_tool

    sentinel = {"dispatched": tool_name, "status": "ok"}
    mock_handler = mocker.patch(patch_path, new_callable=AsyncMock)
    mock_handler.return_value = sentinel

    extract_mock = None
    if expected_extract_video_id_arg is not None:
        from tube_bridge.youtube.client import extract_video_id as real_extract
        # We want extract_video_id to work normally so the real value flows
        # into the handler mock. So we just spy on it rather than replace.
        extract_mock = mocker.patch(
            "tube_bridge.server.extract_video_id",
            side_effect=real_extract,
        )

    result = await _handle_tool(tool_name, dispatch_args)
    assert result == sentinel, f"Dispatch failed for {tool_name}: {result}"

    mock_handler.assert_awaited_once_with(*expected_handler_args)

    if extract_mock is not None:
        extract_mock.assert_called_once_with(expected_extract_video_id_arg)


# ---------------------------------------------------------------------------
# 1. youtube_search — passes query, limit (default 10), and full args dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_search(mocker):
    """youtube_search(args['query'], args.get('limit',10), args)"""
    await _dispatch_and_assert(
        mocker,
        "youtube_search",
        {"query": "cats", "limit": 5, "order": "date"},
        "tube_bridge.server.search",
        ("cats", 5, {"query": "cats", "limit": 5, "order": "date"}),
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_search_default_limit(mocker):
    """youtube_search with no limit → defaults to 10."""
    await _dispatch_and_assert(
        mocker,
        "youtube_search",
        {"query": "cats"},
        "tube_bridge.server.search",
        ("cats", 10, {"query": "cats"}),
    )


# ---------------------------------------------------------------------------
# 2. youtube_search_channels — query, limit (default 10), args
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_search_channels(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_search_channels",
        {"query": "tech", "limit": 3, "min_subscribers": 1000},
        "tube_bridge.server.search_channels",
        ("tech", 3, {"query": "tech", "limit": 3, "min_subscribers": 1000}),
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_search_channels_default_limit(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_search_channels",
        {"query": "tech"},
        "tube_bridge.server.search_channels",
        ("tech", 10, {"query": "tech"}),
    )


# ---------------------------------------------------------------------------
# 3. youtube_get_channel_info — channel_info(args['channel_id'])
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_channel_info(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_channel_info",
        {"channel_id": "UCtest123"},
        "tube_bridge.server.channel_info",
        ("UCtest123",),
    )


# ---------------------------------------------------------------------------
# 4. youtube_get_video_info — video_info(extract_video_id(args['url']))
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_video_info(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_video_info",
        {"url": "dQw4w9WgXcQ"},
        "tube_bridge.server.video_info",
        ("dQw4w9WgXcQ",),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_get_video_info_full_url(mocker):
    """extract_video_id called on full YouTube URL, result passed to handler."""
    await _dispatch_and_assert(
        mocker,
        "youtube_get_video_info",
        {"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
        "tube_bridge.server.video_info",
        ("dQw4w9WgXcQ",),
        expected_extract_video_id_arg="https://youtube.com/watch?v=dQw4w9WgXcQ",
    )


# ---------------------------------------------------------------------------
# 5. youtube_get_trending — trending(args.get('limit', 10))
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_trending_with_limit(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_trending",
        {"limit": 5},
        "tube_bridge.server.trending",
        (5,),
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_get_trending_default_limit(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_trending",
        {},
        "tube_bridge.server.trending",
        (10,),
    )


# ---------------------------------------------------------------------------
# 6. youtube_get_channel_videos — channel_videos(url, limit default 10)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_channel_videos(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_channel_videos",
        {"channel_url": "@testchannel", "limit": 5},
        "tube_bridge.server.channel_videos",
        ("@testchannel", 5),
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_get_channel_videos_default_limit(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_channel_videos",
        {"channel_url": "@testchannel"},
        "tube_bridge.server.channel_videos",
        ("@testchannel", 10),
    )


# ---------------------------------------------------------------------------
# 7. youtube_get_playlist — playlist(url, limit default 20)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_playlist(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_playlist",
        {"playlist_url": "https://youtube.com/playlist?list=PLtest"},
        "tube_bridge.server.playlist",
        ("https://youtube.com/playlist?list=PLtest", 20),
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_get_playlist_custom_limit(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_playlist",
        {"playlist_url": "https://youtube.com/playlist?list=PLtest", "limit": 50},
        "tube_bridge.server.playlist",
        ("https://youtube.com/playlist?list=PLtest", 50),
    )


# ---------------------------------------------------------------------------
# 8. youtube_get_transcript — transcript(extract_video_id(url), lang, timestamps)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_transcript_defaults(mocker):
    """lang=None, with_timestamps=False when not provided."""
    await _dispatch_and_assert(
        mocker,
        "youtube_get_transcript",
        {"url": "dQw4w9WgXcQ"},
        "tube_bridge.server.transcript",
        ("dQw4w9WgXcQ", None, False),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_get_transcript_full_args(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_transcript",
        {"url": "dQw4w9WgXcQ", "lang": "en", "with_timestamps": True},
        "tube_bridge.server.transcript",
        ("dQw4w9WgXcQ", "en", True),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


# ---------------------------------------------------------------------------
# 9. youtube_get_frame — video_frame(extract_video_id(url), timestamp_ms, width)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_frame_defaults(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_frame",
        {"url": "dQw4w9WgXcQ", "timestamp_ms": 30_000},
        "tube_bridge.server.video_frame",
        ("dQw4w9WgXcQ", 30_000, 640),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_get_frame_custom_width(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_frame",
        {"url": "dQw4w9WgXcQ", "timestamp_ms": 1234, "max_width": 1280},
        "tube_bridge.server.video_frame",
        ("dQw4w9WgXcQ", 1234, 1280),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


# ---------------------------------------------------------------------------
# 10. youtube_get_available_languages — available_languages(extract_video_id(url))
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_available_languages(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_available_languages",
        {"url": "dQw4w9WgXcQ"},
        "tube_bridge.server.available_languages",
        ("dQw4w9WgXcQ",),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


# ---------------------------------------------------------------------------
# 10. youtube_get_comments — comments(extract_video_id(url), max_results default 20)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_youtube_get_comments(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_comments",
        {"url": "dQw4w9WgXcQ", "max_results": 15},
        "tube_bridge.server.comments",
        ("dQw4w9WgXcQ", 15),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


@pytest.mark.asyncio
async def test_dispatch_youtube_get_comments_default_max(mocker):
    await _dispatch_and_assert(
        mocker,
        "youtube_get_comments",
        {"url": "dQw4w9WgXcQ"},
        "tube_bridge.server.comments",
        ("dQw4w9WgXcQ", 20),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


# ---------------------------------------------------------------------------
# 11. corpus_create — corpus_create(id, label default None)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_corpus_create(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_create",
        {"corpus_id": "test-corpus", "label": "Test Label"},
        "tube_bridge.server.corpus_create",
        ("test-corpus", "Test Label"),
    )


@pytest.mark.asyncio
async def test_dispatch_corpus_create_default_label(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_create",
        {"corpus_id": "test-corpus"},
        "tube_bridge.server.corpus_create",
        ("test-corpus", None),
    )


# ---------------------------------------------------------------------------
# 12. corpus_add — corpus_add(id, extract_video_id(url), force_reembed default False)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_corpus_add(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_add",
        {"corpus_id": "test-corpus", "url": "dQw4w9WgXcQ", "force_reembed": True},
        "tube_bridge.server.corpus_add",
        ("test-corpus", "dQw4w9WgXcQ", True),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


@pytest.mark.asyncio
async def test_dispatch_corpus_add_default_force(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_add",
        {"corpus_id": "test-corpus", "url": "dQw4w9WgXcQ"},
        "tube_bridge.server.corpus_add",
        ("test-corpus", "dQw4w9WgXcQ", False),
        expected_extract_video_id_arg="dQw4w9WgXcQ",
    )


# ---------------------------------------------------------------------------
# 13. corpus_search — corpus_search(id, query, top_k default 10)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_corpus_search(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_search",
        {"corpus_id": "test-corpus", "query": "climate", "top_k": 5},
        "tube_bridge.server.corpus_search",
        ("test-corpus", "climate", 5),
    )


@pytest.mark.asyncio
async def test_dispatch_corpus_search_default_top_k(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_search",
        {"corpus_id": "test-corpus", "query": "climate"},
        "tube_bridge.server.corpus_search",
        ("test-corpus", "climate", 10),
    )


# ---------------------------------------------------------------------------
# 14. corpus_list — corpus_list() no args
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_corpus_list(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_list",
        {},
        "tube_bridge.server.corpus_list",
        (),
    )


# ---------------------------------------------------------------------------
# 15. corpus_delete — corpus_delete(id)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_corpus_delete(mocker):
    await _dispatch_and_assert(
        mocker,
        "corpus_delete",
        {"corpus_id": "test-corpus"},
        "tube_bridge.server.corpus_delete",
        ("test-corpus",),
    )


# ---------------------------------------------------------------------------
# 16. tube_bridge_help — returns HELP_TEXT directly (16th branch, no handler)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_tube_bridge_help():
    """Help is the 16th branch — returns HELP_TEXT dict directly, no handler."""
    from tube_bridge.server import _handle_tool, HELP_TEXT

    result = await _handle_tool("tube_bridge_help", {})
    assert result is HELP_TEXT, "tube_bridge_help must return HELP_TEXT directly"
    assert isinstance(result, dict)
    assert result.get("server") == "tube-bridge"


# ---------------------------------------------------------------------------
# Unknown tool returns ValueError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_unknown_tool_raises_value_error():
    from tube_bridge.server import _handle_tool

    with pytest.raises(ValueError, match="Unknown tool"):
        await _handle_tool("nonexistent_tool_xyz", {})


# ---------------------------------------------------------------------------
# call_tool error handling — controlled MCP text responses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_tool_returns_error_for_unknown_tool():
    """call_tool wraps ValueError into JSON error."""
    import json
    from tube_bridge.server import call_tool

    result = await call_tool("unknown_tool_abc", {})
    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert len(result.content) == 1
    data = json.loads(result.content[0].text)
    assert data["code"] == "invalid_argument"
    assert data["source"] == "tube_bridge"


@pytest.mark.asyncio
async def test_call_tool_returns_error_for_runtime_error(mocker):
    """call_tool wraps RuntimeError into JSON error."""
    import json
    from tube_bridge.server import call_tool

    mocker.patch("tube_bridge.server.corpus_list",
                 side_effect=RuntimeError("simulated runtime failure"))

    result = await call_tool("corpus_list", {})
    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert len(result.content) == 1
    data = json.loads(result.content[0].text)
    assert data["code"] == "upstream_unavailable"
    assert data["source"] == "tube_bridge"
    assert data["retryable"] is False
    assert "simulated runtime failure" in data["error"]


@pytest.mark.asyncio
async def test_call_tool_returns_error_for_unexpected_exception(mocker):
    """call_tool wraps unexpected Exception into JSON error."""
    import json
    from tube_bridge.server import call_tool

    mocker.patch("tube_bridge.server.corpus_list",
                 side_effect=Exception("unexpected crash"))

    result = await call_tool("corpus_list", {})
    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert len(result.content) == 1
    data = json.loads(result.content[0].text)
    assert data == {
        "error": "Unexpected error",
        "code": "internal_error",
        "source": "tube_bridge",
        "retryable": False,
    }


# ---------------------------------------------------------------------------
# extract_video_id smoke (transformation used in dispatch for 5 tools)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_extract_video_id_bare_id_passthrough():
    """Short IDs pass through extract_video_id unchanged."""
    from tube_bridge.youtube.client import extract_video_id
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_dispatch_extract_video_id_from_url():
    """Full youtube URL extracts the video id."""
    from tube_bridge.youtube.client import extract_video_id
    assert extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
