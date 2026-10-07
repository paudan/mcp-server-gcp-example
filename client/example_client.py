"""Call the server the way a deployed agent would: find it in Agent Registry by display
name, mint an ID token for its URL, and list tools.

    uv run --with mcp --with google-auth --with google-adk python client/example_client.py

Set MCP_URL to skip the registry lookup (local runs, or `gcloud ... describe` output).
"""

from __future__ import annotations

import asyncio
import os
import time

import google.auth.transport.requests
import httpx
from google.auth import jwt
from google.oauth2 import id_token
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DISPLAY_NAME = os.environ.get("MCP_DISPLAY_NAME", "catalog-mcp")
_tokens: dict[str, tuple[float, str]] = {}


def find_in_registry(project: str, location: str) -> str:
    """Exact-match the display name over every MCP server entry (following pages) and
    return its endpoint. Zero or several matches are errors, never a guess."""
    from google.adk.integrations.agent_registry import AgentRegistry

    registry = AgentRegistry(project_id=project, location=location)
    matches, token = [], None
    while True:
        page = registry.list_mcp_servers(page_size=100, page_token=token)
        matches += [m for m in page.get("mcpServers", []) if m.get("displayName") == DISPLAY_NAME]
        token = page.get("nextPageToken")
        if not token:
            break
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one registry entry named {DISPLAY_NAME!r}, got {len(matches)}")
    interfaces = list(matches[0].get("interfaces", []))
    url = next(i["url"] for i in interfaces if i.get("url"))
    # Entries registered with a bare base URL still work: the endpoint is /mcp.
    return url if url.rstrip("/").endswith("/mcp") else url.rstrip("/") + "/mcp"


def token_for(audience: str) -> str:
    """One ID token per audience, reused until five minutes before it expires. Fetching a
    fresh one for every request made registry-backed lookups take seconds each."""
    cached = _tokens.get(audience)
    if cached and cached[0] - 300 > time.time():
        return cached[1]
    token = id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)
    _tokens[audience] = (float(jwt.decode(token, verify=False)["exp"]), token)
    return token


class IdTokenAuth(httpx.Auth):
    def __init__(self, audience: str):
        self.audience = audience

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {token_for(self.audience)}"
        yield request


async def main() -> None:
    url = os.environ.get("MCP_URL") or find_in_registry(
        os.environ["PROJECT"], os.environ.get("REGION", "europe-west4"))
    audience = url.removesuffix("/mcp")  # Cloud Run's audience is the service URL
    async with streamablehttp_client(url, auth=IdTokenAuth(audience)) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print([t.name for t in (await session.list_tools()).tools])
            print(await session.call_tool("list_notes", {}))


if __name__ == "__main__":
    asyncio.run(main())
