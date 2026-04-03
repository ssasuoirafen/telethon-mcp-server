"""Telethon client wrapper for MCP tools."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    User,
    UserStatusLastMonth,
    UserStatusLastWeek,
    UserStatusOffline,
    UserStatusOnline,
    UserStatusRecently,
)


class TelethonMcpClient:
    def __init__(self, api_id: int, api_hash: str) -> None:
        session_path = str(Path.home() / ".telethon-mcp-session")
        self._client = TelegramClient(session_path, api_id, api_hash)
        self._me: User | None = None

    async def connect(self) -> None:
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError("Not authorized. Run: telethon-mcp-auth status")
        self._me = await self._client.get_me()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    def _parse_id(self, identifier: str) -> int | str:
        if identifier.isdigit():
            return int(identifier)
        return identifier

    def _format_ts(self, dt: datetime) -> str:
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")

    def _sender_name(self, sender: User | None, sender_id: int | None) -> str:
        if sender_id and self._me and sender_id == self._me.id:
            return "You"
        if sender is None:
            return f"User#{sender_id or '?'}"
        if sender.username:
            return f"@{sender.username}"
        parts = [sender.first_name or "", sender.last_name or ""]
        return " ".join(p for p in parts if p) or f"User#{sender.id}"

    def _format_user_status(self, user: User) -> str:
        status = user.status
        if isinstance(status, UserStatusOnline):
            return "online"
        if isinstance(status, UserStatusOffline):
            return f"offline (last seen {self._format_ts(status.was_online)})"
        if isinstance(status, UserStatusRecently):
            return "recently"
        if isinstance(status, UserStatusLastWeek):
            return "last week"
        if isinstance(status, UserStatusLastMonth):
            return "last month"
        return "unknown"

    def _media_tag(self, msg) -> str:
        if isinstance(msg.media, MessageMediaPhoto):
            return "[Photo]"
        if isinstance(msg.media, MessageMediaDocument):
            name = None
            if msg.document:
                for attr in msg.document.attributes:
                    if hasattr(attr, "file_name"):
                        name = attr.file_name
                        break
            return f"[Document: {name}]" if name else "[Document]"
        if msg.media is not None:
            return f"[Media: {type(msg.media).__name__}]"
        return ""

    async def resolve_entity(self, identifier: str) -> str:
        entity = await self._client.get_entity(self._parse_id(identifier))
        if not isinstance(entity, User):
            lines = [
                f"## {getattr(entity, 'title', str(entity.id))}",
                f"- **ID**: {entity.id}",
                f"- **Type**: {type(entity).__name__}",
            ]
            return "\n".join(lines)

        lines = [
            f"## {entity.first_name or ''} {entity.last_name or ''}".rstrip(),
            f"- **ID**: {entity.id}",
        ]
        if entity.username:
            lines.append(f"- **Username**: @{entity.username}")
        if entity.phone:
            lines.append(f"- **Phone**: {entity.phone}")
        lines.append(f"- **Bot**: {'yes' if entity.bot else 'no'}")
        lines.append(f"- **Status**: {self._format_user_status(entity)}")
        return "\n".join(lines)

    async def send_message(self, identifier: str, text: str) -> str:
        entity = await self._client.get_entity(self._parse_id(identifier))
        msg = await self._client.send_message(entity, text)
        return (
            f"Message sent.\n"
            f"- **ID**: {msg.id}\n"
            f"- **Time**: {self._format_ts(msg.date)}"
        )

    async def read_history(
        self, identifier: str, limit: int = 20, min_id: int | None = None,
    ) -> str:
        entity = await self._client.get_entity(self._parse_id(identifier))
        kwargs: dict = {"limit": limit}
        if min_id is not None:
            kwargs["min_id"] = min_id

        messages = await self._client.get_messages(entity, **kwargs)

        if not messages:
            return "No messages found."

        name = getattr(entity, "username", None)
        if name:
            name = f"@{name}"
        else:
            name = getattr(entity, "first_name", None) or str(entity.id)

        lines = [f"## Dialog with {name} ({len(messages)} messages)", ""]

        for msg in reversed(messages):  # chronological order (oldest first)
            sender = self._sender_name(msg.sender, msg.sender_id)
            ts = self._format_ts(msg.date)
            text_parts = []

            media_tag = self._media_tag(msg)
            if media_tag:
                text_parts.append(media_tag)
            if msg.text:
                text_parts.append(msg.text)

            content = " ".join(text_parts) if text_parts else "[empty message]"
            lines.append(f"**[{ts}] {sender} (id:{msg.id}):**")
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    async def list_dialogs(self, limit: int = 20) -> str:
        dialogs = await self._client.get_dialogs(limit=limit)

        if not dialogs:
            return "No dialogs found."

        lines = [f"# Dialogs ({len(dialogs)})", ""]

        for d in dialogs:
            unread = f" ({d.unread_count} unread)" if d.unread_count else ""
            last_msg = ""
            if d.message and d.message.text:
                preview = d.message.text[:80]
                if len(d.message.text) > 80:
                    preview += "..."
                last_msg = f" - \"{preview}\""
            lines.append(f"- **{d.name}** (id:{d.entity.id}){unread}{last_msg}")

        return "\n".join(lines)

    async def download_media(
        self, identifier: str, message_id: int, download_path: str | None = None,
    ) -> str:
        entity = await self._client.get_entity(self._parse_id(identifier))
        msg = await self._client.get_messages(entity, ids=message_id)

        if msg is None:
            return f"Message {message_id} not found."
        if msg.media is None:
            return f"Message {message_id} has no media."

        target = download_path or tempfile.mkdtemp(prefix="telethon-mcp-")
        path = await self._client.download_media(msg, file=target)

        if path is None:
            return "Failed to download media."
        return f"Downloaded to: {Path(path).resolve()}"

    async def send_media(
        self, identifier: str, file_path: str, caption: str | None = None,
    ) -> str:
        entity = await self._client.get_entity(self._parse_id(identifier))
        msg = await self._client.send_file(entity, file_path, caption=caption)
        return (
            f"Media sent.\n"
            f"- **ID**: {msg.id}\n"
            f"- **Time**: {self._format_ts(msg.date)}"
        )


def handle_error(e: Exception) -> str:
    return f"Error: {e}"
