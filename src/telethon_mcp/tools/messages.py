"""Tools: send messages and read chat history."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient, handle_error


class SendMessageInput(BaseModel):
    identifier: str = Field(
        ...,
        description=(
            "@username, phone number with a leading + (e.g. +79991234567; found only among "
            "this account's contacts), or numeric chat ID as shown by telegram_list_dialogs "
            "(resolves only for chats this session has seen)"
        ),
    )
    text: str = Field(..., description="Message text to send")


class ReadHistoryInput(BaseModel):
    identifier: str = Field(
        ...,
        description=(
            "@username, phone number with a leading + (e.g. +79991234567; found only among "
            "this account's contacts), or numeric chat ID as shown by telegram_list_dialogs "
            "(resolves only for chats this session has seen)"
        ),
    )
    limit: int = Field(20, description="Number of messages to fetch (default 20)")
    min_id: int | None = Field(
        None,
        description=(
            "Only messages with an ID greater than this; IDs are per chat, so the ID "
            "telegram_send_message returns works here"
        ),
    )


def register(mcp: MCPServer, client: TelethonMcpClient) -> None:

    @mcp.tool(
        name="telegram_send_message",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def send_message(params: SendMessageInput) -> str:
        """Send a text message as the logged-in user to a user, group, or channel the
        account can post in. It is delivered immediately; this server has no edit or
        delete. Text is parsed as Telegram markdown: **bold**, __italic__, ~~strike~~,
        `code`, ```pre```, [text](url); single * and _ and # stay literal. Returns the
        sent message ID and time (UTC)."""
        try:
            return await client.send_message(params.identifier, params.text)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="telegram_read_history",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def read_history(params: ReadHistoryInput) -> str:
        """Read the newest messages of a 1-on-1 dialog, printed oldest first as
        "[time] sender (id:N):" followed by text plus media and forward tags. Times are
        UTC. Returns the newest `limit` messages, after min_id when given; there is no
        paging further back, so raise limit to see older history."""
        try:
            return await client.read_history(params.identifier, params.limit, params.min_id)
        except Exception as e:
            return handle_error(e)
