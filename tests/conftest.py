"""Test doubles for the Telegram connection, shared by the client and CLI tests."""

from types import SimpleNamespace

import pytest
from telethon.tl.types import User

import telethon_mcp.cli
import telethon_mcp.client


class FakeTelegramClient:
    """Stands in for telethon.TelegramClient: no network and no session file.

    Only the methods the server and the CLI call are here.
    """

    def __init__(self, *, authorized: bool) -> None:
        self.authorized = authorized
        self.connected = False
        # Deliberately unlike SESSION_PATH, so a test can tell which one the code printed.
        self.session = SimpleNamespace(filename="/fake-home/.telethon-mcp-session.session")
        self.me = User(id=777, username="owner", first_name="Owner")
        self.dialogs: list = []

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def is_user_authorized(self) -> bool:
        return self.authorized

    async def get_me(self) -> User | None:
        return self.me if self.authorized else None

    async def start(self, phone, code_callback, password) -> None:
        # The real start() prompts through the callbacks; stdin is captured under pytest.
        self.connected = True
        self.authorized = True

    async def get_dialogs(self, limit: int) -> list:
        return self.dialogs[:limit]


class FakeSessions:
    """Opens fake clients in place of open_telegram_client and records them.

    `authorized` is what the session file holds right now: setting it to True is what a
    `telethon-mcp login` in another process does.
    """

    def __init__(self) -> None:
        self.authorized = False
        self.opened: list[FakeTelegramClient] = []

    def open(self, session_path: str, api_id: int, api_hash: str) -> FakeTelegramClient:
        client = FakeTelegramClient(authorized=self.authorized)
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
