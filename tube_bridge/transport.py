"""tube-bridge — HTTP/SSE transport with StreamableHTTPSessionManager and optional auth."""

import contextlib
import os

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.responses import JSONResponse


def _get_auth_key() -> str | None:
    """If set, all /mcp and /sse requests must include Authorization: Bearer <this>."""
    return os.environ.get("TUBE_BRIDGE_AUTH_KEY")


def _check_auth(scope) -> bool:
    """Returns True if request is authorized. Always True if no auth key configured."""
    key = _get_auth_key()
    if not key:
        return True
    # Parse Authorization header from ASGI scope
    for header_name, header_value in scope.get("headers", []):
        if header_name == b"authorization":
            return header_value == f"Bearer {key}".encode()
    return False


def create_app(server: Server, host: str, port: int):
    """Build a raw ASGI app with /mcp (Streamable HTTP), /sse (legacy), /health."""

    sse = SseServerTransport("/messages")
    http_manager = StreamableHTTPSessionManager(app=server, stateless=True)
    auth_key = _get_auth_key()

    async def handle_sse(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    async def handle_messages(scope, receive, send):
        await sse.handle_post_message(scope, receive, send)

    async def health(scope, receive, send):
        from .server import TOOL_CATALOG

        response = JSONResponse({
            "status": "ok", "server": "tube-bridge", "tools": len(TOOL_CATALOG),
            "auth": "enabled" if auth_key else "disabled",
        })
        await response(scope, receive, send)

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            async with contextlib.AsyncExitStack() as stack:
                await stack.enter_async_context(http_manager.run())
                await send({"type": "lifespan.startup.complete"})
                while True:
                    message = await receive()
                    if message["type"] == "lifespan.shutdown":
                        await send({"type": "lifespan.shutdown.complete"})
                        return
            return

        path = scope["path"]
        method = scope["method"]

        # Auth check for protected routes (health is always open)
        if path != "/health" and not _check_auth(scope):
            resp = JSONResponse({"error": "unauthorized", "message": "Set Authorization: Bearer <key> header"}, status_code=401)
            await resp(scope, receive, send)
            return

        if path == "/health":
            await health(scope, receive, send)
        elif path == "/mcp":
            await http_manager.handle_request(scope, receive, send)
        elif path == "/sse":
            await handle_sse(scope, receive, send)
        elif path == "/messages" and method == "POST":
            await handle_messages(scope, receive, send)
        else:
            resp = JSONResponse({"error": "not found"}, status_code=404)
            await resp(scope, receive, send)

    return app
