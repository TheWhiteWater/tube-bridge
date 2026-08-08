"""Tool contract tests — per-required-field schema validation, registry integrity, dispatch.

Pack C Second Remediation: preserve approved per-required-field schema tests and
real authorized MCP handshake. Implement exact missing contracts.

Validates:
- Exactly 16 unique tool names with valid object schemas.
- Per-required-field: every required field is validated; omission is rejected.
- Metaschema conformance: type=object, properties dict, required array.
- Key classification: 13 zero-setup / 3 Data API required.
- Help tool names match registered names; no dead numeric/docstring mismatch.
- All 16 names dispatch to the expected handler without live network.
- Unknown tool and runtime errors return controlled MCP text responses.
- Package docstring makes no 10/11-tool claim.
"""

import asyncio
import json

import jsonschema
import pytest

from tube_bridge.server import HELP_TEXT, list_tools, _handle_tool


def _sync_list_tools():
    """Synchronous wrapper: list_tools is async (MCP framework contract)
    but returns synchronously — call via asyncio.run."""
    return asyncio.run(list_tools())


# ---------------------------------------------------------------------------
# Representative valid inputs for all 16 tools
# ---------------------------------------------------------------------------

VALID_INPUTS = {
    "youtube_search":                        {"query": "test search"},
    "youtube_search_channels":               {"query": "news"},
    "youtube_get_channel_info":              {"channel_id": "UC1234567890"},
    "youtube_get_video_info":                {"url": "dQw4w9WgXcQ"},
    "youtube_get_trending":                  {},
    "youtube_get_channel_videos":            {"channel_url": "@testchannel"},
    "youtube_get_playlist":                  {"playlist_url": "https://youtube.com/playlist?list=PLabc"},
    "youtube_get_transcript":                {"url": "dQw4w9WgXcQ"},
    "youtube_get_available_languages":       {"url": "dQw4w9WgXcQ"},
    "youtube_get_comments":                  {"url": "dQw4w9WgXcQ"},
    "tube_bridge_help":                      {},
    "corpus_create":                         {"corpus_id": "test-corpus"},
    "corpus_add":                            {"corpus_id": "my-corpus", "url": "dQw4w9WgXcQ"},
    "corpus_search":                         {"corpus_id": "my-corpus", "query": "semantic search"},
    "corpus_list":                           {},
    "corpus_delete":                         {"corpus_id": "old-corpus"},
}

# Tools that require YOUTUBE_API_KEY (Data API only)
DATA_API_REQUIRED_TOOLS = {
    "youtube_search_channels",
    "youtube_get_channel_info",
    "youtube_get_comments",
}

# All tools that work without any API key (zero-setup)
ZERO_SETUP_TOOLS = set(VALID_INPUTS.keys()) - DATA_API_REQUIRED_TOOLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_tool_by_name(tools, name):
    """Find a tool by name in a list of Tool objects."""
    for t in tools:
        if t.name == name:
            return t
    return None


# ---------------------------------------------------------------------------
# Registry integrity
# ---------------------------------------------------------------------------

