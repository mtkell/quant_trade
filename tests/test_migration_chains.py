"""Test migration chains: apply and rollback multiple versions."""
import sqlite3
from pathlib import Path

from trading.db_migrations import MIGRATIONS, apply_migrations, rollback_last, rollback_migration


def test_migration_chain_v1_v2_apply(tmp_path: Path):
    """Apply v1 then v2, verify both are applied."""
    db = tmp_path / "chain.db"
    conn = sqlite3.connect(str(db), timeout=30)
    
    # Apply all migrations
    applied = apply_migrations(conn)
    assert 1 in applied and 2 in applied, f"Expected [1, 2] but got {applied}"
    
    # Verify both tables and indices exist
    cur = conn.cursor()
    
    # Check tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "positions" in tables
    assert "orders" in tables
    
    # Check indices
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = {row[0] for row in cur.fetchall()}
    assert "idx_positions_id" in indices
    assert "idx_orders_position_id" in indices
    assert "idx_orders_state" in indices
    
    conn.close()


def test_migration_chain_rollback_v2_only(tmp_path: Path):
    """Apply v1 and v2, then rollback only v2."""
    db = tmp_path / "chain2.db"
    conn = sqlite3.connect(str(db), timeout=30)
    
    apply_migrations(conn)
    
    # Rollback v2
    rollback_migration(conn, 2)
    
    # Verify v1 tables still exist, but indices are gone
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "positions" in tables
    assert "orders" in tables
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = {row[0] for row in cur.fetchall()}
    assert "idx_positions_id" not in indices
    
    # Verify v2 is no longer in schema_migrations
    cur.execute("SELECT version FROM schema_migrations")
    versions = {row[0] for row in cur.fetchall()}
    assert 1 in versions
    assert 2 not in versions
    
    conn.close()


def test_migration_chain_rollback_last_twice(tmp_path: Path):
    """Apply v1 and v2, rollback last twice to get back to nothing."""
    db = tmp_path / "chain3.db"
    conn = sqlite3.connect(str(db), timeout=30)
    
    apply_migrations(conn)
    
    # Rollback v2
    v = rollback_last(conn)
    assert v == 2
    
    # Rollback v1
    v = rollback_last(conn)
    assert v == 1
    
    # Verify no migrations remain
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations")
    versions = [row[0] for row in cur.fetchall()]
    assert len(versions) == 0
    
    conn.close()


def test_migration_idempotent_v1_v2(tmp_path: Path):
    """Apply migrations twice; second apply should be idempotent."""
    db = tmp_path / "chain4.db"
    conn = sqlite3.connect(str(db), timeout=30)
    
    applied1 = apply_migrations(conn)
    assert applied1 == [1, 2]
    
    # Second apply should do nothing
    applied2 = apply_migrations(conn)
    assert applied2 == []
    
    conn.close()
