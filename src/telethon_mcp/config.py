"""Credential loading shared by the MCP server and the auth CLI.

Both entry points need the same two environment variables, and both used to
read them at module import - which meant a non-numeric TELEGRAM_API_ID blew up
with an int() traceback before the "missing env" check could ever run. Reading
them here, on call, keeps every bad-environment case on the same clean path.
"""

from __future__ import annotations

import os
import sys
from typing import NoReturn

API_ID_VAR = "TELEGRAM_API_ID"
API_HASH_VAR = "TELEGRAM_API_HASH"

_HOW_TO_SET = (
    "Both come from https://my.telegram.org (API development tools).\n"
    f"  bash:       export {API_ID_VAR}=1234567\n"
    f"  PowerShell: $env:{API_ID_VAR} = '1234567'\n"
    "The MCP server gets these from the env block in .mcp.json, but the CLI "
    "runs outside the MCP client and reads them from the shell."
)


def load_credentials() -> tuple[int, str]:
    """Return (api_id, api_hash) from the environment, or exit 1 with guidance."""
    api_id = os.environ.get(API_ID_VAR, "").strip()
    api_hash = os.environ.get(API_HASH_VAR, "").strip()

    missing = [name for name, val in ((API_ID_VAR, api_id), (API_HASH_VAR, api_hash)) if not val]
    if missing:
        _fail(f"Missing env: {', '.join(missing)}")

    try:
        return int(api_id), api_hash
    except ValueError:
        # Deliberately not echoing the value: the usual way to get here is
        # pasting the api_hash into the api_id slot, and repeating it back
        # would print a live secret to stderr and into anything capturing it.
        _fail(
            f"{API_ID_VAR} must be the numeric app id, not the api_hash "
            "(got a non-numeric value)."
        )


def _fail(problem: str) -> NoReturn:
    print(f"{problem}\n{_HOW_TO_SET}", file=sys.stderr)
    sys.exit(1)
