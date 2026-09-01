"""ntfy MCP Server — Push-Notifications senden + lesen via Claude.

Auth-Architektur (identisch zu whisper-mcp / hero-mcp):
  1. Statischer Bearer (MCP_API_KEY) → Claude Desktop / direkte API-Clients
  2. Bearer JWT → Authelia OIDC Introspection → Claude.ai
"""

import json
import logging
import os
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)

from . import client  # noqa: E402

server = Server(
    "ntfy-mcp-server",
    instructions=(
        "MCP-Server für selbst gehostetes ntfy.sh. "
        "Tools:\n"
        "- ntfy_send: Push-Notification an ein Topic senden\n"
        "- ntfy_send_with_actions: mit Action-Buttons (URL, HTTP, View)\n"
        "- ntfy_get_messages: gecachte Messages eines Topics holen\n"
        "- ntfy_list_topics: Topics auflisten, auf die der Token Zugriff hat"
    ),
)


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="ntfy_send",
            description=(
                "Sendet eine Push-Notification an ein ntfy-Topic. "
                "Verwendet die JSON-Publish-API."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic-Name (z.B. 'alerts', 'baustelle')",
                    },
                    "message": {
                        "type": "string",
                        "description": "Hauptnachricht",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optionaler Titel (fett dargestellt)",
                    },
                    "priority": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": (
                            "Priorität 1 (min) bis 5 (max/urgent). "
                            "Default 3."
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Tags / Emojis: ['warning'] wird zu ⚠️, "
                            "['+1'] zu 👍, freie Tags als Text angezeigt."
                        ),
                    },
                    "click": {
                        "type": "string",
                        "description": "URL die beim Tippen auf die Notification geöffnet wird",
                    },
                    "delay": {
                        "type": "string",
                        "description": (
                            "Verzögerte Zustellung: '30min', '1h', '2026-07-01 09:00', "
                            "'tomorrow 10am' usw."
                        ),
                    },
                    "markdown": {
                        "type": "boolean",
                        "default": False,
                        "description": "Markdown im message-Body rendern",
                    },
                    "icon": {
                        "type": "string",
                        "description": "URL zu einem Icon (PNG/JPG)",
                    },
                    "email": {
                        "type": "string",
                        "description": "Wenn gesetzt: zusätzlich per E-Mail zustellen",
                    },
                },
                "required": ["topic", "message"],
            },
        ),
        types.Tool(
            name="ntfy_send_with_actions",
            description=(
                "Sendet eine Notification mit Action-Buttons. Bis zu 3 Actions. "
                "Action-Typen: 'view' (öffnet URL), 'http' (sendet HTTP-Request), "
                "'broadcast' (Android Intent)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "message": {"type": "string"},
                    "title": {"type": "string"},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                    "actions": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["view", "http", "broadcast"],
                                },
                                "label": {"type": "string"},
                                "url": {"type": "string"},
                                "method": {
                                    "type": "string",
                                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                                },
                                "headers": {"type": "object"},
                                "body": {"type": "string"},
                                "clear": {
                                    "type": "boolean",
                                    "description": "Notification nach Action schließen",
                                },
                            },
                            "required": ["action", "label"],
                        },
                    },
                },
                "required": ["topic", "message", "actions"],
            },
        ),
        types.Tool(
            name="ntfy_get_messages",
            description=(
                "Holt gecachte Messages eines Topics im Poll-Modus (kein "
                "Streaming). Mit `since=10m` letzte 10 Minuten, `since=1h` "
                "letzte Stunde, `since=all` alle gecachten."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "since": {
                        "type": "string",
                        "default": "all",
                        "description": (
                            "Zeitfenster: '10m', '1h', '24h', 'all' oder "
                            "Unix-Timestamp / ISO-Datum"
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 50,
                        "description": "Maximal-Anzahl Messages",
                    },
                },
                "required": ["topic"],
            },
        ),
        types.Tool(
            name="ntfy_list_topics",
            description=(
                "Gibt das Account-Profil zurück inkl. der Zugriffsrechte (welche "
                "Topics darf der konfigurierte Token lesen/schreiben)."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments or {})
    except Exception as exc:
        result = {"error": str(exc), "tool": name}
    return [
        types.TextContent(
            type="text", text=json.dumps(result, ensure_ascii=False, indent=2)
        )
    ]


async def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "ntfy_send":
        return await client.publish(
            topic=args["topic"],
            message=args["message"],
            title=args.get("title"),
            priority=args.get("priority"),
            tags=args.get("tags"),
            click=args.get("click"),
            delay=args.get("delay"),
            markdown=args.get("markdown", False),
            icon=args.get("icon"),
            email=args.get("email"),
        )
    if name == "ntfy_send_with_actions":
        return await client.publish(
            topic=args["topic"],
            message=args["message"],
            title=args.get("title"),
            priority=args.get("priority"),
            actions=args.get("actions"),
        )
    if name == "ntfy_get_messages":
        return await client.get_messages(
            topic=args["topic"],
            since=args.get("since", "all"),
            limit=args.get("limit", 50),
        )
    if name == "ntfy_list_topics":
        return await client.list_user_topics()
    raise ValueError(f"Unbekanntes Tool: {name}")


def main() -> None:
    import asyncio

    if os.getenv("MCP_TRANSPORT", "stdio") == "sse":
        _run_sse()
    else:
        asyncio.run(mcp.server.stdio.run_server(server))


def _run_sse() -> None:
    """SSE + Streamable-HTTP transport mit Dual-Auth (statisch + OIDC)."""
    import contextlib
    from collections.abc import AsyncIterator

    import httpx as _httpx
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    mcp_api_key = os.getenv("MCP_API_KEY", "")
    oidc_introspection_url = os.getenv("OIDC_INTROSPECTION_URL", "")
    oidc_client_id = os.getenv("OIDC_CLIENT_ID", "")
    oidc_client_secret = os.getenv("OIDC_CLIENT_SECRET", "")

    # Refuse to start rather than serve everything unauthenticated: an empty
    # MCP_API_KEY is the image default, so a forgotten env var used to be enough to
    # open the server to anyone. Failing loudly at startup is the only variant of
    # this that cannot go unnoticed.
    if not mcp_api_key and not all(
        (oidc_introspection_url, oidc_client_id, oidc_client_secret)
    ):
        raise RuntimeError(
            "[auth] Neither MCP_API_KEY nor a complete OIDC triple "
            "(OIDC_INTROSPECTION_URL + OIDC_CLIENT_ID + OIDC_CLIENT_SECRET) is set. "
            "Refusing to start."
        )

    async def _is_authorized(request: Request) -> tuple[bool, str | None]:
        auth = request.headers.get("Authorization", "")
        if not auth:
            return False, "no_header"
        if mcp_api_key and auth == f"Bearer {mcp_api_key}":
            return True, None
        if not auth.startswith("Bearer "):
            return False, "invalid_token"
        if oidc_introspection_url and oidc_client_id and oidc_client_secret:
            jwt_token = auth[7:]
            try:
                async with _httpx.AsyncClient() as http:
                    resp = await http.post(
                        oidc_introspection_url,
                        data={"token": jwt_token},
                        auth=(oidc_client_id, oidc_client_secret),
                        timeout=5.0,
                    )
                    data = resp.json()
                    if data.get("active", False):
                        return True, None
                    return False, "invalid_token"
            except Exception as e:
                logging.error("Introspection fehlgeschlagen: %s", e)
                return False, "invalid_token"
        return False, "invalid_token"

    def _unauthorized(reason: str | None) -> Response:
        if reason == "invalid_token":
            www = (
                'Bearer realm="ntfy-mcp", error="invalid_token", '
                'error_description="The access token expired or is invalid"'
            )
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": www},
            )
        return Response("Unauthorized", status_code=401)

    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        ok, reason = await _is_authorized(request)
        if not ok:
            return _unauthorized(reason)
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )
        return Response()

    async def handle_messages(scope, receive, send):
        """The /messages/ endpoint carries the client's JSON-RPC calls for an SSE
        session, so it needs the same check as every other route -- mounting
        SseServerTransport.handle_post_message directly bypasses _is_authorized."""
        req = Request(scope, receive=receive)
        ok, reason = await _is_authorized(req)
        if not ok:
            await _unauthorized(reason)(scope, receive, send)
            return
        await sse.handle_post_message(scope, receive, send)

    class _AlreadySent(Response):
        def __init__(self) -> None:
            super().__init__(content=b"", status_code=200)

        async def __call__(self, scope, receive, send):  # noqa: D401
            return

    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
    )

    async def handle_streamable_http(request: Request):
        ok, reason = await _is_authorized(request)
        if not ok:
            return _unauthorized(reason)
        await session_manager.handle_request(
            request.scope, request.receive, request._send
        )
        return _AlreadySent()

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logging.info("StreamableHTTPSessionManager started")
            yield
            logging.info("StreamableHTTPSessionManager stopping")

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_streamable_http, methods=["POST"]),
            Route("/mcp", endpoint=handle_streamable_http, methods=["POST"]),
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=handle_messages),
        ],
        lifespan=lifespan,
    )

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
