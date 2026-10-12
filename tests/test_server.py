"""Tests for server assembly and tool registration surface.

TELEGRAM_API_ID / TELEGRAM_API_HASH are validated at module import, so dummy values
are set before importing telethon_mcp.server. The import opens no session file: the
client connects in the lifespan, which these tests never run.
"""

import os

os.environ.setdefault("TELEGRAM_API_ID", "12345")
os.environ.setdefault("TELEGRAM_API_HASH", "dummyhash")

from telethon_mcp.server import mcp  # noqa: E402

EXPECTED_TOOLS = {
    "telegram_edit_message",
    "telegram_delete_message",
    "telegram_resolve_entity",
    "telegram_send_message",
    "telegram_read_history",
    "telegram_list_dialogs",
    "telegram_download_media",
    "telegram_send_media",
}


def _tool_names() -> set[str]:
    return {tool.name for tool in mcp._tool_manager.list_tools()}


def test_tool_count():
    assert len(_tool_names()) == 8


def test_tool_names():
    assert _tool_names() == EXPECTED_TOOLS
