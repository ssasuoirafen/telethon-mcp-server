"""CLI for Telethon session authorization."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from telethon import TelegramClient

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_PATH = str(Path.home() / ".telethon-mcp-session")


def _make_client() -> TelegramClient:
    return TelegramClient(SESSION_PATH, API_ID, API_HASH)


async def _request_code(phone: str) -> None:
    client = _make_client()
    await client.connect()
    try:
        if await client.is_user_authorized():
            print("ALREADY_AUTHORIZED")
            return
        result = await client.send_code_request(phone)
        print(f"PHONE_CODE_HASH={result.phone_code_hash}")
    finally:
        await client.disconnect()


async def _sign_in(
    phone: str, code: str, phone_code_hash: str, password: str | None = None
) -> None:
    client = _make_client()
    await client.connect()
    try:
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except Exception as e:
            if "SessionPasswordNeeded" in type(e).__name__:
                if not password:
                    print("2FA_REQUIRED")
                    return
                await client.sign_in(password=password)
            else:
                raise
        print("AUTH_OK")
    finally:
        await client.disconnect()


async def _status() -> None:
    client = _make_client()
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            username = f"@{me.username}" if me.username else me.first_name
            print(f"Authorized as {username} (ID: {me.id})")
        else:
            print("Not authorized")
    finally:
        await client.disconnect()


def main() -> None:
    if not API_ID or not API_HASH:
        print("Missing env: TELEGRAM_API_ID, TELEGRAM_API_HASH", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage:")
        print(f"  {sys.argv[0]} request-code <phone>")
        print(f"  {sys.argv[0]} sign-in <phone> <code> <hash> [2fa_password]")
        print(f"  {sys.argv[0]} status")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "request-code":
        asyncio.run(_request_code(sys.argv[2]))
    elif cmd == "sign-in":
        password = sys.argv[5] if len(sys.argv) > 5 else None
        asyncio.run(_sign_in(sys.argv[2], sys.argv[3], sys.argv[4], password))
    elif cmd == "status":
        asyncio.run(_status())
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
