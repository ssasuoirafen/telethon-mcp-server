"""Telethon MCP server - MCPServer with persistent Telethon client."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from mcp.server.mcpserver import MCPServer

from .client import TelethonMcpClient
from .config import load_credentials
from .tools import dialogs, entities, media, messages

# Validated at import so a bad environment stops the server at startup rather
# than surfacing as a failure on the first tool call.
api_id, api_hash = load_credentials()

client = TelethonMcpClient(api_id, api_hash)


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[dict]:
    await client.connect()
    if not client.is_authorized():
        print(
            "Warning: Telegram session not authorized. Run `telethon-mcp login` in a "
            "terminal; the server picks up the login on the next tool call.",
            file=sys.stderr,
        )
    try:
        yield {}
    finally:
        await client.disconnect()


try:
    _VERSION = version("telethon-mcp-server")
except PackageNotFoundError:  # running from a source tree without an install
    _VERSION = "0.0.0+dev"

# mcp 2.x defaults version to "" (1.x reported the SDK's own version), so set it
# explicitly or clients see a blank version in serverInfo.
mcp = MCPServer(
    "telethon-mcp",
    version=_VERSION,
    instructions=(
        "Telegram through the user's personal account, not a bot: anything sent appears "
        "under their name. Use these tools to list dialogs, look up users and chats, read "
        "history, send, edit and delete messages, and download or send media.\n"
        "The login is kept in a session file between sessions. Only when a tool reports "
        "\"Not authorized\", ask the user to run `telethon-mcp login` in a terminal (the "
        "command that starts this server, with `login` appended) and retry once they have "
        "logged in; the server picks up the login without a restart."
    ),
    lifespan=lifespan,
)

entities.register(mcp, client)
messages.register(mcp, client)
dialogs.register(mcp, client)
media.register(mcp, client)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
