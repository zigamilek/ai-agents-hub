from __future__ import annotations

from argparse import Namespace

import mobius.__main__ as cli


def test_parser_accepts_db_bootstrap_local_command() -> None:
    parser = cli._build_parser()
    args = parser.parse_args(
        [
            "db",
            "bootstrap-local",
            "--db-name",
            "mobius",
            "--db-user",
            "mobius_user",
            "--db-port",
            "5432",
            "--yes",
            "--dry-run",
        ]
    )
    assert args.command == "db"
    assert args.db_command == "bootstrap-local"
    assert args.db_name == "mobius"
    assert args.db_user == "mobius_user"
    assert args.db_port == 5432
    assert args.yes is True
    assert args.dry_run is True


def test_safe_db_identifier_validation() -> None:
    assert cli._is_safe_db_identifier("mobius")
    assert cli._is_safe_db_identifier("mobius_1")
    assert not cli._is_safe_db_identifier("1mobius")
    assert not cli._is_safe_db_identifier("mobius-db")
    assert not cli._is_safe_db_identifier("mobius db")


def test_upsert_env_lines_updates_and_appends() -> None:
    lines = [
        "OPENAI_API_KEY=abc",
        "MOBIUS_API_KEY=old",
        "# comment",
    ]
    updated = cli._upsert_env_lines(
        lines,
        {"MOBIUS_API_KEY": "new", "MOBIUS_STATE_DSN": "postgresql://x"},
    )
    assert "MOBIUS_API_KEY=new" in updated
    assert "MOBIUS_STATE_DSN=postgresql://x" in updated
    assert "OPENAI_API_KEY=abc" in updated
    assert "# comment" in updated


def test_state_dsn_encodes_password() -> None:
    dsn = cli._state_dsn(
        db_user="mobius",
        db_password="p@ss:word",
        db_host="127.0.0.1",
        db_port=5432,
        db_name="mobius",
    )
    assert dsn == "postgresql://mobius:p%40ss%3Aword@127.0.0.1:5432/mobius"


def test_db_bootstrap_dry_run_requires_root_when_supported(monkeypatch, capsys) -> None:
    if not hasattr(cli.os, "geteuid"):
        return
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)
    rc = cli._cmd_db_bootstrap_local(
        Namespace(
            config_path=None,
            env_file=None,
            db_name="mobius",
            db_user="mobius",
            db_password=None,
            db_host="127.0.0.1",
            db_port=5432,
            skip_install=True,
            no_restart=True,
            yes=True,
            dry_run=True,
        )
    )
    output = capsys.readouterr().out
    assert rc == 1
    assert "should be run as root" in output
