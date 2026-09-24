"""Tool: list recent dialogs."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient, handle_error


class ListDialogsInput(BaseModel):
    limit: int = Field(20, description="Number of recent dialogs to list (default 20)")


def register(mcp: MCPServer, client: TelethonMcpClient) -> None:

    @mcp.tool(
        name="telegram_list_dialogs",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def list_dialogs(params: ListDialogsInput) -> str:
        """List the first `limit` chats of the account's dialog list (users, groups,
        channels; same order as the Telegram app), one line each: name, (id:N), unread
        count, and the first 80 characters of the last text message. The id works as the
        identifier in the other telegram_* tools. There is no paging past limit."""
        try:
            return await client.list_dialogs(params.limit)
        except Exception as e:
            return handle_error(e)
