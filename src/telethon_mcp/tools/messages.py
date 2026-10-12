"""Tools: send messages and read chat history."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient
from .common import ADDITIVE, IDENTIFIER_DESCRIPTION, READ_ONLY, register_tool


class SendMessageInput(BaseModel):
    identifier: str = Field(..., description=IDENTIFIER_DESCRIPTION)
    text: str = Field(..., description="Message text to send")


class ReadHistoryInput(BaseModel):
    identifier: str = Field(..., description=IDENTIFIER_DESCRIPTION)
    limit: int = Field(20, description="Number of messages to fetch (default 20)")
    min_id: int | None = Field(
        None,
        description=(
            "Only messages with an ID greater than this; IDs are per chat, so the ID "
            "telegram_send_message returns works here"
        ),
    )


def register(mcp: MCPServer, client: TelethonMcpClient) -> None:

    @register_tool(mcp, name="telegram_send_message", annotations=ADDITIVE)
    async def send_message(params: SendMessageInput) -> str:
        """Send a text message as the logged-in user to a user, group, or channel the
        account can post in. It is delivered immediately; this server has no edit or
        delete. Text is parsed as Telegram markdown: **bold**, __italic__, ~~strike~~,
        `code`, ```pre```, [text](url); single * and _ and # stay literal. Returns the
        sent message ID and time (UTC)."""
        return await client.send_message(params.identifier, params.text)

    @register_tool(mcp, name="telegram_read_history", annotations=READ_ONLY)
    async def read_history(params: ReadHistoryInput) -> str:
        """Read the newest messages of a 1-on-1 dialog, printed oldest first as
        "[time] sender (id:N):" followed by text plus media and forward tags. Times are
        UTC. Returns the newest `limit` messages, after min_id when given; there is no
        paging further back, so raise limit to see older history."""
        return await client.read_history(params.identifier, params.limit, params.min_id)
