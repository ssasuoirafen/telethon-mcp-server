"""Tests for the client wrapper: identifier parsing and the session lifecycle.

_parse_id decides whether a tool argument reaches Telethon as a numeric ID or as a
string (username or phone). Telethon resolves a phone number only when it arrives
as a string, so a phone must never be turned into an int.

The session tests run on fakes from conftest.py: `sessions.authorized` is what the
session file holds, and flipping it to True stands for `telethon-mcp login` run in a
terminal while the server is up.
"""

import asyncio

import pytest

from telethon_mcp.client import TelethonMcpClient

client = TelethonMcpClient(12345, "dummyhash")


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
