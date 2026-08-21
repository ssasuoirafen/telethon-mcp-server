"""Tests for credential loading.

load_credentials() is the single place both entry points read
TELEGRAM_API_ID / TELEGRAM_API_HASH, so the failure modes tested here are
what a user actually sees when the environment is wrong.
"""

import pytest

from telethon_mcp.config import load_credentials


def test_returns_parsed_pair(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "1234567")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abcdef0123456789")
    assert load_credentials() == (1234567, "abcdef0123456789")


def test_surrounding_whitespace_is_tolerated(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "  1234567 ")
    monkeypatch.setenv("TELEGRAM_API_HASH", " abcdef ")
    assert load_credentials() == (1234567, "abcdef")


@pytest.mark.parametrize(
    ("api_id", "api_hash", "expected"),
    [
        (None, None, ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"]),
        (None, "abcdef", ["TELEGRAM_API_ID"]),
        ("1234567", None, ["TELEGRAM_API_HASH"]),
        ("", "", ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"]),
    ],
)
def test_missing_vars_are_named_individually(monkeypatch, capsys, api_id, api_hash, expected):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    if api_id is not None:
        monkeypatch.setenv("TELEGRAM_API_ID", api_id)
    if api_hash is not None:
        monkeypatch.setenv("TELEGRAM_API_HASH", api_hash)

    with pytest.raises(SystemExit) as exc:
        load_credentials()

    assert exc.value.code == 1
    err = capsys.readouterr().err

    # Only the first line lists what is missing; the guidance below it names
    # both variables by design, so exclusivity is asserted on that line alone.
    summary = err.splitlines()[0]
    for name in expected:
        assert name in summary
    for name in {"TELEGRAM_API_ID", "TELEGRAM_API_HASH"} - set(expected):
        assert name not in summary
    assert "my.telegram.org" in err, "message should say where to get the values"


def test_non_numeric_api_id_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_API_ID", "not-a-number")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abcdef")

    with pytest.raises(SystemExit) as exc:
        load_credentials()

    assert exc.value.code == 1
    assert "TELEGRAM_API_ID" in capsys.readouterr().err


def test_bad_api_id_value_is_never_echoed(monkeypatch, capsys):
    """The classic mistake is pasting the hash into the ID slot.

    Echoing the offending value back would print a live secret to stderr and
    into whatever collects it, so the message must describe the problem
    without repeating the input.
    """
    secret = "0123456789abcdef0123456789abcdef"
    monkeypatch.setenv("TELEGRAM_API_ID", secret)
    monkeypatch.setenv("TELEGRAM_API_HASH", secret)

    with pytest.raises(SystemExit):
        load_credentials()

    out = capsys.readouterr()
    assert secret not in out.err
    assert secret not in out.out
