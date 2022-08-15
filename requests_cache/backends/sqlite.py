"""SQLite cache backend. For usage details, see :ref:`Backends: SQLite <sqlite>`.

.. automodsumm:: requests_cache.backends.sqlite
   :classes-only:
   :nosignatures:
"""
import sqlite3
import threading
from contextlib import contextmanager
from logging import getLogger
from os import unlink
from os.path import getsize, isfile
from pathlib import Path
from tempfile import gettempdir
from time import time
from typing import Collection, Iterator, List, Tuple, Type, Union

from platformdirs import user_cache_dir

from requests_cache.models.response import CachedResponse

from .._utils import chunkify, get_valid_kwargs
from . import BaseCache, BaseStorage

MEMORY_URI = 'file::memory:?cache=shared'
SQLITE_MAX_VARIABLE_NUMBER = 999
AnyPath = Union[Path, str]
logger = getLogger(__name__)


class SQLiteCache(BaseCache):
    """SQLite cache backend.

    Args:
        db_path: Database file path
        use_cache_dir: Store datebase in a user cache directory (e.g., `~/.cache/http_cache.sqlite`)
        use_temp: Store database in a temp directory (e.g., ``/tmp/http_cache.sqlite``)
        use_memory: Store database in memory instead of in a file
        fast_save: Significantly increases cache write performance, but with the possibility of data
            loss. See `pragma: synchronous <https://www.sqlite.org/pragma.html#pragma_synchronous>`_
            for details.
        wal: Use `Write Ahead Logging <https://sqlite.org/wal.html>`_, so readers do not block writers.
        kwargs: Additional keyword arguments for :py:func:`sqlite3.connect`
    """

    def __init__(self, db_path: AnyPath = 'http_cache', **kwargs):
        super().__init__(cache_name=str(db_path), **kwargs)
        self.responses: SQLiteDict = SQLiteDict(db_path, table_name='responses', **kwargs)
        self.redirects: SQLiteDict = SQLiteDict(
            db_path, table_name='redirects', no_serializer=True, **kwargs
        )

    @property
    def db_path(self) -> AnyPath:
        return self.responses.db_path

    def clear(self):
        """Clear the cache. If this fails due to a corrupted cache or other I/O error, this will
        attempt to delete the cache file and re-initialize.
        """
        try:
            super().clear()
        except Exception:
            logger.exception('Failed to clear cache')
            if isfile(self.responses.db_path):
                unlink(self.responses.db_path)
            self.responses.init_db()
            self.redirects.init_db()

    def delete(
        self,
        *keys: str,
        expired: bool = False,
        **kwargs,
    ):
        """A more efficient SQLite implementation of :py:meth:`BaseCache.delete`"""
        if keys:
            self.responses.bulk_delete(keys)
        if expired:
            self._delete_expired()

        # For any remaining conditions, use base implementation
        if kwargs:
            with self.responses._lock, self.redirects._lock:
                return super().delete(**kwargs)
        else:
            self._prune_redirects()

        self.responses.vacuum()
        self.redirects.vacuum()

    def _delete_expired(self):
        """A more efficient implementation deleting expired responses in SQL"""
        with self.responses._lock, self.responses.connection(commit=True) as con:
            con.execute(
                f'DELETE FROM {self.responses.table_name} WHERE expires <= ?', (round(time()),)
            )

    def _prune_redirects(self):
        """A more efficient implementation of removing invalid redirects in SQL"""
        with self.redirects.connection(commit=True) as conn:
            t1 = self.redirects.table_name
            t2 = self.responses.table_name
            conn.execute(
                f'DELETE FROM {t1} WHERE key IN ('
                f'    SELECT {t1}.key FROM {t1}'
                f'    LEFT JOIN {t2} ON {t2}.key = {t1}.value'
                f'    WHERE {t2}.key IS NULL'
                ')'
            )

    def filter(  # type: ignore
        self, valid: bool = True, expired: bool = True, **kwargs
    ) -> Iterator[CachedResponse]:
        """A more efficient implementation of :py:meth:`BaseCache.filter`, in the case where we want
        to get **only** expired responses
        """
        if expired and not valid and not kwargs:
            return self.responses.sorted(expired=True)
        else:
            return super().filter(valid, expired, **kwargs)

    def recreate_keys(self):
        """A more efficient implementation of :py:meth:`BaseCache.recreate_keys`"""
        with self.responses.bulk_commit():
            super().recreate_keys()

    def sorted(
        self,
        key: str = 'expires',
        reversed: bool = False,
        limit: int = None,
        expired: bool = True,
    ):
        """Get cached responses, with sorting and other query options.

        Args:
            key: Key to sort by; either 'expires', 'size', or 'key'
            reversed: Sort in descending order
            limit: Maximum number of responses to return
            expired: Set to ``False`` to exclude expired responses
        """
        return self.responses.sorted(key, reversed, limit, expired)


