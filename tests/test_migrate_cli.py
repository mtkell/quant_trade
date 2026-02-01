import sqlite3
from pathlib import Path
import subprocess
import sys

from trading.db_migrations import MIGRATIONS


def run_cli(db_path, args):
    cmd = [sys.executable, "scripts/migrate.py", "--db", str(db_path)] + args
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def test_cli_apply_and_list(tmp_path: Path):
    db = tmp_path / "cli.db"
    code, out, err = run_cli(db, ["apply"])
    assert code == 0
    assert "Applied migrations" in out or "No migrations applied" in out

    code, out, err = run_cli(db, ["list"])
    assert code == 0
    assert "Available migrations:" in out


def test_cli_rollback_last(tmp_path: Path):
    db = tmp_path / "cli2.db"
    # ensure applied
    run_cli(db, ["apply"])
    code, out, err = run_cli(db, ["rollback", "--last"])
    assert code == 0
    assert "Rolled back migration" in out or "No applied migrations" in out


def test_cli_apply_dry_run(tmp_path: Path):
    db = tmp_path / "cli3.db"
    # before apply: should show v1 as pending
    code, out, err = run_cli(db, ["apply", "--dry-run"])
    assert code == 0
    assert "Pending migrations:" in out or "No pending migrations" in out
    
    # apply migrations
    code, out, err = run_cli(db, ["apply"])
    assert code == 0
    
    # now dry-run should show no pending
    code, out, err = run_cli(db, ["apply", "--dry-run"])
    assert code == 0
    assert "No pending migrations" in out


def test_cli_rollback_dry_run(tmp_path: Path):
    db = tmp_path / "cli4.db"
    # apply migrations first
    run_cli(db, ["apply"])
    # dry-run rollback should not actually rollback
    code, out, err = run_cli(db, ["rollback", "--last", "--dry-run"])
    assert code == 0
    assert "Would rollback migration" in out or "No applied migrations" in out
    
    # verify migration is still applied
    code, out, err = run_cli(db, ["list"])
    assert code == 0
    assert "applied" in out


def test_cli_rollback_with_yes_flag(tmp_path: Path):
    db = tmp_path / "cli5.db"
    run_cli(db, ["apply"])
    # rollback with --yes should not prompt
    code, out, err = run_cli(db, ["rollback", "--last", "--yes"])
    assert code == 0
    assert "Rolled back migration" in out
    assert "Are you sure" not in out
