"""CLI for Telethon session authorization."""

from __future__ import annotations

import asyncio
import getpass
import os
import sys
from pathlib import Path

from telethon import TelegramClient

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_PATH = str(Path.home() / ".telethon-mcp-session")


def _make_client() -> TelegramClient:
    return TelegramClient(SESSION_PATH, API_ID, API_HASH)


def _me_label(me) -> str:
    if me.username:
        return f"@{me.username}"
    return me.first_name or f"User#{me.id}"


async def _login() -> None:
    client = _make_client()
    try:
        await client.start(
            phone=lambda: input("Phone: ").strip(),
            code_callback=lambda: input("Code from Telegram: ").strip(),
            password=lambda: getpass.getpass("2FA password: "),
        )
        me = await client.get_me()
        print(f"Authorized as {_me_label(me)} (ID: {me.id})")
        print(f"Session saved to {SESSION_PATH}")
    finally:
        await client.disconnect()


async def _status() -> None:
    client = _make_client()
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"Authorized as {_me_label(me)} (ID: {me.id})")
        else:
            print("Not authorized")
    finally:
        await client.disconnect()


def main() -> None:
    if not API_ID or not API_HASH:
        print("Missing env: TELEGRAM_API_ID, TELEGRAM_API_HASH", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"

    if cmd == "login":
        asyncio.run(_login())
    elif cmd == "status":
        asyncio.run(_status())
    else:
        print("Usage: telethon-mcp-auth [login|status]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
