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
    "telethon": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ssasuoirafen/telethon-mcp-server", "telethon-mcp-server"],
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

First-time auth is a two-phase flow via the `telethon-mcp-auth` CLI:

```bash
# Request login code (sent to your Telegram account)
uvx --from git+https://github.com/ssasuoirafen/telethon-mcp-server telethon-mcp-auth request-code

# Sign in with the received code
uvx --from git+https://github.com/ssasuoirafen/telethon-mcp-server telethon-mcp-auth sign-in --code 12345

# Verify session
uvx --from git+https://github.com/ssasuoirafen/telethon-mcp-server telethon-mcp-auth status
```

Session is stored at `~/.telethon-mcp-session`. Once authenticated, the MCP server picks up the session automatically.

## Development

```bash
git clone https://github.com/ssasuoirafen/telethon-mcp-server.git
cd telethon-mcp-server
uv sync
uv run telethon-mcp-auth status
```

## License

MIT
