"""Tools called through the MCP layer, in-process via `mcp.Client(server.mcp)`.

Telegram is the fakes from conftest.py. These tests pin what reaches the MCP client: a
result, or an error result (`is_error`) carrying a message the agent can act on.
"""

import os

import pytest
from mcp import Client
from telethon.errors import UsernameInvalidError

os.environ.setdefault("TELEGRAM_API_ID", "12345")
os.environ.setdefault("TELEGRAM_API_HASH", "dummyhash")

from telethon_mcp import server  # noqa: E402


@pytest.fixture(autouse=True)
async def disconnect_after_test(sessions):
    """The server's client outlives a test; drop its connection to the fakes afterwards."""
    yield
    await server.client.disconnect()


async def call(name: str, **params):
    async with Client(server.mcp) as client:
        return await client.call_tool(name, {"params": params})


def text(result) -> str:
    return result.content[0].text


async def test_call_without_a_login_is_an_error(sessions):
    result = await call("telegram_list_dialogs", limit=1)

    assert result.is_error
    assert "Not authorized" in text(result)
    assert "`telethon-mcp login`" in text(result)


@pytest.mark.parametrize(
    "failure",
    [
        ValueError('No user has "nobody" as username'),
        UsernameInvalidError(request=None),
        ConnectionError("Cannot send requests while disconnected"),
    ],
    ids=["unknown username", "Telegram refusal", "network"],
)
async def test_anticipated_failures_reach_the_client_as_errors(sessions, failure):
    sessions.authorized = True
    sessions.entity_error = failure

    result = await call("telegram_send_message", identifier="nobody", text="hi")

    assert result.is_error
    assert str(failure) in text(result)


async def test_a_bug_stays_a_crash_and_keeps_its_details_out(sessions):
    sessions.authorized = True
    sessions.entity_error = TypeError("internal detail")

    result = await call("telegram_send_message", identifier="alice", text="hi")

    assert result.is_error
    assert "internal detail" not in text(result)


async def test_downloading_a_missing_message_is_an_error(sessions):
    sessions.authorized = True

    result = await call("telegram_download_media", identifier="alice", message_id=5)

    assert result.is_error
    assert "Message 5 not found" in text(result)
