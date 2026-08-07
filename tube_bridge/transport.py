"""tube-bridge — HTTP/SSE transport (raw ASGI)."""

import asyncio

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import JSONResponse


def create_app(server: Server, host: str, port: int):
    """Build a raw ASGI app with /mcp (Streamable HTTP), /sse (legacy), /health."""

    sse = SseServerTransport("/messages")
    streamable_http = StreamableHTTPServerTransport(None)

    async def handle_sse(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    async def handle_messages(scope, receive, send):
        await sse.handle_post_message(scope, receive, send)

    async def handle_mcp(scope, receive, send):
        await streamable_http.handle_request(scope, receive, send)

    async def health(scope, receive, send):
        response = JSONResponse({"status": "ok", "server": "tube-bridge", "tools": 10})
        await response(scope, receive, send)

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    async def run():
                        async with streamable_http.connect() as (read, write):
                            await server.run(read, write, server.create_initialization_options())
                    asyncio.create_task(run())
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
            return

        path = scope["path"]
        method = scope["method"]

        if path == "/health":
            await health(scope, receive, send)
        elif path == "/mcp":
            await handle_mcp(scope, receive, send)
        elif path == "/sse":
            await handle_sse(scope, receive, send)
        elif path == "/messages" and method == "POST":
            await handle_messages(scope, receive, send)
        else:
            resp = JSONResponse({"error": "not found"}, status_code=404)
            await resp(scope, receive, send)

    return app
