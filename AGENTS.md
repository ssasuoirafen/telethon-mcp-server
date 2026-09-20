# Telethon MCP Server

## Project Overview <!-- last reviewed: 2026-08-21 -->

Personal MCP server for Telegram via Telethon (user account, not bot). Python 3.12+, capped below 3.14 (dev pinned to 3.13 via `.python-version`) - the cap is precautionary and untested, see Known Quirks. MCPServer from `mcp[cli]` 2.x (pinned `>=2.0.0,<3` - mcp 2.0 renamed FastMCP to MCPServer and moved it to `mcp.server.mcpserver`), Telethon 1.44+ (pinned `>=1.44,<2` - the SQLite session schema migrates one-way), Pydantic 2.0+.

Used by the `xray-vpn` project (see its `.mcp.json`) for admin notifications and user support via Telegram.

## Commands

```bash
# Install dependencies
uv sync

# First-time login (interactive: phone, code, optional 2FA password)
# Needs TELEGRAM_API_ID / TELEGRAM_API_HASH exported in the shell: the CLI runs
# outside the MCP client, so the env block in .mcp.json never reaches it
uv run telethon-mcp-auth login        # default subcommand
uv run telethon-mcp-auth status       # check session

# Run the server standalone
uv run telethon-mcp

# Run via MCP inspector (for debugging)
npx @modelcontextprotocol/inspector uv run telethon-mcp
```

## Environment Variables

- `TELEGRAM_API_ID` (required) - Telegram app API ID (https://my.telegram.org)
- `TELEGRAM_API_HASH` (required) - Telegram app API hash

## Architecture

**Entry point**: `src/telethon_mcp/server.py` - creates the `MCPServer` instance, instantiates persistent `TelethonMcpClient`, wires it into lifespan (`connect` on startup, `disconnect` on shutdown), registers all tool modules.

**Client wrapper**: `src/telethon_mcp/client.py` - `TelethonMcpClient` wraps `telethon.TelegramClient`. One method per tool. Session file at `~/.telethon-mcp-session` (hardcoded). `_ensure_authorized()` guard raises `RuntimeError` if session not authorized.

**Credentials**: `src/telethon_mcp/config.py` - `load_credentials()` reads and validates `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`, or exits 1 with guidance. Shared by `server.py` and `auth.py` so both fail the same way. Never echoes the offending value: the usual mistake is pasting the api_hash into the api_id slot.

**Auth CLI**: `src/telethon_mcp/auth.py` - standalone `telethon-mcp-auth` entry point for interactive login outside the MCP flow. Default: `login`; also `status`.

**Tool modules**: `src/telethon_mcp/tools/` - each module exports `register(mcp, client)` with `@mcp.tool()` async functions.

### Tool modules

- `auth.py` - `telegram_auth_status`, `telegram_auth_start`, `telegram_auth_submit_code`, `telegram_auth_submit_password`
- `entities.py` - `telegram_resolve_entity`
- `messages.py` - `telegram_send_message`, `telegram_read_history`
- `dialogs.py` - `telegram_list_dialogs`
- `media.py` - `telegram_download_media`, `telegram_send_media`

## Known Quirks

- **Session path hardcoded** at `~/.telethon-mcp-session` in `client.py`. Not overridable via env.
- **Session schema migrates one-way** - Telethon rewrites `~/.telethon-mcp-session` in place when it bumps the schema (v7 -> v8 added a `tmp_auth_key` column). A session file touched by 1.44 can no longer be opened by 1.42, which dies with `ValueError: too many values to unpack (expected 5)`. Keep the dependency floor and `uv.lock` on the same Telethon, or `uv run` and `uvx` fight over the same file. An earlier version of this note blamed that row-shape error on Python 3.14's sqlite3; it was actually observed on 3.13.12, so the cause is Telethon's own migration. Whether 3.14 breaks separately has not been tested - the `<3.14` cap stays as a precaution, not as a diagnosed bug.
- **Env vars validated at import** (top-level in `server.py`, via `config.load_credentials()`) - a missing or non-numeric `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` exits immediately with a clear stderr message. Like remnawave-mcp-server, this fails fast at import rather than deferring to the first tool call. The CLI resolves the same credentials in `main()` instead, so a mistyped subcommand does not first demand a valid environment.
- **Lifespan tolerates unauthorized session** - server starts and emits stderr warning. Tools then raise `RuntimeError` via `_ensure_authorized()` until user runs auth flow.
- **2FA is two-step at MCP level**: `telegram_auth_submit_code` detects `SessionPasswordNeededError` and returns a prompt for password; client must then call `telegram_auth_submit_password`.
- **No logging configured** - errors surface only through `handle_error()` as tool return strings.
- **Flood-wait errors from Telegram** are not retried/backed off - propagate to tool return as raw error strings.

## Adding a New Tool

1. Add a method on `TelethonMcpClient` in `client.py` (start with `await self._ensure_authorized()` if auth required)
2. Create or pick a module in `src/telethon_mcp/tools/`
3. Define Pydantic input model with `Field` descriptions
4. Write `register(mcp, client)` with `@mcp.tool()` async function that calls the client method
5. Import and call `module.register(mcp, client)` in `server.py`

## Usage

Local dev (path install) from consumer project's `.mcp.json`:

```json
{"command": "uv", "args": ["run", "--project", "<path-to-repo>", "telethon-mcp"]}
```

Remote install from git (see README for full example):

```json
{"command": "uvx", "args": ["--from", "git+https://github.com/ssasuoirafen/telethon-mcp-server", "telethon-mcp"]}
```

## Git

- Single branch (`main`). CI (`.github/workflows/ci.yml`): `uv sync` + pytest + advisory ruff on push/PR
- ruff + pytest in the dev group (`uv sync`); tool-registration and credential-loading tests in `tests/` (`uv run pytest`). No pre-commit hooks; ruff is advisory in CI until the pre-existing source lint is cleaned

## Conventions

- Tool names prefixed with `telegram_` (e.g., `telegram_send_message`)
- Package manager: `uv`, build backend: hatchling
- All tools return `str` (markdown)

## Backlog

- Groups/channels: read history, search, write
- Extended media: send voice/video notes, send stickers (download/recognition already done)
- Message forwarding
