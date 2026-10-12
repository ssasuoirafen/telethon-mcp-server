"""Tests for the telethon-mcp command line: the server by default, `login` and `status`."""

import importlib

import pytest

from telethon_mcp import cli


@pytest.mark.parametrize(("argv", "exit_code"), [(["logn"], 2), (["--help"], 0)])
def test_parsing_needs_no_credentials(monkeypatch, capsys, argv, exit_code):
    """A typo or --help must not first demand a valid environment."""
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)

    with pytest.raises(SystemExit) as exc:
        cli.main(argv)

    assert exc.value.code == exit_code
    assert "Missing env" not in capsys.readouterr().err


def test_no_subcommand_runs_the_server(monkeypatch, credentials, sessions):
    server = importlib.import_module("telethon_mcp.server")
    runs = []
    monkeypatch.setattr(server, "main", lambda: runs.append("server"))

    cli.main([])

    assert runs == ["server"]


def test_status_without_a_session(credentials, sessions, capsys):
    cli.main(["status"])

    assert capsys.readouterr().out == "Not authorized\n"


def test_login_reports_the_account_and_the_file_telethon_wrote(credentials, sessions, capsys):
    cli.main(["login"])

    out = capsys.readouterr().out
    assert "Authorized as @owner (ID: 777)" in out
    assert "Session saved to /fake-home/.telethon-mcp-session.session" in out
