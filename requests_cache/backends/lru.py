from logging import getLogger
from time import time_ns
from typing import Iterator, Optional

from .sqlite import SQLiteDict

logger = getLogger(__name__)


class LRUDict(SQLiteDict):
    def __init__(self, *args, **kwargs):
        kwargs.pop('serializer', None)
        super().__init__(*args, **kwargs)

    def init_db(self):
        self.close()
        with self.connection(commit=True) as con:
            # Table for LRU metadata
            con.execute(
                f'CREATE TABLE IF NOT EXISTS {self.table_name} ('
                '    key TEXT PRIMARY KEY,'
                '    access_time INTEGER NOT NULL,'
                '    size INTEGER NOT NULL'
                ')'
            )
            con.execute(
                f'CREATE INDEX IF NOT EXISTS idx_access_time ON {self.table_name}(access_time)'
            )
            con.execute(f'CREATE INDEX IF NOT EXISTS idx_size ON {self.table_name}(size)')

            # Single-row table to persist total cache size
            con.execute(
                f'CREATE TABLE IF NOT EXISTS {self.table_name}_size ('
                '    total_size INTEGER NOT NULL'
                ')'
            )
            con.execute(f'INSERT OR IGNORE INTO {self.table_name}_size (total_size) VALUES (0)')

            # Triggers to update total size
            con.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {self.table_name}_insert
                AFTER INSERT ON {self.table_name}
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size + NEW.size;
                END;
                """
            )
            con.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {self.table_name}_delete
                AFTER DELETE ON {self.table_name}
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size - OLD.size;
                END;
                """
            )
            con.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {self.table_name}_update
                AFTER UPDATE OF size ON {self.table_name}
                WHEN OLD.size != NEW.size
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size + (NEW.size - OLD.size);
                END;
                """
            )

    def __delitem__(self, key):
        with self.connection(commit=True) as con:
            cur = con.execute(f'DELETE FROM {self.table_name} WHERE key=?', (key,))
        if not cur.rowcount:
            raise KeyError

    def __getitem__(self, key) -> int:
        with self.connection() as con:
            # Using placeholders here with python 3.12+ and concurrency results in the error:
            # sqlite3.InterfaceError: bad parameter or other API misuse
            row = con.execute(f"SELECT size FROM {self.table_name} WHERE key='{key}'").fetchone()
            if not row:
                raise KeyError(key)
            return row[0]

    def __setitem__(self, key: str, size: int):
        """Save a value (file size), and update access time and total cache size"""

        timestamp = int(time_ns())
        with self.connection(commit=True) as con:
            con.execute(
                f"""
                INSERT INTO {self.table_name} (key, access_time, size)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE
                SET access_time = excluded.access_time, size = excluded.size
                """,
                (key, timestamp, size),
            )

    def clear(self):
        super().clear()
        with self.connection(commit=True) as con:
            con.execute(f'UPDATE {self.table_name}_size SET total_size = 0')

    def count(self, *args, **kwargs):
        with self.connection() as con:
            return con.execute(f'SELECT COUNT(key) FROM {self.table_name}').fetchone()[0]

    def get_lru(self, total_size: int):
        """Get the least recently used keys with a combined size >= total_size"""

        with self.connection() as con:
            cur = con.execute(
                f"""
                WITH ordered AS (
                    SELECT key, size, access_time, SUM(size) OVER (ORDER BY access_time) AS running_total
                    FROM {self.table_name}
                )
                SELECT * FROM ordered WHERE running_total - size < ?
                ORDER BY access_time;
                """,
                (total_size,),
            )
            rows = cur.fetchall()
            cur.close()
            return [row[0] for row in rows]

    def sorted(  # type: ignore
        self,
        key: str = 'access_time',
        reversed: bool = False,
        limit: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """Get LRU entries in sorted order, by either ``access_time`` or ``size``"""
        # Get sort key, direction, and limit
        if key not in ['access_time', 'size', 'key']:
            raise ValueError(f'Invalid sort key: {key}')
        direction = 'DESC' if reversed else 'ASC'
        limit_expr = f'LIMIT {limit}' if limit else ''

        with self.connection() as con:
            for row in con.execute(
                f'SELECT key FROM {self.table_name} ORDER BY {key} {direction} {limit_expr}',
            ):
                yield row[0]

    def total_size(self) -> int:
        with self.connection() as con:
            row = con.execute(f'SELECT total_size FROM {self.table_name}_size').fetchone()
            return row[0] if row else 0

    def update_access_time(self, key: str):
        """Update the given key with the current timestamp

        Raises:
            KeyError: If the key doesn't exist in the LRU index
        """
        timestamp = int(time_ns())
        with self.connection(commit=True) as con:
            cur = con.execute(
                f'UPDATE {self.table_name} SET access_time = ? WHERE key = ?',
                (timestamp, key),
            )
            # updated = cur.rowcount
        if not cur.rowcount:
            raise KeyError(key)
