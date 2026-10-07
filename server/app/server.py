"""A tiny notes catalog as an MCP server. Every tool is registered; the caller's role
decides which ones it sees (`tools/list`) and may call (`tools/call`)."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import auth, config, telemetry

READ_TOOLS = ("list_notes", "get_note")
ADMIN_TOOLS = ("delete_note",)

_QUERY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                         openWorldHint=False)
_DELETE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True,
                          openWorldHint=False)

NOTES: dict[str, str] = {
    "welcome": "Hello from the example catalog.",
    "deploy": "Deploys go through CI.",
}


def allowed_tools(role: str) -> frozenset[str]:
    if role == auth.ROLE_ADMIN:
        return frozenset(READ_TOOLS + ADMIN_TOOLS)
    if role == auth.ROLE_READER:
        return frozenset(READ_TOOLS)
    return frozenset()


def _guarded(fn: Callable[..., dict]) -> Callable[..., dict]:
    """A tool returns `{"ok": False, "error": ...}` instead of raising, so a client
    sees an answer it can read rather than a transport error."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> dict:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return wrapper


class _TieredFastMCP(FastMCP):
    """Lists and runs only the tools the caller's role allows, and audits every call."""

    def _caller(self) -> auth.Caller | None:
        try:
            request = self.get_context().request_context.request
        except ValueError:  # no request in flight: a direct call, not a transport
            request = None
        return auth.caller_of(request)

    async def list_tools(self):
        caller = self._caller()
        allowed = allowed_tools(caller.role) if caller else frozenset()
        return [t for t in await super().list_tools() if t.name in allowed]

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        caller = self._caller() or auth.Caller("unknown", "none")
        allowed = name in allowed_tools(caller.role)
        started = time.perf_counter()
        error = ""
        try:
            if not allowed:
                raise ToolError(f"{name} is not available to this caller")
            with telemetry.tracer.start_as_current_span(f"execute_tool {name}") as span:
                span.set_attribute("gen_ai.tool.name", name)
                span.set_attribute("mcp.caller.role", caller.role)
                return await super().call_tool(name, arguments)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            telemetry.audit(name, caller.principal, caller.role, allowed,
                            (time.perf_counter() - started) * 1000, error)


mcp = _TieredFastMCP(
    "catalog",
    host=config.mcp_host(),
    port=config.mcp_port(),
    # Cloud Run has no session affinity and runs several instances; an in-memory
    # session id would 404 ("Session terminated") on any instance that did not issue it.
    stateless_http=True,
    instructions="Read notes from a small catalog; admins may also delete them.",
)


def create_app():
    """The streamable-HTTP ASGI app, with every request authenticated first."""
    app = mcp.streamable_http_app()
    app.add_middleware(auth.CallerAuthMiddleware)
    return app


@mcp.tool(annotations=_QUERY)
@_guarded
def list_notes() -> dict:
    """List the ids of all notes."""
    return {"ok": True, "ids": sorted(NOTES)}


@mcp.tool(annotations=_QUERY)
@_guarded
def get_note(note_id: str) -> dict:
    """Return one note by id."""
    if note_id not in NOTES:
        return {"ok": False, "error": f"no note {note_id!r}"}
    return {"ok": True, "id": note_id, "text": NOTES[note_id]}


@mcp.tool(annotations=_DELETE)
@_guarded
def delete_note(note_id: str) -> dict:
    """Delete one note by id (admin only)."""
    return {"ok": NOTES.pop(note_id, None) is not None, "id": note_id}
