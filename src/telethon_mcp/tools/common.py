"""What the tool modules share: the identifier description, annotations, error handling."""

from __future__ import annotations

import functools

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from telethon.errors import RPCError

from ..client import TelethonMcpError

IDENTIFIER_DESCRIPTION = (
    "@username, phone number with a leading + (e.g. +79991234567; found only among "
    "this account's contacts), or numeric chat ID as shown by telegram_list_dialogs "
    "(resolves only for chats this session has seen)"
)

READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
ADDITIVE = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}
DESTRUCTIVE = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}

# Failures the caller can act on: ours, Telegram refusing a request, and the network or a
# local file path. mcp 2.x passes only ToolError text to the client; any other exception
# reaches it as a bare "Error executing tool <name>", with the traceback in the server
# log, which is what a real bug should stay.
ANTICIPATED_ERRORS = (TelethonMcpError, RPCError, OSError)


def register_tool(mcp: MCPServer, *, name: str, annotations: dict):
    """Register an async tool whose anticipated failures reach the client as MCP errors."""

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except ANTICIPATED_ERRORS as exc:
                raise ToolError(str(exc)) from exc

        return mcp.tool(name=name, annotations=annotations)(wrapper)

    return decorator