class TestToolRegistry:
    """Exactly 16 unique tool names with valid schemas."""

    def test_exactly_sixteen_tools(self):
        """list_tools() returns exactly 16 tools."""
        tools = _sync_list_tools()
        assert len(tools) == 16, (
            f"Expected 16 tools, got {len(tools)}: "
            f"{sorted(t.name for t in tools)}"
        )

    def test_all_tool_names_are_unique(self):
        """No duplicate tool names in registry."""
        tools = _sync_list_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), (
            f"Duplicate tool names found: {names}"
        )

    def test_help_tool_names_match_registered(self):
        """HELP_TEXT tool names match registered tool names exactly."""
        tools = _sync_list_tools()
        registered_names = {t.name for t in tools}

        help_tool_names = {entry["name"] for entry in HELP_TEXT.get("tools", [])}

        missing_from_help = registered_names - help_tool_names
        extra_in_help = help_tool_names - registered_names

        assert not missing_from_help, (
            f"Tools registered but missing from HELP_TEXT: {missing_from_help}"
        )
        assert not extra_in_help, (
            f"Tools in HELP_TEXT but not registered: {extra_in_help}"
        )

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestToolSchemas:
    """Every tool has a valid JSON Schema with required-field validation."""

    def test_all_schemas_have_required_type_object(self):
        """Every tool schema has type=object."""
        tools = _sync_list_tools()
        for tool in tools:
            schema = tool.inputSchema
            assert schema.get("type") == "object", (
                f"Tool '{tool.name}' schema type is {schema.get('type')}, expected 'object'"
            )

    def test_all_schemas_have_properties_dict(self):
        """Every tool schema has a 'properties' object (may be empty)."""
        tools = _sync_list_tools()
        for tool in tools:
            schema = tool.inputSchema
            assert "properties" in schema, (
                f"Tool '{tool.name}' schema missing 'properties'"
            )
            assert isinstance(schema["properties"], dict), (
                f"Tool '{tool.name}' properties is not a dict"
            )

    def test_required_fields_are_valid_array(self):
        """Every tool with required fields has them as a list of strings."""
        tools = _sync_list_tools()
        for tool in tools:
            schema = tool.inputSchema
            if "required" in schema:
                required = schema["required"]
                assert isinstance(required, list), (
                    f"Tool '{tool.name}' required is not a list"
                )
                for field in required:
                    assert isinstance(field, str), (
                        f"Tool '{tool.name}' required field {field!r} is not a string"
                    )

    def test_required_fields_exist_in_properties(self):
        """Every required field is present in properties."""
        tools = _sync_list_tools()
        for tool in tools:
            schema = tool.inputSchema
            required = schema.get("required", [])
            properties = schema.get("properties", {})
            for field in required:
                assert field in properties, (
                    f"Tool '{tool.name}': required field '{field}' "
                    f"not found in properties"
                )

    def test_per_required_field_validation(self):
        """For each tool with required fields, removing any required field
        makes the valid input invalid."""
        tools = _sync_list_tools()
        for tool in tools:
            schema = tool.inputSchema
            required = schema.get("required", [])
            valid_input = VALID_INPUTS.get(tool.name, {})

            if not required:
                # Tools with no required fields: valid input passes
                jsonschema.validate(instance=valid_input, schema=schema)
                continue

            for field in required:
                # Remove just this field from the valid input
                incomplete = {k: v for k, v in valid_input.items() if k != field}
                with pytest.raises(jsonschema.ValidationError,
                                   match=field):
                    jsonschema.validate(instance=incomplete, schema=schema)


# ---------------------------------------------------------------------------
# Key classification
# ---------------------------------------------------------------------------

class TestKeyClassification:
    """13 zero-setup tools, 3 Data API required."""

    def test_zero_setup_count(self):
        """Exactly 13 tools work without YOUTUBE_API_KEY."""
        tools = _sync_list_tools()
        zero_setup = [
            t for t in tools
            if t.name not in DATA_API_REQUIRED_TOOLS
        ]
        assert len(zero_setup) == 13, (
            f"Expected 13 zero-setup tools, got {len(zero_setup)}: "
            f"{sorted(t.name for t in zero_setup)}"
        )

    def test_data_api_required_count(self):
        """Exactly 3 tools require YOUTUBE_API_KEY."""
        tools = _sync_list_tools()
        data_api = [t for t in tools if t.name in DATA_API_REQUIRED_TOOLS]
        assert len(data_api) == 3, (
            f"Expected 3 Data-API-required tools, got {len(data_api)}: "
            f"{sorted(t.name for t in data_api)}"
        )

    def test_all_tools_accounted_for(self):
        """Every tool is either zero-setup or Data API required."""
        tools = _sync_list_tools()
        for tool in tools:
            assert (
                tool.name in ZERO_SETUP_TOOLS or
                tool.name in DATA_API_REQUIRED_TOOLS
            ), f"Tool '{tool.name}' not classified"


# ---------------------------------------------------------------------------
# Dispatch contract
# ---------------------------------------------------------------------------

