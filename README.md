# telethon-mcp-server

Personal MCP server for Telegram via [Telethon](https://github.com/LonamiWebs/Telethon). Uses a user account (not a bot), so you can read and send messages as yourself from Claude Code or any MCP-compatible client.

## Tools

| Tool | Description |
|------|-------------|
| `telegram_resolve_entity` | Resolve username, phone, or numeric ID to entity details |
| `telegram_list_dialogs` | List recent dialogs (chats, channels, users) |
| `telegram_send_message` | Send text message to a user, chat, or channel |
| `telegram_read_history` | Read message history from a chat |
| `telegram_download_media` | Download media (photo, video, document, voice, sticker) from a message |
| `telegram_send_media` | Upload and send a local file as media |

## Configuration

Requires a Telegram API application. Get `api_id` and `api_hash` from [my.telegram.org](https://my.telegram.org/apps).

### Claude Code (`.mcp.json`)

```json
{
  "mcpServers": {
    "telethon-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ssasuoirafen/telethon-mcp-server", "telethon-mcp"],
      "env": {
        "TELEGRAM_API_ID": "your-api-id",
        "TELEGRAM_API_HASH": "your-api-hash"
      }
    }
  }
}
```

| Variable | Description |
|----------|-------------|
| `TELEGRAM_API_ID` | API ID from my.telegram.org |
| `TELEGRAM_API_HASH` | API hash from my.telegram.org |

### Authentication

Log in from a terminal with the command that starts the server, with `login` appended. It prompts for the phone number, the login code, and the 2FA password if the account has one. There are no login tools: the MCP client never sees the code or the password.

The command runs outside the MCP client, so it reads `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from the shell environment - the `env` block in `.mcp.json` never reaches it. Set both first:

```bash
export TELEGRAM_API_ID=your-api-id
export TELEGRAM_API_HASH=your-api-hash

# Interactive login (prompts for phone, code, 2FA password)
uvx --from git+https://github.com/ssasuoirafen/telethon-mcp-server telethon-mcp login

# Verify session
uvx --from git+https://github.com/ssasuoirafen/telethon-mcp-server telethon-mcp status
```

When a tool reports "Not authorized", run the login, then restart the MCP server.

The session is stored at `~/.telethon-mcp-session.session` (Telethon appends `.session`). It holds the account's auth key, so treat it like a password. Delete it to force a fresh login.

## Development

```bash
git clone https://github.com/ssasuoirafen/telethon-mcp-server.git
cd telethon-mcp-server
uv sync
uv run telethon-mcp status
```

## License

MIT
