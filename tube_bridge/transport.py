"""tube-bridge — HTTP/SSE transport with StreamableHTTPSessionManager and optional auth."""

import contextlib
import os

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.responses import JSONResponse

from . import demo_policy as policy
from .oauth import AuthPrincipal, OAuthService


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


def create_app(
    server: Server, host: str, port: int, oauth_service: OAuthService | None = None
):
    """Build the HTTP app with optional static-Bearer and OAuth authorization."""

    sse = SseServerTransport("/messages")
    http_manager = StreamableHTTPSessionManager(app=server, stateless=True)
    auth_key = _get_auth_key()
    oauth = oauth_service if oauth_service is not None else OAuthService.from_env()
    auth_enabled = bool(auth_key) or oauth.enabled

    async def handle_sse(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    async def handle_messages(scope, receive, send):
        await sse.handle_post_message(scope, receive, send)

    async def health(scope, receive, send):
        metrics = policy.demo_metrics()
        response = JSONResponse(
            {
                "status": "ok",
                "server": "tube-bridge",
                "tools": 16,
                "auth": "enabled" if auth_enabled else "disabled",
                "auth_oauth": {"enabled": oauth.enabled, **oauth.metrics()},
                "demo": {
                    "enabled": policy.is_demo_mode(),
                    "data_api_limit": policy.DEMO_DATA_API_LIMIT,
                    "allowed_total": metrics["allowed_total"],
                    "rejected_total": metrics["rejected_total"],
                    "client_buckets": metrics["client_buckets"],
                    "corpus_ttl_seconds": policy.DEMO_CORPUS_TTL_SECONDS,
                },
            }
        )
        await response(scope, receive, send)

    async def dispatch_protected(scope, receive, send, principal: AuthPrincipal | None):
        path = scope["path"]
        method = scope["method"]
        with policy.bind_request_identity(scope):
            if path == "/mcp":
                oauth.record_authenticated(principal)
                await http_manager.handle_request(scope, receive, send)
            elif path == "/sse":
                oauth.record_authenticated(principal)
                await handle_sse(scope, receive, send)
            elif path == "/messages" and method == "POST":
                oauth.record_authenticated(principal)
                await handle_messages(scope, receive, send)
            else:
                await JSONResponse({"error": "not found"}, status_code=404)(
                    scope, receive, send
                )

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            demo_ttl = None
            if policy.is_demo_mode():
                from . import demo_ttl

                demo_ttl.start_demo_ttl_worker()
            try:
                async with contextlib.AsyncExitStack() as stack:
                    await stack.enter_async_context(http_manager.run())
                    await send({"type": "lifespan.startup.complete"})
                    while True:
                        message = await receive()
                        if message["type"] == "lifespan.shutdown":
                            await send({"type": "lifespan.shutdown.complete"})
                            return
            finally:
                if demo_ttl is not None:
                    demo_ttl.stop_demo_ttl_worker()
            return

        path = scope["path"]
        if path == "/health":
            await health(scope, receive, send)
            return
        if await oauth.handle(scope, receive, send):
            return

        protected = path in ("/mcp", "/sse", "/messages")
        principal = (
            oauth.authenticate_request(scope, static_key=auth_key)
            if auth_enabled
            else None
        )
        if protected and auth_enabled and principal is None:
            headers = {"www-authenticate": oauth.challenge()} if oauth.enabled else None
            await JSONResponse(
                {
                    "error": "unauthorized",
                    "message": "Set Authorization: Bearer <key> header",
                },
                status_code=401,
                headers=headers,
            )(scope, receive, send)
            return
        await dispatch_protected(scope, receive, send, principal)

    return app
