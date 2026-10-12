"""Test doubles for the Telegram connection, shared by the client, CLI and tool tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from telethon.errors import AuthKeyUnregisteredError
from telethon.tl.types import Message, PeerUser, User
from telethon.tl.types.messages import AffectedMessages

import telethon_mcp.cli
import telethon_mcp.client

OWNER = User(id=777, username="owner", first_name="Owner")
ALICE = User(id=555, access_hash=5555, username="alice", first_name="Alice")
SENT_AT = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
EDITED_AT = datetime(2026, 10, 12, 9, 45, tzinfo=UTC)


class FakeTelegramClient:
    """Stands in for telethon.TelegramClient: no network and no real session file.

    Like the real one, it holds the session file from construction until disconnect(),
    and Telegram answers a call that needs a login with 401 when there is none. The chat
    and its messages live in FakeSessions, shared by every client opened on it. Only the
    methods the server and the CLI call are here.
    """

    def __init__(self, sessions: FakeSessions) -> None:
        self.sessions = sessions
        self.authorized = sessions.authorized
        self.connect_error = sessions.connect_error
        self.file_open = True
        # Deliberately unlike SESSION_PATH, so a test can tell which one the code printed.
        self.session = SimpleNamespace(filename="/fake-home/.telethon-mcp-session.session")
        self.me = OWNER
        self.dialogs: list = []

    async def connect(self) -> None:
        await asyncio.sleep(0)  # the network round trip lets other tasks run
        if self.connect_error is not None:
            raise self.connect_error

    async def disconnect(self) -> None:
        self.file_open = False

    async def is_user_authorized(self) -> bool:
        return self.authorized

    async def get_me(self) -> User | None:
        return self.me if self.authorized else None

    async def start(self, phone, code_callback, password) -> None:
        # The real start() prompts through the callbacks; stdin is captured under pytest.
        self.authorized = True

    async def get_dialogs(self, limit: int) -> list:
        self._require_login()
        return self.dialogs[:limit]

    async def get_entity(self, identifier):
        self._require_login()
        if self.sessions.entity_error is not None:
            raise self.sessions.entity_error
        return self.sessions.chat

    async def get_messages(self, entity, ids: int) -> Message | None:
        self._require_login()
        return self.sessions.messages.get(ids)

    async def edit_message(self, entity, message: int, text: str) -> Message:
        self._require_login()
        edited = self.sessions.messages[message]
        edited.message = text
        edited.edit_date = EDITED_AT
        return edited

    async def delete_messages(self, entity, message_ids: list[int], *, revoke: bool = True):
        self._require_login()
        self.sessions.deleted.append((list(message_ids), revoke))
        for message_id in message_ids:
            self.sessions.messages.pop(message_id, None)
        return [AffectedMessages(pts=1, pts_count=len(message_ids))]

    def _require_login(self) -> None:
        if not self.authorized:
            raise AuthKeyUnregisteredError(request=None)


class FakeSessions:
    """Opens fake clients in place of open_telegram_client and plays Telegram's side.

    `authorized` is what the session file holds right now: setting it to True is what a
    `telethon-mcp login` in another process does. `connect_error` makes the clients
    opened from then on fail to connect. Every identifier resolves to `chat` (or fails
    with `entity_error`), `messages` holds its messages by ID, and `deleted` records the
    delete calls as (message IDs, revoke).
    """

    def __init__(self) -> None:
        self.authorized = False
        self.connect_error: Exception | None = None
        self.opened: list[FakeTelegramClient] = []
        self.chat = ALICE
        self.entity_error: Exception | None = None
        self.messages: dict[int, Message] = {}
        self.deleted: list[tuple[list[int], bool]] = []

    def open(self, session_path: str, api_id: int, api_hash: str) -> FakeTelegramClient:
        client = FakeTelegramClient(self)
        self.opened.append(client)
        return client

    def add_message(self, message_id: int, text: str, *, out: bool) -> Message:
        """A message in the chat; out=True means it was sent from this account."""
        sender = OWNER if out else ALICE
        added = Message(
            id=message_id,
            peer_id=PeerUser(ALICE.id),
            date=SENT_AT,
            message=text,
            out=out,
            from_id=PeerUser(sender.id),
        )
        self.messages[message_id] = added
        return added


@pytest.fixture
def sessions(monkeypatch) -> FakeSessions:
    sessions = FakeSessions()
    monkeypatch.setattr(telethon_mcp.client, "open_telegram_client", sessions.open)
    monkeypatch.setattr(telethon_mcp.cli, "open_telegram_client", sessions.open)
    return sessions


@pytest.fixture
def credentials(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "dummyhash")
