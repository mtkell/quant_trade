from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional


def _migration_1(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            position_id TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            position_id TEXT,
            value TEXT NOT NULL,
            state TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER
        )
        """
    )


def _migration_1_down(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS orders")
    cur.execute("DROP TABLE IF EXISTS positions")
    cur.execute("DROP TABLE IF EXISTS kv")
    conn.commit()


def _migration_2(conn):
    """Add indices for faster queries during reconciliation."""
    cur = conn.cursor()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_positions_id ON positions(position_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_position_id ON orders(position_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state)")
    conn.commit()


def _migration_2_down(conn):
    """Drop indices."""
    cur = conn.cursor()
    cur.execute("DROP INDEX IF EXISTS idx_positions_id")
    cur.execute("DROP INDEX IF EXISTS idx_orders_position_id")
    cur.execute("DROP INDEX IF EXISTS idx_orders_state")
    conn.commit()


MIGRATIONS: Dict[int, Callable] = {
    1: _migration_1,
    2: _migration_2,
}

# Optional down migrations
MIGRATION_DOWNS: Dict[int, Callable] = {
    1: _migration_1_down,
    2: _migration_2_down,
}


def apply_migrations(conn) -> List[int]:
    """Apply pending migrations to the given sqlite3 connection.

    Returns the list of applied migration versions.
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # get applied versions
    cur.execute("SELECT version FROM schema_migrations ORDER BY version")
    applied = {row[0] for row in cur.fetchall()}

    to_apply = sorted(v for v in MIGRATIONS.keys() if v not in applied)
    applied_now = []
    for v in to_apply:
        # run migration inside transaction
        try:
            conn.execute("BEGIN IMMEDIATE")
            MIGRATIONS[v](conn)
            cur.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (v, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            applied_now.append(v)
        except Exception:
            conn.rollback()
            raise

    return applied_now


def rollback_migration(conn, version: int) -> None:
    """Rollback a specific migration version if a down migration is registered."""
    if version not in MIGRATION_DOWNS:
        raise RuntimeError(f"No down migration registered for version {version}")

    cur = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        MIGRATION_DOWNS[version](conn)
        cur.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def rollback_last(conn) -> Optional[int]:
    """Rollback the latest applied migration if possible; returns rolled-back version or None."""
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return None
    v = row[0]
    rollback_migration(conn, v)
    return v
