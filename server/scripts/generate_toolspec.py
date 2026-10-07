"""Dump the server's tool list as the toolspec JSON Agent Registry takes.

Agent Registry caps a toolspec at 10 KB, and JSON-schema prose and typed `$defs`
eat that budget quickly. This trims what the registry doesn't need and FAILS the
build above LIMIT, rather than letting the registration call reject it later.

    cd server && uv run python scripts/generate_toolspec.py /tmp/toolspec.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.server import mcp  # noqa: E402

LIMIT = 9_500  # the registry's cap is 10,000 bytes; keep headroom for the next tool


def without_prose(node):
    """Drop string `title`/`description` (properties that are themselves named
    `title` stay) and `$defs`, and turn any `$ref` into a plain object."""
    if isinstance(node, dict):
        if "$ref" in node:
            return {"type": "object"}
        return {
            k: without_prose(v)
            for k, v in node.items()
            if k != "$defs" and not (k in ("title", "description") and isinstance(v, str))
        }
    if isinstance(node, list):
        return [without_prose(v) for v in node]
    return node


async def tool_list() -> list[dict]:
    specs = [t.model_dump(mode="json", exclude_none=True) for t in await mcp.list_tools()]
    return [{**s, "inputSchema": without_prose(s["inputSchema"])} for s in specs]


def build() -> str:
    return json.dumps({"tools": asyncio.run(tool_list())}, separators=(",", ":"))


def main(out_path: str) -> int:
    text = build()
    size = len(text.encode("utf-8"))
    if size > LIMIT:
        print(f"error: toolspec is {size} bytes, over the {LIMIT}-byte budget", file=sys.stderr)
        return 1
    with open(out_path, "w") as f:
        f.write(text)
    print(f"wrote {out_path} ({size} bytes)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <out-path>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
