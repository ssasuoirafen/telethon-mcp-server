"""Telethon MCP server - FastMCP with persistent Telethon client."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import TelethonMcpClient
from .tools import dialogs, entities, media, messages


def _env_or_exit(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        print(f"Missing env: {name}", file=sys.stderr)
        sys.exit(1)
    return val


api_id = int(_env_or_exit("TELEGRAM_API_ID"))
api_hash = _env_or_exit("TELEGRAM_API_HASH")

client = TelethonMcpClient(api_id, api_hash)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    await client.connect()
    try:
        yield {}
    finally:
        await client.disconnect()


mcp = FastMCP("telethon-mcp", lifespan=lifespan)

entities.register(mcp, client)
messages.register(mcp, client)
dialogs.register(mcp, client)
media.register(mcp, client)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
