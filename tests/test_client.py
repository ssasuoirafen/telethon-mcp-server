"""Tests for the client wrapper: identifier parsing and the session lifecycle.

_parse_id decides whether a tool argument reaches Telethon as a numeric ID or as a
string (username or phone). Telethon resolves a phone number only when it arrives
as a string, so a phone must never be turned into an int.

The session tests run on fakes from conftest.py: `sessions.authorized` is what the
session file holds, and flipping it to True stands for `telethon-mcp login` run in a
terminal while the server is up.
"""

import asyncio
import os
import sqlite3
import stat
import sys
from datetime import UTC, datetime

import pytest
from telethon.tl.types import PeerUser, User
from telethon.tl.types.contacts import ResolvedPeer
from telethon.tl.types.updates import State

from telethon_mcp.client import TelethonMcpClient, open_telegram_client

client = TelethonMcpClient(12345, "dummyhash")


def _write_lock_is_free(session_file) -> bool:
    """Whether another process could write the session file right now."""
    probe = sqlite3.connect(session_file, timeout=0)
    try:
        probe.execute("BEGIN IMMEDIATE")
        probe.rollback()
        return True
    except sqlite3.OperationalError:  # "database is locked"
        return False
    finally:
        probe.close()


def _cache_entities(session) -> None:
    # Telethon does this with the entities of every result and every update.
    owner = User(id=777, access_hash=4242, username="owner", first_name="Owner")
    session.process_entities(ResolvedPeer(PeerUser(777), [owner], []))


def _save_update_state(session) -> None:
    # Telethon does this when its in-memory entity cache overflows.
    session.set_update_state(0, State(pts=1, qts=0, date=datetime.now(UTC), seq=0, unread_count=0))


def _look_up_a_duplicate_username(session) -> None:
    old = User(id=1, access_hash=11, username="dup", first_name="Old")
    new = User(id=2, access_hash=22, username="dup", first_name="New")
    session.process_entities(ResolvedPeer(PeerUser(2), [old, new], []))
    session.save()  # only the lookup below is under test
    # The lookup clears the username on the older row: a write inside a read.
    session.get_entity_rows_by_username("dup")


@pytest.mark.parametrize(
    "write",
    [_cache_entities, _save_update_state, _look_up_a_duplicate_username],
    ids=["entities", "update state", "duplicate username"],
)
async def test_session_writes_leave_the_file_unlocked(tmp_path, write):
    """Every MCP client session runs its own server process on the same file."""
    opened = open_telegram_client(str(tmp_path / "telethon"), 12345, "dummyhash")
    try:
        write(opened.session)

        assert _write_lock_is_free(tmp_path / "telethon.session")
    finally:
        await opened.disconnect()


@pytest.mark.skipif(sys.platform == "win32", reason="os.chmod only sets the read-only flag there")
@pytest.mark.parametrize("existing_mode", [None, 0o644], ids=["new file", "existing 0644 file"])
async def test_session_file_is_readable_only_by_its_owner(tmp_path, existing_mode):
    # The file holds the auth key: whoever reads it has the account, 2FA included.
    session_file = tmp_path / "telethon.session"
    if existing_mode is not None:
        session_file.touch()
        os.chmod(session_file, existing_mode)
    old_umask = os.umask(0o022)  # the usual umask, under which SQLite creates 0644 files
    try:
        opened = open_telegram_client(str(tmp_path / "telethon"), 12345, "dummyhash")
    finally:
        os.umask(old_umask)

    try:
        assert stat.S_IMODE(session_file.stat().st_mode) == 0o600
    finally:
        await opened.disconnect()


async def _start(sessions, *, authorized: bool) -> TelethonMcpClient:
    """A client after the server's startup, with the session file in the given state."""
    sessions.authorized = authorized
    started = TelethonMcpClient(12345, "dummyhash")
    await started.connect()
    return started


def _revoke(sessions) -> None:
    """Terminate the session from another device: Telegram answers 401 from now on."""
    sessions.authorized = False
    for opened in sessions.opened:
        opened.authorized = False


async def test_tool_call_without_a_session_points_at_the_login_command(sessions):
    unauthorized = TelethonMcpClient(12345, "dummyhash")

    with pytest.raises(RuntimeError) as exc:
        await unauthorized.list_dialogs()

    message = str(exc.value)
    # The server instructions key off this prefix.
    assert message.startswith("Not authorized")
    assert "`telethon-mcp login`" in message


async def test_startup_without_a_login_releases_the_session_file(sessions):
    started = await _start(sessions, authorized=False)

    assert not started.is_authorized()
    assert [opened.file_open for opened in sessions.opened] == [False]


async def test_login_from_a_terminal_is_picked_up_without_a_restart(sessions):
    started = await _start(sessions, authorized=False)

    sessions.authorized = True

    assert await started.list_dialogs() == "No dialogs found."


async def test_authorized_session_is_reused_across_calls(sessions):
    started = await _start(sessions, authorized=True)

    await started.list_dialogs()
    await started.list_dialogs()

    assert len(sessions.opened) == 1


async def test_revoked_session_is_dropped_with_not_authorized(sessions):
    started = await _start(sessions, authorized=True)
    _revoke(sessions)

    with pytest.raises(RuntimeError) as exc:
        await started.list_dialogs()

    assert str(exc.value).startswith("Not authorized")
    assert not sessions.opened[0].file_open


async def test_login_after_a_revoked_session_is_picked_up(sessions):
    started = await _start(sessions, authorized=True)
    _revoke(sessions)
    with pytest.raises(RuntimeError):
        await started.list_dialogs()

    sessions.authorized = True

    assert await started.list_dialogs() == "No dialogs found."


async def test_concurrent_calls_open_one_connection(sessions):
    started = await _start(sessions, authorized=False)
    sessions.authorized = True

    results = await asyncio.gather(started.list_dialogs(), started.list_dialogs())

    assert results == ["No dialogs found.", "No dialogs found."]
    # the startup check, then a single reopen that both calls share
    assert [opened.file_open for opened in sessions.opened] == [False, True]


async def test_failed_reopen_releases_the_session_file(sessions):
    started = await _start(sessions, authorized=False)
    sessions.connect_error = ConnectionError("Network is unreachable")

    with pytest.raises(ConnectionError):
        await started.list_dialogs()

    assert not sessions.opened[-1].file_open


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("+79991234567", "+79991234567"),
        ("123456789", 123456789),
        ("-1001234567890", -1001234567890),
        ("@durov", "@durov"),
        ("durov", "durov"),
    ],
)
def test_parse_id(identifier, expected):
    assert client._parse_id(identifier) == expected
