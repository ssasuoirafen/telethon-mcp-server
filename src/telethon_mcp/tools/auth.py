"""Tools: interactive Telegram authorization flow."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..client import TelethonMcpClient, handle_error


class AuthStartInput(BaseModel):
    phone: str = Field(
        ..., description="Phone number in international format, e.g. +79991234567"
    )


class AuthSubmitCodeInput(BaseModel):
    code: str = Field(
        ..., description="Login code the user received in the Telegram app or via SMS"
    )


class AuthSubmitPasswordInput(BaseModel):
    password: str = Field(
        ..., description="2FA cloud password (only if enabled on the account)"
    )


def register(mcp: FastMCP, client: TelethonMcpClient) -> None:

    @mcp.tool(
        name="telegram_auth_status",
        annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    )
    async def auth_status() -> str:
        """Check current Telegram authorization status. Returns the logged-in user info or a hint to start auth."""
        try:
            return await client.auth_status()
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="telegram_auth_start",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def auth_start(params: AuthStartInput) -> str:
        """Start Telegram login. Sends a one-time code to the user's Telegram app. After calling this, ask the user for the code they received, then call telegram_auth_submit_code."""
        try:
            return await client.auth_start(params.phone)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="telegram_auth_submit_code",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def auth_submit_code(params: AuthSubmitCodeInput) -> str:
        """Submit the login code received from Telegram. If the account has 2FA, the response will ask for a password — then call telegram_auth_submit_password."""
        try:
            return await client.auth_submit_code(params.code)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="telegram_auth_submit_password",
        annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    )
    async def auth_submit_password(params: AuthSubmitPasswordInput) -> str:
        """Submit the 2FA cloud password to finish login. Only needed if telegram_auth_submit_code asked for it."""
        try:
            return await client.auth_submit_password(params.password)
        except Exception as e:
            return handle_error(e)
