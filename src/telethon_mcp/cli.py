"""Command line: `telethon-mcp` runs the MCP server, `login` and `status` manage the session."""

from __future__ import annotations

import argparse
import asyncio
import getpass

from .client import SESSION_PATH, open_telegram_client
from .config import load_credentials


def _me_label(me) -> str:
    if me.username:
        return f"@{me.username}"
    return me.first_name or f"User#{me.id}"


async def _login(api_id: int, api_hash: str) -> None:
    client = open_telegram_client(SESSION_PATH, api_id, api_hash)
    try:
        await client.start(
            phone=lambda: input("Phone: ").strip(),
            code_callback=lambda: input("Code from Telegram: ").strip(),
            password=lambda: getpass.getpass("2FA password: "),
        )
        me = await client.get_me()
        print(f"Authorized as {_me_label(me)} (ID: {me.id})")
        print(f"Session saved to {client.session.filename}")
    finally:
        await client.disconnect()


async def _status(api_id: int, api_hash: str) -> None:
    client = open_telegram_client(SESSION_PATH, api_id, api_hash)
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"Authorized as {_me_label(me)} (ID: {me.id})")
        else:
            print("Not authorized")
    finally:
        await client.disconnect()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="telethon-mcp",
        description=(
            "MCP server for Telegram over stdio. Needs TELEGRAM_API_ID and TELEGRAM_API_HASH."
        ),
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser(
        "login", help="log in to Telegram in this terminal: phone, code, 2FA password"
    )
    commands.add_parser("status", help="show the account the session is authorized as")
    args = parser.parse_args(argv)

    if args.command is None:
        # Imported only here: the server module reads and validates the credentials at
        # import, and --help or a mistyped subcommand must not demand them.
        from .server import main as run_server

        run_server()
        return

    api_id, api_hash = load_credentials()
    if args.command == "login":
        asyncio.run(_login(api_id, api_hash))
    else:
        asyncio.run(_status(api_id, api_hash))


if __name__ == "__main__":
    main()
