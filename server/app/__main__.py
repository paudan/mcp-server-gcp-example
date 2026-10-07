"""Runs the server over streamable HTTP: `uv run python -m app`."""

from __future__ import annotations

import logging
import sys

import uvicorn

from . import config, telemetry
from .server import create_app


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    telemetry.setup_tracing()
    if not (config.allow_anonymous() or config.reader_identities() or config.admin_identities()):
        print("No MCP_*_IDENTITIES set and MCP_ALLOW_ANONYMOUS is off: "
              "every request will be refused.", file=sys.stderr)
    uvicorn.run(create_app(), host=config.mcp_host(), port=config.mcp_port(), log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