class SQLiteDict(BaseStorage):
    """A dictionary-like interface for SQLite"""

    def __init__(
        self,
        db_path,
        table_name='http_cache',
        fast_save=False,
        use_cache_dir: bool = False,
        use_memory: bool = False,
        use_temp: bool = False,
        wal: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._can_commit = True
        self._local_context = threading.local()
        self._lock = threading.RLock()
        self.connection_kwargs = get_valid_kwargs(sqlite_template, kwargs)
        self.db_path = _get_sqlite_cache_path(db_path, use_cache_dir, use_temp, use_memory)
        self.fast_save = fast_save
        self.table_name = table_name
        self.wal = wal
        self.init_db()

    def init_db(self):
        """Initialize the database, if it hasn't already been"""
        self.close()
        with self._lock, self.connection() as con:
            # Add new column to tables created before 0.10
            try:
                con.execute(f'ALTER TABLE {self.table_name} ADD COLUMN expires TEXT')
            except sqlite3.OperationalError:
                pass

            con.execute(
                f'CREATE TABLE IF NOT EXISTS {self.table_name} ('
                '    key TEXT PRIMARY KEY,'
                '    value BLOB, '
                '    expires INTEGER'
                ')'
            )
            con.execute(f'CREATE INDEX IF NOT EXISTS expires_idx ON {self.table_name}(expires)')

    @contextmanager
    def connection(self, commit=False) -> Iterator[sqlite3.Connection]:
        """Get a thread-local database connection"""
        if not getattr(self._local_context, 'con', None):
            logger.debug(f'Opening connection to {self.db_path}:{self.table_name}')
            self._local_context.con = sqlite3.connect(self.db_path, **self.connection_kwargs)
            if self.fast_save:
                self._local_context.con.execute('PRAGMA synchronous = 0;')
            if self.wal:
                self._local_context.con.execute('PRAGMA journal_mode = wal')
        yield self._local_context.con
        if commit and self._can_commit:
            self._local_context.con.commit()

    def close(self):
        """Close any active connections"""
        if getattr(self._local_context, 'con', None):
            self._local_context.con.close()
            self._local_context.con = None

    @contextmanager
    def bulk_commit(self):
        """Context manager used to speed up insertion of a large number of records

        Example:

            >>> d1 = SQLiteDict('test')
            >>> with d1.bulk_commit():
            ...     for i in range(1000):
            ...         d1[i] = i * 2

        """
        self._can_commit = False
        try:
            yield
            if hasattr(self._local_context, 'con'):
                self._local_context.con.commit()
        finally:
            self._can_commit = True

    def __del__(self):
        self.close()

    def __delitem__(self, key):
        with self.connection(commit=True) as con:
            cur = con.execute(f'DELETE FROM {self.table_name} WHERE key=?', (key,))
        if not cur.rowcount:
            raise KeyError

    def __getitem__(self, key):
        with self.connection() as con:
            row = con.execute(f'SELECT value FROM {self.table_name} WHERE key=?', (key,)).fetchone()
        # raise error after the with block, otherwise the connection will be locked
        if not row:
            raise KeyError

        return self.deserialize(row[0])

    def __setitem__(self, key, value):
        # If available, set expiration as a timestamp in unix format
        expires = value.expires_unix if getattr(value, 'expires_unix', None) else None
        value = self.serialize(value)
        if isinstance(value, bytes):
            value = sqlite3.Binary(value)
        with self.connection(commit=True) as con:
            con.execute(
                f'INSERT OR REPLACE INTO {self.table_name} (key,value,expires) VALUES (?,?,?)',
                (key, value, expires),
            )

    def __iter__(self):
        with self.connection() as con:
            for row in con.execute(f'SELECT key FROM {self.table_name}'):
                yield row[0]

    def __len__(self):
        with self.connection() as con:
            return con.execute(f'SELECT COUNT(key) FROM {self.table_name}').fetchone()[0]

    def bulk_delete(self, keys=None, values=None):
        """Delete multiple items from the cache, without raising errors for any missing items.
        Supports deleting by either key or by value.
        """
        if not keys and not values:
            return

        column = 'key' if keys else 'value'
        with self.connection(commit=True) as con:
            # Split into small enough chunks for SQLite to handle
            for chunk in chunkify(keys or values, max_size=SQLITE_MAX_VARIABLE_NUMBER):
                marks, args = _format_sequence(chunk)
                statement = f'DELETE FROM {self.table_name} WHERE {column} IN ({marks})'
                con.execute(statement, args)

    def clear(self):
        with self._lock:
            with self.connection(commit=True) as con:
                con.execute(f'DROP TABLE IF EXISTS {self.table_name}')
            self.init_db()
            self.vacuum()

    def size(self) -> int:
        """Return the size of the database, in bytes. For an in-memory database, this will be an
        estimate based on page size.
        """
        try:
            return getsize(self.db_path)
        except IOError:
            return self._estimate_size()

    def _estimate_size(self) -> int:
        """Estimate the current size of the database based on page count * size"""
        with self.connection() as conn:
            page_count = conn.execute('PRAGMA page_count').fetchone()[0]
            page_size = conn.execute('PRAGMA page_size').fetchone()[0]
            return page_count * page_size

    def sorted(
        self, key: str = 'expires', reversed: bool = False, limit: int = None, expired: bool = True
    ):
        """Get cache values in sorted order; see :py:meth:`.SQLiteCache.sorted` for usage details"""
        # Get sort key, direction, and limit
        if key not in ['expires', 'size', 'key']:
            raise ValueError(f'Invalid sort key: {key}')
        if key == 'size':
            key = 'LENGTH(value)'
        direction = 'DESC' if reversed else 'ASC'
        limit_expr = f'LIMIT {limit}' if limit else ''

        # Filter out expired items, if specified
        filter_expr = ''
        params: Tuple = ()
        if not expired:
            filter_expr = 'WHERE expires is null or expires > ?'
            params = (time(),)

        with self.connection(commit=True) as con:
            for row in con.execute(
                f'SELECT value FROM {self.table_name} {filter_expr}'
                f'  ORDER BY {key} {direction} {limit_expr}',
                params,
            ):
                yield self.deserialize(row[0])

    def vacuum(self):
        with self.connection(commit=True) as con:
            con.execute('VACUUM')


def _format_sequence(values: Collection) -> Tuple[str, List]:
    """Get SQL parameter marks for a sequence-based query"""
    return ','.join(['?'] * len(values)), list(values)


def _get_sqlite_cache_path(
    db_path: AnyPath, use_cache_dir: bool, use_temp: bool, use_memory: bool = False
) -> AnyPath:
    """Get a resolved path for a SQLite database file (or memory URI)"""
    # Use an in-memory database, if specified
    db_path = str(db_path)
    if use_memory:
        return MEMORY_URI
    elif ':memory:' in db_path or 'mode=memory' in db_path:
        return db_path

    # Add file extension if not specified
    if not Path(db_path).suffix:
        db_path += '.sqlite'
    return get_cache_path(db_path, use_cache_dir, use_temp)


def get_cache_path(db_path: AnyPath, use_cache_dir: bool = False, use_temp: bool = False) -> Path:
    """Get a resolved cache path"""
    db_path = Path(db_path)

    # Save to platform-specific temp or user cache directory, if specified
    if use_cache_dir and not db_path.is_absolute():
        db_path = Path(user_cache_dir()) / db_path
    elif use_temp and not db_path.is_absolute():
        db_path = Path(gettempdir()) / db_path

    # Expand relative and user paths (~), make parent dir(s), and better error if parent is a file
    db_path = db_path.expanduser().absolute()
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        raise FileExistsError(
            f'Parent path exists and is not a directory: {db_path.parent}.'
            'Please either delete the file or choose a different path.'
        )
    return db_path


def sqlite_template(
    timeout: float = 5.0,
    detect_types: int = 0,
    isolation_level: str = None,
    check_same_thread: bool = True,
    factory: Type = None,
    cached_statements: int = 100,
    uri: bool = False,
):
    """Template function to get an accurate signature for the builtin :py:func:`sqlite3.connect`"""
