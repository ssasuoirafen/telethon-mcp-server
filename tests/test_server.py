"""Tests for server assembly and tool registration surface.

Two import-time hazards in telethon_mcp.server are handled before importing it:

1. TELEGRAM_API_ID / TELEGRAM_API_HASH are validated at module import - dummy
   values are set first.
2. server.py instantiates TelethonMcpClient at module level, whose __init__ is
   NOT lazy: it constructs telethon.TelegramClient, which opens a SQLite session
   file. We stub TelegramClient with a no-op so import does no I/O and no network
   (and to dodge the Telethon 1.42 / Python 3.14 SQLiteSession row-unpack bug).
   The tool closures are never invoked here, so a stub client is sufficient - we
   only assert the registered tool surface.
"""

import os
from unittest.mock import MagicMock

import telethon

os.environ.setdefault("TELEGRAM_API_ID", "12345")
os.environ.setdefault("TELEGRAM_API_HASH", "dummyhash")
telethon.TelegramClient = MagicMock()

from telethon_mcp.server import mcp  # noqa: E402

EXPECTED_TOOLS = {
    "telegram_auth_status",
    "telegram_auth_start",
    "telegram_auth_submit_code",
    "telegram_auth_submit_password",
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
    assert len(_tool_names()) == 10


def test_tool_names():
    assert _tool_names() == EXPECTED_TOOLS
