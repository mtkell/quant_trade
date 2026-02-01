#!/usr/bin/env python
"""Migration CLI: list, apply, rollback migrations for SQLite DB.

Usage (examples):

python scripts/migrate.py --db state.db list
python scripts/migrate.py --db state.db apply
python scripts/migrate.py --db state.db rollback --version 1
python scripts/migrate.py --db state.db rollback --last
"""
import argparse
import sqlite3
from pathlib import Path
import sys
from pathlib import Path as _Path
# Ensure project root is on sys.path so `trading` package is importable when running as a script.
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from trading.db_migrations import MIGRATIONS, apply_migrations, rollback_last, rollback_migration


def list_migrations(conn):
    cur = conn.cursor()
    cur.execute("SELECT version, applied_at FROM schema_migrations ORDER BY version")
    applied = {row[0]: row[1] for row in cur.fetchall()}
    print("Available migrations:")
    for v in sorted(MIGRATIONS.keys()):
        status = "applied" if v in applied else "pending"
        when = applied.get(v, "-")
        print(f"  {v}: {status} (applied_at={when})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to sqlite DB file")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list")
    apply_p = sub.add_parser("apply")
    apply_p.add_argument("--dry-run", action="store_true", help="Show pending migrations without applying them")

    rb = sub.add_parser("rollback")
    rb.add_argument("--version", type=int, help="Rollback a specific migration version")
    rb.add_argument("--last", action="store_true", help="Rollback the last applied migration")
    rb.add_argument("--dry-run", action="store_true", help="Show which migration would be rolled back without performing it")
    rb.add_argument("--yes", action="store_true", help="Do not prompt for confirmation when rolling back")

    args = parser.parse_args()
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db), timeout=30)

    if args.cmd == "list":
        list_migrations(conn)
        return

    if args.cmd == "apply":
        if getattr(args, 'dry_run', False):
            # show pending migrations without applying
            cur = conn.cursor()
            # Create schema_migrations table if missing so we can query it
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            applied = {row[0] for row in cur.fetchall()}
            pending = sorted(v for v in MIGRATIONS.keys() if v not in applied)
            if pending:
                print("Pending migrations:", pending)
            else:
                print("No pending migrations; database up-to-date.")
            return

        applied = apply_migrations(conn)
        if applied:
            print("Applied migrations:", applied)
        else:
            print("No migrations applied; database up-to-date.")
        return

    if args.cmd == "rollback":
        if args.version:
            if getattr(args, 'dry_run', False):
                print(f"Would rollback migration {args.version} (dry-run)")
                return
            if not getattr(args, 'yes', False):
                # For non-interactive/test runs, auto-confirm; for interactive, prompt.
                try:
                    confirm = input(f"Are you sure you want to rollback migration {args.version}? This may DROP data. Type 'yes' to continue: ")
                    if confirm.strip().lower() != 'yes':
                        print("Aborted.")
                        return
                except (EOFError, BrokenPipeError):
                    # Non-interactive or piped stdin; auto-confirm
                    pass
            rollback_migration(conn, args.version)
            print(f"Rolled back migration {args.version}")
            return
        if args.last:
            if getattr(args, 'dry_run', False):
                cur = conn.cursor()
                cur.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
                row = cur.fetchone()
                if not row:
                    print("No applied migrations to rollback")
                else:
                    print(f"Would rollback migration {row[0]} (dry-run)")
                return

            if not getattr(args, 'yes', False):
                cur = conn.cursor()
                cur.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
                row = cur.fetchone()
                if not row:
                    print("No applied migrations to rollback")
                    return
                try:
                    confirm = input(f"Are you sure you want to rollback the last migration {row[0]}? This may DROP data. Type 'yes' to continue: ")
                    if confirm.strip().lower() != 'yes':
                        print("Aborted.")
                        return
                except (EOFError, BrokenPipeError):
                    # Non-interactive or piped stdin; auto-confirm
                    pass

            v = rollback_last(conn)
            if v is None:
                print("No applied migrations to rollback")
            else:
                print(f"Rolled back migration {v}")
            return

    parser.print_help()


if __name__ == '__main__':
    main()
