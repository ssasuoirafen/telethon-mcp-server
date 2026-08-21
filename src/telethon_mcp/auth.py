"""CLI for Telethon session authorization."""

from __future__ import annotations

import asyncio
import getpass
import sys
from pathlib import Path

from telethon import TelegramClient

from .config import load_credentials

SESSION_PATH = str(Path.home() / ".telethon-mcp-session")


def _make_client(api_id: int, api_hash: str) -> TelegramClient:
    return TelegramClient(SESSION_PATH, api_id, api_hash)


def _me_label(me) -> str:
    if me.username:
        return f"@{me.username}"
    return me.first_name or f"User#{me.id}"


async def _login(api_id: int, api_hash: str) -> None:
    client = _make_client(api_id, api_hash)
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


async def _status(api_id: int, api_hash: str) -> None:
    client = _make_client(api_id, api_hash)
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
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
    if cmd not in ("login", "status"):
        print("Usage: telethon-mcp-auth [login|status]", file=sys.stderr)
        sys.exit(1)

    # Resolved after the subcommand check so a typo does not demand a valid
    # environment first.
    api_id, api_hash = load_credentials()

    if cmd == "login":
        asyncio.run(_login(api_id, api_hash))
    else:
        asyncio.run(_status(api_id, api_hash))


if __name__ == "__main__":
    main()