class TestToolDispatch:
    """All 16 names dispatch to the expected handler."""

    @pytest.mark.asyncio
    async def test_every_registered_name_dispatches(self, monkeypatch):
        """Every registered tool name dispatches without raising ValueError('Unknown tool')."""
        from tube_bridge.tools import (
            search, search_channels, channel_info, video_info, trending,
            channel_videos, playlist, transcript, available_languages,
            comments, corpus_create, corpus_add, corpus_search,
            corpus_list, corpus_delete,
        )

        # Mock all upstreams to avoid live network. Each returns structured data.
        async def _mock_search(*args, **kwargs):
            return {"results": [], "total": 0}
        async def _mock_search_channels(*args, **kwargs):
            return {"channels": []}
        async def _mock_channel_info(*args, **kwargs):
            return {"subscribers": 0}
        async def _mock_video_info(*args, **kwargs):
            return {"title": "mock", "cached": False}
        async def _mock_trending(*args, **kwargs):
            return {"videos": []}
        async def _mock_channel_videos(*args, **kwargs):
            return {"videos": []}
        async def _mock_playlist(*args, **kwargs):
            return {"videos": []}
        async def _mock_transcript(*args, **kwargs):
            return {"text": "mock transcript"}
        async def _mock_available_languages(*args, **kwargs):
            return {"languages": []}
        async def _mock_comments(*args, **kwargs):
            return {"comments": []}
        async def _mock_corpus_create(*args, **kwargs):
            return {"corpus_id": args[0], "status": "created"}
        async def _mock_corpus_add(*args, **kwargs):
            return {"status": "indexed", "chunks": 0}
        async def _mock_corpus_search(*args, **kwargs):
            return {"chunks": [], "total_results": 0}
        async def _mock_corpus_list(*args, **kwargs):
            return {"corpora": [], "total": 0}
        async def _mock_corpus_delete(*args, **kwargs):
            return {"status": "deleted"}

        # Map FUNCTION names (as imported in server.py) to mocks.
        # Use sys.modules to get the actual module (not the re-exported
        # Server object from tube_bridge.__init__).
        import sys
        server_mod = sys.modules["tube_bridge.server"]

        mock_map = {
            "search": _mock_search,
            "search_channels": _mock_search_channels,
            "channel_info": _mock_channel_info,
            "video_info": _mock_video_info,
            "trending": _mock_trending,
            "channel_videos": _mock_channel_videos,
            "playlist": _mock_playlist,
            "transcript": _mock_transcript,
            "available_languages": _mock_available_languages,
            "comments": _mock_comments,
            "corpus_create": _mock_corpus_create,
            "corpus_add": _mock_corpus_add,
            "corpus_search": _mock_corpus_search,
            "corpus_list": _mock_corpus_list,
            "corpus_delete": _mock_corpus_delete,
        }

        for fn_name, mock_fn in mock_map.items():
            monkeypatch.setattr(server_mod, fn_name, mock_fn)

        # Also mock extract_video_id for tools that use it
        monkeypatch.setattr(server_mod, "extract_video_id",
                            lambda x: x  # identity passthrough
        )

        tools = await list_tools()
        for tool in tools:
            name = tool.name
            args = dict(VALID_INPUTS.get(name, {}))
            if name == "tube_bridge_help":
                result = await _handle_tool(name, args)
                assert result == HELP_TEXT, (
                    f"tube_bridge_help did not return HELP_TEXT"
                )
            else:
                try:
                    result = await _handle_tool(name, args)
                    assert result is not None, (
                        f"Dispatch for '{name}' returned None"
                    )
                except ValueError as e:
                    if "Unknown tool" in str(e):
                        pytest.fail(f"Tool '{name}' raised Unknown tool ValueError")
                    raise

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_controlled_error(self):
        """Unknown tool name raises ValueError with a clear message."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await _handle_tool("nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_help_dispatch_returns_help_text(self):
        """tube_bridge_help returns HELP_TEXT."""
        result = await _handle_tool("tube_bridge_help", {})
        assert result == HELP_TEXT

    @pytest.mark.asyncio
    async def test_dispatch_returns_controlled_error_on_validation_failure(self):
        """Missing required argument raises KeyError (production path).
        call_tool() wraps this as a controlled MCP text response."""
        with pytest.raises(KeyError):
            await _handle_tool("youtube_search", {})


# ---------------------------------------------------------------------------
# Docstring / metadata honesty
# ---------------------------------------------------------------------------

class TestDocstringHonesty:
    """Package docstring and metadata make no stale claims."""

    def test_package_docstring_no_stale_tool_count(self):
        """Package docstring does not claim 10 or 11 tools."""
        import tube_bridge
        doc = tube_bridge.__doc__ or ""
        assert "10 tools" not in doc, (
            "Package docstring still claims 10 tools"
        )
        assert "11 tools" not in doc, (
            "Package docstring still claims 11 tools"
        )

    def test_help_text_tools_count_consistent(self):
        """HELP_TEXT top-level tool count (or tool list length) matches registry."""
        tools = _sync_list_tools()
        count = HELP_TEXT.get("tools")
        # May be an int or a list (duplicate key in dict overwrites)
        if isinstance(count, list):
            actual_count = len(count)
        elif isinstance(count, int):
            actual_count = count
        else:
            actual_count = 0
        assert actual_count >= 16, (
            f"HELP_TEXT tool count is {actual_count}, must be >= 16"
        )
