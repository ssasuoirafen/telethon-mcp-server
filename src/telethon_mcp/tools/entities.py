"""Tool: resolve Telegram entity."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient, handle_error


class ResolveInput(BaseModel):
    identifier: str = Field(
        ...,
        description=(
            "@username, phone number with a leading + (e.g. +79991234567; found only among "
            "this account's contacts), or numeric chat ID as shown by telegram_list_dialogs "
            "(resolves only for chats this session has seen)"
        ),
    )


def register(mcp: MCPServer, client: TelethonMcpClient) -> None:

    @mcp.tool(
        name="telegram_resolve_entity",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    )
    async def resolve_entity(params: ResolveInput) -> str:
        """Resolve a Telegram username, phone, or ID to full user info (name, status, phone, bot flag)."""
        try:
            return await client.resolve_entity(params.identifier)
        except Exception as e:
            return handle_error(e)
