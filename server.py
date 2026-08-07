"""tube-bridge — launch via stdio or HTTP/SSE."""

import argparse
import asyncio

import uvicorn
from mcp.server.stdio import stdio_server

from tube_bridge.server import server
from tube_bridge.transport import create_app


async def main():
    parser = argparse.ArgumentParser(description="tube-bridge MCP server")
    parser.add_argument("--http", action="store_true", help="Run as HTTP/SSE server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    if args.http:
        app = create_app(server, args.host, args.port)
        config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        srv = uvicorn.Server(config)
        await srv.serve()
    else:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
