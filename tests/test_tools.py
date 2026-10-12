"""Tools called through the MCP layer, in-process via `mcp.Client(server.mcp)`.

Telegram is the fakes from conftest.py. These tests pin what reaches the MCP client: a
result, or an error result (`is_error`) carrying a message the agent can act on.
"""

import os

import pytest
from mcp import Client
from telethon.errors import UsernameInvalidError
from telethon.tl.types import Channel, ChatPhotoEmpty

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


def _supergroup() -> Channel:
    return Channel(
        id=1001, title="Support", photo=ChatPhotoEmpty(), date=None, megagroup=True,
        access_hash=1,
    )


async def test_editing_an_own_message_replaces_its_text(sessions):
    sessions.authorized = True
    sessions.add_message(10, "old text", out=True)

    result = await call("telegram_edit_message", identifier="alice", message_id=10, text="new")

    assert not result.is_error, text(result)
    assert sessions.messages[10].message == "new"
    assert "2026-10-12 09:45" in text(result)  # the edit time, UTC


async def test_editing_a_message_from_someone_else_is_refused(sessions):
    sessions.authorized = True
    sessions.add_message(11, "their text", out=False)

    result = await call("telegram_edit_message", identifier="alice", message_id=11, text="x")

    assert result.is_error
    assert sessions.messages[11].message == "their text"


async def test_editing_a_missing_message_is_an_error(sessions):
    sessions.authorized = True

    result = await call("telegram_edit_message", identifier="alice", message_id=12, text="x")

    assert result.is_error
    assert "Message 12 not found" in text(result)


@pytest.mark.parametrize(
    ("for_everyone", "scope"), [(True, "for everyone"), (False, "only for this account")]
)
async def test_deleting_an_own_message_uses_the_chosen_scope(sessions, for_everyone, scope):
    sessions.authorized = True
    sessions.add_message(20, "oops", out=True)

    result = await call(
        "telegram_delete_message", identifier="alice", message_id=20, for_everyone=for_everyone
    )

    assert not result.is_error, text(result)
    assert sessions.deleted == [([20], for_everyone)]
    assert scope in text(result)


async def test_deleting_only_for_this_account_in_a_supergroup_is_refused(sessions):
    # Telethon would silently delete it for everyone: Telegram has no other way there.
    sessions.authorized = True
    sessions.chat = _supergroup()
    sessions.add_message(21, "oops", out=True)

    result = await call(
        "telegram_delete_message", identifier="support", message_id=21, for_everyone=False
    )

    assert result.is_error
    assert sessions.deleted == []


async def test_deleting_for_everyone_in_a_supergroup_works(sessions):
    sessions.authorized = True
    sessions.chat = _supergroup()
    sessions.add_message(22, "oops", out=True)

    result = await call(
        "telegram_delete_message", identifier="support", message_id=22, for_everyone=True
    )

    assert not result.is_error, text(result)
    assert sessions.deleted == [([22], True)]


async def test_deleting_a_message_from_someone_else_is_refused(sessions):
    # In a private chat Telegram would allow it, for both sides.
    sessions.authorized = True
    sessions.add_message(23, "their text", out=False)

    result = await call(
        "telegram_delete_message", identifier="alice", message_id=23, for_everyone=True
    )

    assert result.is_error
    assert sessions.deleted == []
