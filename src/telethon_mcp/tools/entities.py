"""Tool: resolve Telegram entity."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient
from .common import IDENTIFIER_DESCRIPTION, READ_ONLY, register_tool


class ResolveInput(BaseModel):
    identifier: str = Field(..., description=IDENTIFIER_DESCRIPTION)


def register(mcp: MCPServer, client: TelethonMcpClient) -> None:

    @register_tool(mcp, name="telegram_resolve_entity", annotations=READ_ONLY)
    async def resolve_entity(params: ResolveInput) -> str:
        """Resolve a Telegram username, phone, or ID to full user info (name, status,
        phone, bot flag)."""
        return await client.resolve_entity(params.identifier)
