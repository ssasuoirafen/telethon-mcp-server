"""Tests for identifier parsing in the client.

_parse_id decides whether a tool argument reaches Telethon as a numeric ID or as a
string (username or phone). Telethon resolves a phone number only when it arrives
as a string, so a phone must never be turned into an int.
"""

import pytest

from telethon_mcp.client import TelethonMcpClient

# __init__ opens the Telethon session file; _parse_id needs no state.
client = TelethonMcpClient.__new__(TelethonMcpClient)


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("+79991234567", "+79991234567"),
        ("123456789", 123456789),
        ("-1001234567890", -1001234567890),
        ("@durov", "@durov"),
        ("durov", "durov"),
    ],
)
def test_parse_id(identifier, expected):
    assert client._parse_id(identifier) == expected
