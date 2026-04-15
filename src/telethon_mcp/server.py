"""Telethon MCP server - FastMCP with persistent Telethon client."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import TelethonMcpClient
from .tools import auth, dialogs, entities, media, messages


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
    if not client.is_authorized():
        print(
            "Warning: Telegram session not authorized. "
            "Use telegram_auth_start tool or run `telethon-mcp-auth login`.",
            file=sys.stderr,
        )
    try:
        yield {}
    finally:
        await client.disconnect()


mcp = FastMCP("telethon-mcp", lifespan=lifespan)

auth.register(mcp, client)
entities.register(mcp, client)
messages.register(mcp, client)
dialogs.register(mcp, client)
media.register(mcp, client)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
