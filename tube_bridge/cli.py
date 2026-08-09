"""Command-line entrypoint for tube-bridge."""

import argparse
import asyncio

import uvicorn
from mcp.server.stdio import stdio_server

from .server import server
from .transport import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="tube-bridge MCP server")
    parser.add_argument("--http", action="store_true", help="Run the HTTP MCP server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    return parser


async def _run(args: argparse.Namespace) -> None:
    if args.http:
        app = create_app(server, args.host, args.port)
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        await uvicorn.Server(config).serve()
        return

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main(argv: list[str] | None = None) -> None:
    """Parse arguments synchronously and run the async transport."""
    args = build_parser().parse_args(argv)
    asyncio.run(_run(args))
