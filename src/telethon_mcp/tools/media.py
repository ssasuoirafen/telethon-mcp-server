"""Tools: download and send media files."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient
from .common import ADDITIVE, IDENTIFIER_DESCRIPTION, register_tool


class DownloadMediaInput(BaseModel):
    identifier: str = Field(..., description=IDENTIFIER_DESCRIPTION)
    message_id: int = Field(..., description="Message ID containing the media to download")
    download_path: str | None = Field(
        None,
        description=(
            "Directory to save into (the file name is generated) or full file path; an "
            "existing file at that path is overwritten. Default: a new temp directory per call"
        ),
    )


class SendMediaInput(BaseModel):
    identifier: str = Field(..., description=IDENTIFIER_DESCRIPTION)
    file_path: str = Field(..., description="Absolute path to the local file to send")
    caption: str | None = Field(None, description="Optional caption text for the media")


def register(mcp: MCPServer, client: TelethonMcpClient) -> None:

    @register_tool(mcp, name="telegram_download_media", annotations=ADDITIVE)
    async def download_media(params: DownloadMediaInput) -> str:
        """Download the media (photo, video, voice, sticker, or other document) of one
        message, by the message ID shown in telegram_read_history. Returns the absolute
        local path of the saved file; fails if the message is missing or has no media."""
        return await client.download_media(
            params.identifier, params.message_id, params.download_path
        )

    @register_tool(mcp, name="telegram_send_media", annotations=ADDITIVE)
    async def send_media(params: SendMediaInput) -> str:
        """Send a local file as the logged-in user to a user, group, or channel. Images go
        as compressed photos, other files as documents (chosen by extension). The caption
        is parsed as Telegram markdown, like telegram_send_message. Returns the sent
        message ID and time (UTC)."""
        return await client.send_media(params.identifier, params.file_path, params.caption)
