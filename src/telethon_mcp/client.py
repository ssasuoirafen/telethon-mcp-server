"""Telethon client wrapper for MCP tools."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    MessageMediaWebPage,
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
        self._authorized: bool = False
        self._pending_phone: str | None = None
        self._phone_code_hash: str | None = None

    async def connect(self) -> None:
        await self._client.connect()
        await self._refresh_auth_state()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def _refresh_auth_state(self) -> None:
        if await self._client.is_user_authorized():
            self._authorized = True
            self._me = await self._client.get_me()
        else:
            self._authorized = False
            self._me = None

    def is_authorized(self) -> bool:
        return self._authorized

    async def _ensure_authorized(self) -> None:
        if not self._authorized:
            raise RuntimeError(
                "Not authorized. Call telegram_auth_start(phone) first, "
                "or run `telethon-mcp-auth login` in a terminal."
            )

    def _me_label(self) -> str:
        if self._me is None:
            return "unknown"
        if self._me.username:
            return f"@{self._me.username}"
        return self._me.first_name or f"User#{self._me.id}"

    async def auth_status(self) -> str:
        if self._authorized and self._me is not None:
            return f"Authorized as {self._me_label()} (ID: {self._me.id})"
        return "Not authorized. Use telegram_auth_start to log in."

    async def auth_start(self, phone: str) -> str:
        if self._authorized:
            return f"Already authorized as {self._me_label()}."
        result = await self._client.send_code_request(phone)
        self._pending_phone = phone
        self._phone_code_hash = result.phone_code_hash
        return (
            "Code sent to the Telegram app. "
            "Ask the user for the code, then call telegram_auth_submit_code."
        )

    async def auth_submit_code(self, code: str) -> str:
        if self._authorized:
            return f"Already authorized as {self._me_label()}."
        if not self._pending_phone or not self._phone_code_hash:
            return "No pending auth. Call telegram_auth_start first."
        try:
            await self._client.sign_in(
                self._pending_phone,
                code,
                phone_code_hash=self._phone_code_hash,
            )
        except SessionPasswordNeededError:
            return (
                "2FA password required. "
                "Ask the user for the password, then call telegram_auth_submit_password."
            )
        await self._refresh_auth_state()
        self._pending_phone = None
        self._phone_code_hash = None
        return f"Authorized as {self._me_label()} (ID: {self._me.id})"

    async def auth_submit_password(self, password: str) -> str:
        if self._authorized:
            return f"Already authorized as {self._me_label()}."
        await self._client.sign_in(password=password)
        await self._refresh_auth_state()
        self._pending_phone = None
        self._phone_code_hash = None
        return f"Authorized as {self._me_label()} (ID: {self._me.id})"

    def _parse_id(self, identifier: str) -> int | str:
        try:
            return int(identifier)
        except ValueError:
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
            is_voice = False
            is_video_note = False
            is_sticker = False
            if msg.document:
                for attr in msg.document.attributes:
                    if hasattr(attr, "file_name"):
                        name = attr.file_name
                    if hasattr(attr, "voice") and attr.voice:
                        is_voice = True
                    if hasattr(attr, "round_message") and attr.round_message:
                        is_video_note = True
                    if type(attr).__name__ == "DocumentAttributeSticker":
                        is_sticker = True
            if is_voice:
                return "[Voice message]"
            if is_video_note:
                return "[Video message]"
            if is_sticker:
                alt = getattr(msg.document, "attributes", [])
                emoji = ""
                for attr in alt:
                    if hasattr(attr, "alt"):
                        emoji = attr.alt
                        break
                return f"[Sticker {emoji}]" if emoji else "[Sticker]"
            return f"[Document: {name}]" if name else "[Document]"
        if isinstance(msg.media, MessageMediaWebPage):
            wp = msg.media.webpage
            url = getattr(wp, "url", None) if wp else None
            return f"[Link: {url}]" if url else ""
        if msg.media is not None:
            return f"[Media: {type(msg.media).__name__}]"
        return ""

    def _fwd_tag(self, msg) -> str:
        fwd = msg.fwd_from
        if fwd is None:
            return ""
        if fwd.from_name:
            return f"[Forwarded from {fwd.from_name}]"
        if fwd.from_id:
            type_name = type(fwd.from_id).__name__
            peer_id = getattr(fwd.from_id, "user_id", None) or getattr(fwd.from_id, "channel_id", None) or getattr(fwd.from_id, "chat_id", None)
            if type_name == "PeerChannel":
                return f"[Forwarded from channel:{peer_id}]"
            if type_name == "PeerUser":
                return f"[Forwarded from user:{peer_id}]"
            return f"[Forwarded from {type_name}:{peer_id}]"
        return "[Forwarded]"

    async def resolve_entity(self, identifier: str) -> str:
        await self._ensure_authorized()
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
        await self._ensure_authorized()
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
        await self._ensure_authorized()
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

            fwd_tag = self._fwd_tag(msg)
            if fwd_tag:
                text_parts.append(fwd_tag)

            media_tag = self._media_tag(msg)
            if media_tag:
                text_parts.append(media_tag)
            if msg.text:
                text_parts.append(msg.text)

            if not text_parts:
                # Debug: show raw message type for truly empty messages
                cls_name = type(msg).__name__
                attrs = []
                if hasattr(msg, "action") and msg.action:
                    attrs.append(f"action={type(msg.action).__name__}")
                if hasattr(msg, "fwd_from") and msg.fwd_from:
                    attrs.append("has_fwd_from")
                if hasattr(msg, "media") and msg.media:
                    attrs.append(f"media={type(msg.media).__name__}")
                if hasattr(msg, "reply_markup") and msg.reply_markup:
                    attrs.append("has_reply_markup")
                debug = f" ({', '.join(attrs)})" if attrs else ""
                content = f"[empty message: {cls_name}{debug}]"
            else:
                content = " ".join(text_parts)
            lines.append(f"**[{ts}] {sender} (id:{msg.id}):**")
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    async def list_dialogs(self, limit: int = 20) -> str:
        await self._ensure_authorized()
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
        await self._ensure_authorized()
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
        await self._ensure_authorized()
        entity = await self._client.get_entity(self._parse_id(identifier))
        msg = await self._client.send_file(entity, file_path, caption=caption)
        return (
            f"Media sent.\n"
            f"- **ID**: {msg.id}\n"
            f"- **Time**: {self._format_ts(msg.date)}"
        )


def handle_error(e: Exception) -> str:
    return f"Error: {e}"
