from decimal import Decimal
from pathlib import Path

from trading.persistence_sqlite import SQLitePersistence
from trading.position import PositionState


def test_sqlite_save_and_load(tmp_path: Path):
    db = tmp_path / "state.db"
    persistence = SQLitePersistence(db)
    pos = PositionState(entry_price=Decimal('100'), qty_filled=Decimal('1'), highest_price_since_entry=Decimal('105'))
    persistence.save_position(pos)

    loaded = persistence.load_position()
    assert loaded is not None
    assert loaded.entry_price == pos.entry_price
    assert loaded.qty_filled == pos.qty_filled
    persistence.close()
