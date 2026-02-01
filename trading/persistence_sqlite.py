import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from .position import PositionState


class SQLitePersistence:
    """SQLite-backed persistence supporting multiple positions and order history.

    Backwards-compatible APIs:
    - `save_position(pos)` and `load_position()` operate on a default position id 'position'.

    New APIs:
    - `save_position(pos, position_id)` / `load_position(position_id)`
    - `list_positions()`
    - `save_order(order_id, position_id, order_dict, state)`
    - `get_order(order_id)` / `list_orders(position_id)`

    All writes use transactions for atomicity.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=30, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        # Apply schema migrations
        from .db_migrations import apply_migrations

        apply_migrations(self.conn)

    # --- Position APIs ---
    def save_position(self, pos: PositionState, position_id: str = "position") -> None:
        data = json.dumps(pos.to_dict())
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("INSERT OR REPLACE INTO positions(position_id, value, updated_at) VALUES(?, ?, strftime('%s','now'))", (position_id, data))
        # also write legacy kv for backward compatibility
        cur.execute("INSERT OR REPLACE INTO kv(key, value, updated_at) VALUES(?, ?, strftime('%s','now'))", (position_id, data))
        self.conn.commit()

    def load_position(self, position_id: str = "position") -> Optional[PositionState]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM positions WHERE position_id = ?", (position_id,))
        row = cur.fetchone()
        if row:
            d = json.loads(row[0])
            return PositionState.from_dict(d)
        # fallback to legacy kv
        cur.execute("SELECT value FROM kv WHERE key = ?", (position_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = json.loads(row[0])
        return PositionState.from_dict(d)

    def list_positions(self) -> List[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT position_id FROM positions")
        return [r[0] for r in cur.fetchall()]

    # --- Order APIs ---
    def save_order(self, order_id: str, position_id: Optional[str], order_dict: Dict, state: Optional[str] = None) -> None:
        data = json.dumps(order_dict)
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            "INSERT OR REPLACE INTO orders(order_id, position_id, value, state, created_at, updated_at) VALUES(?, ?, ?, ?, COALESCE((SELECT created_at FROM orders WHERE order_id = ?), strftime('%s','now')), strftime('%s','now'))",
            (order_id, position_id, data, state, order_id),
        )
        self.conn.commit()

    def get_order(self, order_id: str) -> Optional[Dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT order_id, position_id, value, state FROM orders WHERE order_id = ?", (order_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"order_id": row[0], "position_id": row[1], **json.loads(row[2]), "state": row[3]}

    def list_orders(self, position_id: str) -> List[Dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT order_id, value, state FROM orders WHERE position_id = ?", (position_id,))
        out = []
        for row in cur.fetchall():
            data = json.loads(row[1])
            data.update({"order_id": row[0], "state": row[2]})
            out.append(data)
        return out

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
