# Telethon MCP Server

## Project Overview <!-- last reviewed: 2026-08-21 -->

Personal MCP server for Telegram via Telethon (user account, not bot). Python 3.12+ (dev pins 3.14 via `.python-version`). MCPServer from `mcp[cli]` 2.x (pinned `>=2.0.0,<3` - mcp 2.0 renamed FastMCP to MCPServer and moved it to `mcp.server.mcpserver`), Telethon 1.45+ (pinned `>=1.45,<2` - the SQLite session schema migrates one-way), Pydantic 2.0+.

Used by the `xray-vpn` project (see its `.mcp.json`) for admin notifications and user support via Telegram.

## Commands

```bash
# Install dependencies
uv sync

# Login (interactive: phone, code, optional 2FA password)
# Needs TELEGRAM_API_ID / TELEGRAM_API_HASH exported in the shell: the CLI runs
# outside the MCP client, so the env block in .mcp.json never reaches it
uv run telethon-mcp login
uv run telethon-mcp status            # check session

# Run the server standalone (no subcommand)
uv run telethon-mcp

# Run via MCP inspector (for debugging)
npx @modelcontextprotocol/inspector uv run telethon-mcp
```

## Environment Variables

- `TELEGRAM_API_ID` (required) - Telegram app API ID (https://my.telegram.org)
- `TELEGRAM_API_HASH` (required) - Telegram app API hash

## Architecture

**CLI**: `src/telethon_mcp/cli.py` - the `telethon-mcp` entry point. No subcommand runs the MCP server; `login` logs in interactively in the terminal (Telethon's `start()`: phone, code, 2FA password via `getpass`); `status` shows the authorized account.

**Server**: `src/telethon_mcp/server.py` - creates the `MCPServer` instance with `instructions`, instantiates persistent `TelethonMcpClient`, wires it into lifespan (`connect` on startup, `disconnect` on shutdown), registers all tool modules.

**Client wrapper**: `src/telethon_mcp/client.py` - `TelethonMcpClient` wraps `telethon.TelegramClient`. One method per tool. `open_telegram_client()` opens the session file at `SESSION_PATH` for both the server and the CLI. The wrapper keeps a connection only while the session is authorized (`_open()`). `@_requires_login` on every tool method reopens from the session file when there is no connection (`_ensure_authorized()`), raises `TelethonMcpError(NOT_AUTHORIZED)` when there is still no login, and turns a 401 from Telegram into the same error. The client raises `TelethonMcpError` for every anticipated failure it detects itself and stays unaware of MCP.

**Credentials**: `src/telethon_mcp/config.py` - `load_credentials()` reads and validates `TELEGRAM_API_ID`/`TELEGRAM_API_HASH`, or exits 1 with guidance. Shared by `server.py` and `cli.py` so both fail the same way. Never echoes the offending value: the usual mistake is pasting the api_hash into the api_id slot.

**Tool modules**: `src/telethon_mcp/tools/` - each module exports `register(mcp, client)` with async functions registered through `register_tool` from `tools/common.py`, which also holds the shared identifier description and the annotation presets.

### Error handling

- mcp 2.x passes only `ToolError` text to the client (an `is_error` result prefixed `Error executing tool <name>: `). Any other exception is a crash: the client sees only `Error executing tool <name>`, and the traceback goes to the server's stderr
- `register_tool` re-raises the anticipated failures (`ANTICIPATED_ERRORS`: `TelethonMcpError`, Telethon's `RPCError`, `OSError`) as `ToolError` and leaves everything else a crash, so real bugs keep their traceback. `ValueError` is deliberately not in the list: Telethon raises it for an identifier that resolves to nothing, so `_get_entity()` converts that one case and other `ValueError`s stay bugs
- Tools return `str` (markdown) on success; a missing message or media is a failure, not a notice

### Login

- No login tools: the only way in is `telethon-mcp login` in a terminal (the command that starts the server, with `login` appended). The agent never relays a login code or the 2FA password
- `NOT_AUTHORIZED` (`client.py`) tells the agent to ask the user to run that command and retry; the server instructions key off its "Not authorized" prefix
- A running server picks up the login on the next tool call, without a restart (see Known Quirks)

### Tool modules

- `entities.py` - `telegram_resolve_entity`
- `messages.py` - `telegram_send_message`, `telegram_read_history`, `telegram_edit_message`, `telegram_delete_message`
- `dialogs.py` - `telegram_list_dialogs`
- `media.py` - `telegram_download_media`, `telegram_send_media`

## Known Quirks

- **Session path hardcoded** as `SESSION_PATH` in `client.py`. Not overridable via env. Telethon appends `.session`, so the file on disk is `~/.telethon-mcp-session.session`; delete it to force a fresh login. It holds the auth key, so `open_telegram_client()` sets it to 0600 on every open (on Windows `os.chmod` only clears the read-only flag).
- **Session schema migrates one-way** - Telethon rewrites the session file in place when it bumps the schema (v7 -> v8 added a `tmp_auth_key` column). A session file touched by 1.44 can no longer be opened by 1.42, which dies with `ValueError: too many values to unpack (expected 5)`. Keep the dependency floor and `uv.lock` on the same Telethon, or `uv run` and `uvx` fight over the same file. That error was observed on Python 3.13.12, so it comes from Telethon's migration, not from Python 3.14's sqlite3. Python 3.14 was later checked on its own (tests plus an offline session round-trip) and showed no problem, so the precautionary `<3.14` cap was dropped.
- **Env vars validated at import** (top-level in `server.py`, via `config.load_credentials()`) - a missing or non-numeric `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` exits immediately with a clear stderr message. Like remnawave-mcp-server, this fails fast at import rather than deferring to the first tool call. `cli.main()` parses the arguments first and imports `server.py` only when no subcommand is given, so `--help` or a mistyped subcommand does not first demand a valid environment.
- **Lifespan tolerates unauthorized session** - server starts and emits stderr warning. Tools return `NOT_AUTHORIZED` until the user runs `telethon-mcp login`.
- **Session writes are committed at once** - Telethon caches the entities of every result and update in the session file but commits them only once a minute, and the open transaction write-locks the file until then. Every MCP client session runs its own server process on that file, as do `login` and `status`, so `_CommittingSession` (`client.py`) commits right after the writes Telethon 1.45 defers: `process_entities`, `set_update_state`, and `get_entity_rows_by_username` (it clears stale duplicate usernames). Re-check that list when the lock moves to a newer Telethon; `test_session_writes_leave_the_file_unlocked` covers the three.
- **Login picked up without a restart** - the server does not keep an unauthorized connection, so it holds no session file while a terminal login writes it. A tool call without a connection opens a new `TelegramClient` from the session file, under a lock so parallel calls share one. Re-checking the old client would never see the login: Telethon caches `is_user_authorized()` per client, and a login may switch to another DC and write a new auth key. A 401 from Telegram (`UnauthorizedError`, e.g. the session was terminated from another device) drops the connection and returns `NOT_AUTHORIZED`.
- **Edit and delete only own messages** - `_own_message()` refuses a message that is missing or was not sent from this account, although Telegram lets a private chat delete the other side's messages too. `telegram_delete_message` takes `for_everyone` without a default. Supergroups and channels cannot delete a message only for this account, and Telethon's `delete_messages(revoke=False)` silently deletes it for everyone there, so that combination is refused before any call.
- **No logging configured** - failures reach the client as MCP errors (see Error handling); crashes leave their traceback on the server's stderr.
- **Flood-wait errors from Telegram** are not retried/backed off - they reach the client as MCP errors carrying Telegram's message.

## Adding a New Tool

1. Add a method on `TelethonMcpClient` in `client.py`; if it needs the login, decorate it with `@_requires_login` and use `self._client`. Resolve chats with `_get_entity()` and raise `TelethonMcpError` for failures the agent can act on
2. Create or pick a module in `src/telethon_mcp/tools/`
3. Define Pydantic input model with `Field` descriptions (`IDENTIFIER_DESCRIPTION` for a chat argument)
4. Write `register(mcp, client)` with an async function under `@register_tool(mcp, name=..., annotations=<preset>)` that calls the client method
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

- Single branch (`main`). CI (`.github/workflows/ci.yml`): `uv sync` + ruff + pytest on push/PR
- ruff + pytest in the dev group (`uv sync`); tests in `tests/` (`uv run pytest`) cover tool registration, credential loading, the CLI, the client's authorization handling, and what tools return through the MCP layer (`test_tools.py`, in-process `mcp.Client`), with a fake `TelegramClient` from `conftest.py` instead of the network. No pre-commit hooks; ruff fails CI, so run `uv run ruff check .` before pushing

## Conventions

- Tool names prefixed with `telegram_` (e.g., `telegram_send_message`)
- Package manager: `uv`, build backend: hatchling
- Tools return `str` (markdown); failures raise (see Error handling)

## Backlog

- Groups/channels: read history, search, write
- Extended media: send voice/video notes, send stickers (download/recognition already done)
- Message forwarding
