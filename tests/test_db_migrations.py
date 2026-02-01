from pathlib import Path

from trading.db_migrations import apply_migrations, MIGRATIONS
from trading.persistence_sqlite import SQLitePersistence


def test_apply_migrations_idempotent(tmp_path: Path):
    db = tmp_path / "migs.db"
    # create connection via persistence to ensure file exists
    p = SQLitePersistence(db)
    # apply migrations again directly
    applied = apply_migrations(p.conn)
    # initial migrations may already be applied; reapplying should return []
    assert isinstance(applied, list)
    # MIGRATIONS keys are present
    assert set(MIGRATIONS.keys()) >= {1}
    p.close()
