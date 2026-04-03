"""Tools: download and send media files."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient, handle_error


class DownloadMediaInput(BaseModel):
    identifier: str = Field(..., description="Chat identifier (username, phone, or ID)")
    message_id: int = Field(..., description="Message ID containing the media to download")
    download_path: str | None = Field(None, description="Absolute path to save file (default: temp directory)")


class SendMediaInput(BaseModel):
    identifier: str = Field(..., description="Chat identifier (username, phone, or ID)")
    file_path: str = Field(..., description="Absolute path to the local file to send")
    caption: str | None = Field(None, description="Optional caption text for the media")


def register(mcp: FastMCP, client: TelethonMcpClient) -> None:

    @mcp.tool(
        name="telegram_download_media",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def download_media(params: DownloadMediaInput) -> str:
        """Download a photo or document from a specific message. Returns the local file path."""
        try:
            return await client.download_media(params.identifier, params.message_id, params.download_path)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="telegram_send_media",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def send_media(params: SendMediaInput) -> str:
        """Send a local file (photo or document) to a Telegram user. Telethon auto-detects file type by extension."""
        try:
            return await client.send_media(params.identifier, params.file_path, params.caption)
        except Exception as e:
            return handle_error(e)
