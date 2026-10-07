"""Environment-driven settings, read at call time so tests can change them."""

from __future__ import annotations

import os


def _list(name: str) -> frozenset[str]:
    return frozenset(p.strip() for p in os.environ.get(name, "").split(",") if p.strip())


def reader_identities() -> frozenset[str]:
    return _list("MCP_READER_IDENTITIES")


def admin_identities() -> frozenset[str]:
    return _list("MCP_ADMIN_IDENTITIES")


def allow_anonymous() -> bool:
    return os.environ.get("MCP_ALLOW_ANONYMOUS", "").lower() == "true"


def mcp_host() -> str:
    return os.environ.get("MCP_HOST", "127.0.0.1")


def mcp_port() -> int:
    # Cloud Run injects PORT; MCP_PORT is the local override.
    return int(os.environ.get("MCP_PORT") or os.environ.get("PORT") or 8080)
