"""Test doubles for the Telegram connection, shared by the client and CLI tests."""

import asyncio
from types import SimpleNamespace

import pytest
from telethon.errors import AuthKeyUnregisteredError
from telethon.tl.types import User

import telethon_mcp.cli
import telethon_mcp.client


class FakeTelegramClient:
    """Stands in for telethon.TelegramClient: no network and no real session file.

    Like the real one, it holds the session file from construction until disconnect(),
    and Telegram answers a call that needs a login with 401 when there is none. Only the
    methods the server and the CLI call are here.
    """

    def __init__(self, *, authorized: bool, connect_error: Exception | None = None) -> None:
        self.authorized = authorized
        self.connect_error = connect_error
        self.file_open = True
        # Deliberately unlike SESSION_PATH, so a test can tell which one the code printed.
        self.session = SimpleNamespace(filename="/fake-home/.telethon-mcp-session.session")
        self.me = User(id=777, username="owner", first_name="Owner")
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

    def _require_login(self) -> None:
        if not self.authorized:
            raise AuthKeyUnregisteredError(request=None)


class FakeSessions:
    """Opens fake clients in place of open_telegram_client and records them.

    `authorized` is what the session file holds right now: setting it to True is what a
    `telethon-mcp login` in another process does. `connect_error` makes the clients
    opened from then on fail to connect.
    """

    def __init__(self) -> None:
        self.authorized = False
        self.connect_error: Exception | None = None
        self.opened: list[FakeTelegramClient] = []

    def open(self, session_path: str, api_id: int, api_hash: str) -> FakeTelegramClient:
        client = FakeTelegramClient(authorized=self.authorized, connect_error=self.connect_error)
        self.opened.append(client)
        return client


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
