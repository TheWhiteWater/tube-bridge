#!/usr/bin/env python3
"""Deterministic local-network MCP smoke client for Docker/container verification.

Uses mcp.ClientSession with streamable_http_client to perform:
1. initialize handshake
2. list_tools request
3. Validate exactly 16 unique tool names match expected set

Emits JSON result on stdout; exits nonzero on any failure.
No embedded auth values — credentials are passed via CLI only.

STRUCTURED FAILURE: main() catches all transport/session/OS exceptions
and emits structured JSON with ok=false, error_type, error_message.
Returns nonzero exit code on any failure or exception.  This ensures
Docker and CI consumers always receive machine-parseable output.

Usage:
    python3 tests/mcp_client_smoke.py --url http://localhost:8080/mcp
    python3 tests/mcp_client_smoke.py --url http://localhost:8080/mcp --auth test-token
"""

import argparse
import asyncio
import json
import sys
import traceback

import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = [
    "youtube_search",
    "youtube_search_channels",
    "youtube_get_channel_info",
    "youtube_get_video_info",
    "youtube_get_trending",
    "youtube_get_channel_videos",
    "youtube_get_playlist",
    "youtube_get_transcript",
    "youtube_get_available_languages",
    "youtube_get_comments",
    "tube_bridge_help",
    "corpus_create",
    "corpus_add",
    "corpus_search",
    "corpus_list",
    "corpus_delete",
]


def parse_args(argv=None):
    """Parse CLI arguments for URL and optional authorization value."""
    parser = argparse.ArgumentParser(
        description="MCP smoke test — initialize + list_tools validation",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="MCP endpoint URL (e.g. http://localhost:8080/mcp)",
    )
    parser.add_argument(
        "--auth",
        default=None,
        help="Optional authorization token value (Bearer header)",
    )
    return parser.parse_args(argv)


def emit_result(ok: bool, tool_count: int, tool_names: list[str],
                error_type: str | None = None,
                error_message: str | None = None) -> str:
    """Produce a JSON result string.  On failure includes error metadata."""
    result = {
        "ok": ok,
        "tool_count": tool_count,
        "tool_names": sorted(tool_names),
    }
    if not ok:
        result["expected_count"] = 16
        if error_type:
            result["error_type"] = error_type
        if error_message:
            result["error_message"] = error_message
    return json.dumps(result, indent=2)


async def run_smoke(url: str, auth_token: str | None = None) -> tuple[bool, int, list[str]]:
    """Execute initialize + list_tools and return (ok, count, names)."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    async with httpx.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (
            read_stream, write_stream, _
        ):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                if not init_result:
                    return False, 0, []

                tools_result = await session.list_tools()
                names = [tool.name for tool in tools_result.tools]

                if len(names) != 16:
                    return False, len(names), names

                if len(set(names)) != len(names):
                    return False, len(names), names

                missing = set(EXPECTED_TOOLS) - set(names)
                extra = set(names) - set(EXPECTED_TOOLS)
                if missing or extra:
                    return False, len(names), names

                return True, len(names), names


def main(argv=None):
    """Entry point: parse args, run smoke, emit JSON result.

    Catches all transport/session/OS exceptions and emits structured
    JSON with ok=false, error_type, and error_message.  Returns nonzero
    exit code on any failure or exception — Docker and CI consumers
    always receive machine-parseable output, never a raw traceback.
    """
    try:
        args = parse_args(argv)
    except SystemExit:
        raise
    except Exception as e:
        print(emit_result(False, 0, [],
                          error_type=type(e).__name__,
                          error_message=str(e)))
        sys.exit(1)

    try:
        ok, count, names = asyncio.run(run_smoke(args.url, args.auth))
    except Exception as e:
        print(emit_result(False, 0, [],
                          error_type=type(e).__name__,
                          error_message=str(e)))
        sys.exit(1)

    print(emit_result(ok, count, names))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
