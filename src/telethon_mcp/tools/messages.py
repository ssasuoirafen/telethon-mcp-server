"""Tools: send messages and read chat history."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient, handle_error


class SendMessageInput(BaseModel):
    identifier: str = Field(..., description="Username, phone number, or numeric Telegram ID")
    text: str = Field(..., description="Message text to send")


class ReadHistoryInput(BaseModel):
    identifier: str = Field(..., description="Username, phone number, or numeric Telegram ID")
    limit: int = Field(20, description="Number of messages to fetch (default 20)")
    min_id: int | None = Field(None, description="Only messages newer than this message ID")


def register(mcp: FastMCP, client: TelethonMcpClient) -> None:

    @mcp.tool(
        name="telegram_send_message",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def send_message(params: SendMessageInput) -> str:
        """Send a text message to a Telegram user. Returns the sent message ID and timestamp."""
        try:
            return await client.send_message(params.identifier, params.text)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="telegram_read_history",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def read_history(params: ReadHistoryInput) -> str:
        """Read recent messages from a 1-on-1 dialog. Use min_id to only get messages newer than a specific message (e.g., after sending a message, pass its ID to see replies)."""
        try:
            return await client.read_history(params.identifier, params.limit, params.min_id)
        except Exception as e:
            return handle_error(e)
