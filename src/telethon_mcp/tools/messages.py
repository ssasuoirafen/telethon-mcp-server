"""Tools: send messages and read chat history."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient
from .common import ADDITIVE, DESTRUCTIVE, IDENTIFIER_DESCRIPTION, READ_ONLY, register_tool


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


class EditMessageInput(BaseModel):
    identifier: str = Field(..., description=IDENTIFIER_DESCRIPTION)
    message_id: int = Field(
        ...,
        description=(
            "ID of a message sent from this account, as telegram_send_message or "
            "telegram_read_history show it"
        ),
    )
    text: str = Field(..., description="The new text; it replaces the old one entirely")


class DeleteMessageInput(BaseModel):
    identifier: str = Field(..., description=IDENTIFIER_DESCRIPTION)
    message_id: int = Field(..., description="ID of a message sent from this account")
    for_everyone: bool = Field(
        ...,
        description=(
            "true deletes it for every participant; false only for this account, and the "
            "others keep seeing it. Supergroups and channels allow only true"
        ),
    )


def register(mcp: MCPServer, client: TelethonMcpClient) -> None:

    @register_tool(mcp, name="telegram_send_message", annotations=ADDITIVE)
    async def send_message(params: SendMessageInput) -> str:
        """Send a text message as the logged-in user to a user, group, or channel the
        account can post in. It is delivered immediately; telegram_edit_message and
        telegram_delete_message change or remove it afterwards. Text is parsed as Telegram
        markdown: **bold**, __italic__, ~~strike~~, `code`, ```pre```, [text](url); single
        * and _ and # stay literal. Returns the sent message ID and time (UTC)."""
        return await client.send_message(params.identifier, params.text)

    @register_tool(mcp, name="telegram_edit_message", annotations=DESTRUCTIVE)
    async def edit_message(params: EditMessageInput) -> str:
        """Replace the text of a message sent from this account. Everyone in the chat sees
        the new text, marked as edited; Telegram refuses edits some time after sending.
        The text is parsed as Telegram markdown, like telegram_send_message. Returns the
        message ID and the edit time (UTC)."""
        return await client.edit_message(params.identifier, params.message_id, params.text)

    @register_tool(mcp, name="telegram_delete_message", annotations=DESTRUCTIVE)
    async def delete_message(params: DeleteMessageInput) -> str:
        """Delete a message sent from this account, for every participant or only for this
        account (the others keep seeing it). Deleting for everyone cannot be undone.
        Supergroups and channels delete only for everyone."""
        return await client.delete_message(
            params.identifier, params.message_id, params.for_everyone
        )

    @register_tool(mcp, name="telegram_read_history", annotations=READ_ONLY)
    async def read_history(params: ReadHistoryInput) -> str:
        """Read the newest messages of a 1-on-1 dialog, printed oldest first as
        "[time] sender (id:N):" followed by text plus media and forward tags. Times are
        UTC. Returns the newest `limit` messages, after min_id when given; there is no
        paging further back, so raise limit to see older history."""
        return await client.read_history(params.identifier, params.limit, params.min_id)
