"""Tool: list recent dialogs."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient, handle_error


class ListDialogsInput(BaseModel):
    limit: int = Field(20, description="Number of recent dialogs to list (default 20)")


def register(mcp: FastMCP, client: TelethonMcpClient) -> None:

    @mcp.tool(
        name="telegram_list_dialogs",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def list_dialogs(params: ListDialogsInput) -> str:
        """List recent Telegram dialogs with unread counts and last message preview."""
        try:
            return await client.list_dialogs(params.limit)
        except Exception as e:
            return handle_error(e)
