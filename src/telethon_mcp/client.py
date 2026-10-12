"""Telethon client wrapper for MCP tools."""

from __future__ import annotations

import asyncio
import functools
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import UnauthorizedError
from telethon.sessions import SQLiteSession
from telethon.tl.types import (
    Channel,
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

# Telethon appends ".session", so the file on disk is ~/.telethon-mcp-session.session.
SESSION_PATH = str(Path.home() / ".telethon-mcp-session")

class TelethonMcpError(Exception):
    """An anticipated failure; its message says what the agent or the user can do."""


# The server instructions key off "Not authorized", so keep that prefix.
NOT_AUTHORIZED = (
    "Not authorized. Ask the user to run `telethon-mcp login` in a terminal (the command "
    "that starts this server, with `login` appended), then retry."
)


class _CommittingSession(SQLiteSession):
    """A SQLiteSession that commits each write Telethon would otherwise leave open.

    Telethon caches the entities of every result and update in the session file but
    commits them once a minute, and the open transaction write-locks the file until then.
    Every MCP client session runs its own server process on this file, as do `login` and
    `status`, so another process would fail with "database is locked" after five seconds.
    These are the deferred writes in Telethon 1.45; re-check them when upgrading.
    """

    def process_entities(self, tlo):
        super().process_entities(tlo)
        self.save()

    def set_update_state(self, entity_id, state):
        super().set_update_state(entity_id, state)
        self.save()

    def get_entity_rows_by_username(self, username):
        # Clears the username on stale duplicate rows, a write inside a read.
        rows = super().get_entity_rows_by_username(username)
        self.save()
        return rows


def open_telegram_client(session_path: str, api_id: int, api_hash: str) -> TelegramClient:
    """A TelegramClient on the session file; the MCP server and the CLI both open it here."""
    client = TelegramClient(_CommittingSession(session_path), api_id, api_hash)
    # The file holds the auth key: full access to the account, 2FA included. SQLite creates
    # it with the default mode (0644 under the usual umask) and gives its journal files the
    # database file's mode. On Windows os.chmod only clears the read-only flag.
    os.chmod(client.session.filename, 0o600)
    return client


def _requires_login(method):
    """Run a tool method on an authorized connection; a 401 from Telegram drops it."""

    @functools.wraps(method)
    async def wrapper(self: TelethonMcpClient, *args, **kwargs):
        await self._ensure_authorized()
        try:
            return await method(self, *args, **kwargs)
        except UnauthorizedError as exc:
            # Revoked or expired: release the session file for `telethon-mcp login`.
            await self._close()
            raise TelethonMcpError(NOT_AUTHORIZED) from exc

    return wrapper


class TelethonMcpClient:
    def __init__(self, api_id: int, api_hash: str) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        # Connected and authorized, or None. An unauthorized connection is not kept: it
        # would hold the session file that `telethon-mcp login` in a terminal writes.
        self._client: TelegramClient | None = None
        self._me: User | None = None
        self._open_lock = asyncio.Lock()

    async def connect(self) -> None:
        await self._open()

    async def disconnect(self) -> None:
        await self._close()

    async def _open(self) -> None:
        """Connect with what the session file holds now; keep the connection if authorized."""
        client = open_telegram_client(SESSION_PATH, self._api_id, self._api_hash)
        keep = False
        try:
            await client.connect()
            if await client.is_user_authorized():
                self._me = await client.get_me()
                keep = True
        finally:
            if keep:
                self._client = client
            else:
                await client.disconnect()

    async def _close(self) -> None:
        client, self._client, self._me = self._client, None, None
        if client is not None:
            await client.disconnect()

    def is_authorized(self) -> bool:
        return self._client is not None

    async def _ensure_authorized(self) -> None:
        if self._client is None:
            async with self._open_lock:
                # A login from a terminal since the last check is only in the session file,
                # and Telethon caches is_user_authorized() per client, so open a new one.
                if self._client is None:
                    await self._open()
        if self._client is None:
            raise TelethonMcpError(NOT_AUTHORIZED)

    async def _get_entity(self, identifier: str):
        try:
            return await self._client.get_entity(self._parse_id(identifier))
        except ValueError as exc:
            # Telethon's way of saying the username, phone or ID resolves to nothing.
            raise TelethonMcpError(str(exc)) from exc

    def _parse_id(self, identifier: str) -> int | str:
        # int() accepts a leading sign, so "+79991234567" would become a user ID.
        if identifier.startswith("+"):
            return identifier
        try:
            return int(identifier)
        except ValueError:
            return identifier

    def _format_ts(self, dt: datetime) -> str:
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC)
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
            peer_id = (
                getattr(fwd.from_id, "user_id", None)
                or getattr(fwd.from_id, "channel_id", None)
                or getattr(fwd.from_id, "chat_id", None)
            )
            if type_name == "PeerChannel":
                return f"[Forwarded from channel:{peer_id}]"
            if type_name == "PeerUser":
                return f"[Forwarded from user:{peer_id}]"
            return f"[Forwarded from {type_name}:{peer_id}]"
        return "[Forwarded]"

    @_requires_login
    async def resolve_entity(self, identifier: str) -> str:
        entity = await self._get_entity(identifier)
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

    @_requires_login
    async def send_message(self, identifier: str, text: str) -> str:
        entity = await self._get_entity(identifier)
        msg = await self._client.send_message(entity, text)
        return (
            f"Message sent.\n"
            f"- **ID**: {msg.id}\n"
            f"- **Time**: {self._format_ts(msg.date)}"
        )

    @_requires_login
    async def read_history(
        self, identifier: str, limit: int = 20, min_id: int | None = None,
    ) -> str:
        entity = await self._get_entity(identifier)
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

    @_requires_login
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

    @_requires_login
    async def download_media(
        self, identifier: str, message_id: int, download_path: str | None = None,
    ) -> str:
        entity = await self._get_entity(identifier)
        msg = await self._client.get_messages(entity, ids=message_id)

        if msg is None:
            raise TelethonMcpError(f"Message {message_id} not found.")
        if msg.media is None:
            raise TelethonMcpError(f"Message {message_id} has no media.")

        target = download_path or tempfile.mkdtemp(prefix="telethon-mcp-")
        path = await self._client.download_media(msg, file=target)

        if path is None:
            raise TelethonMcpError(f"Telegram returned no file for message {message_id}.")
        return f"Downloaded to: {Path(path).resolve()}"

    @_requires_login
    async def send_media(
        self, identifier: str, file_path: str, caption: str | None = None,
    ) -> str:
        entity = await self._get_entity(identifier)
        msg = await self._client.send_file(entity, file_path, caption=caption)
        return (
            f"Media sent.\n"
            f"- **ID**: {msg.id}\n"
            f"- **Time**: {self._format_ts(msg.date)}"
        )

    @_requires_login
    async def edit_message(self, identifier: str, message_id: int, text: str) -> str:
        entity = await self._get_entity(identifier)
        await self._own_message(entity, message_id)
        msg = await self._client.edit_message(entity, message_id, text)
        return (
            f"Message edited.\n"
            f"- **ID**: {msg.id}\n"
            f"- **Edited**: {self._format_ts(msg.edit_date or msg.date)}"
        )

    @_requires_login
    async def delete_message(self, identifier: str, message_id: int, for_everyone: bool) -> str:
        entity = await self._get_entity(identifier)
        if not for_everyone and isinstance(entity, Channel):
            # Telethon would delete it for everyone anyway: Telegram has no other way there.
            raise TelethonMcpError(
                "Supergroups and channels cannot delete a message only for this account: "
                "Telegram deletes it for everyone or not at all."
            )
        await self._own_message(entity, message_id)
        await self._client.delete_messages(entity, [message_id], revoke=for_everyone)
        scope = "for everyone" if for_everyone else "only for this account"
        return f"Message {message_id} deleted {scope}."

    async def _own_message(self, entity, message_id: int):
        """The message, if it exists and was sent from this account.

        Telegram itself lets a private chat delete the other side's messages too.
        """
        msg = await self._client.get_messages(entity, ids=message_id)
        if msg is None:
            raise TelethonMcpError(f"Message {message_id} not found.")
        if not msg.out:
            raise TelethonMcpError(
                f"Message {message_id} was not sent from this account; only messages sent "
                "from this account can be edited or deleted."
            )
        return msg
