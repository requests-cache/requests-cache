import sqlite3
import threading
from contextlib import contextmanager
from logging import getLogger
from os import makedirs, unlink
from os.path import abspath, basename, dirname, expanduser, isabs, isfile, join
from pathlib import Path
from tempfile import gettempdir
from typing import Collection, Iterable, Iterator, List, Tuple, Type, Union

from . import BaseCache, BaseStorage, get_valid_kwargs

SQLITE_MAX_VARIABLE_NUMBER = 999
logger = getLogger(__name__)


class DbCache(BaseCache):
    """SQLite cache backend.


    Args:
        db_path: Database file path (expands user paths and creates parent dirs)
        use_temp: Store database in a temp directory (e.g., ``/tmp/http_cache.sqlite``).
            Note: if ``db_path`` is an absolute path, this option will be ignored.
        fast_save: Speedup cache saving up to 50 times but with possibility of data loss.
            See :py:class:`.DbDict` for more info
        kwargs: Additional keyword arguments for :py:func:`sqlite3.connect`
    """

    def __init__(
        self,
        db_path: Union[Path, str] = 'http_cache',
        use_temp: bool = False,
        fast_save: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.responses = DbPickleDict(
            db_path, table_name='responses', use_temp=use_temp, fast_save=fast_save, **kwargs
        )
        self.redirects = DbDict(db_path, table_name='redirects', use_temp=use_temp, **kwargs)

    def bulk_delete(self, keys):
        """Remove multiple responses and their associated redirects from the cache, with additional cleanup"""
        self.responses.bulk_delete(keys=keys)
        self.responses.vacuum()
        self.redirects.bulk_delete(keys=keys)
        self.redirects.bulk_delete(values=keys)
        self.redirects.vacuum()

    def clear(self):
        """Clear the cache by deleting the cache file and re-initializing. This is done to allow
        clear() to succeed even if the file is corrupted.
        """
        if isfile(self.responses.db_path):
            unlink(self.responses.db_path)
        self.responses.init_db()
        self.redirects.init_db()


class DbDict(BaseStorage):
    """A dictionary-like interface for SQLite.

    It's possible to create multiply DbDict instances, which will be stored as separate
    tables in one database::

        d1 = DbDict('test', 'table1')
        d2 = DbDict('test', 'table2')
        d3 = DbDict('test', 'table3')

    All data will be stored in separate tables in the file ``test.sqlite``.

    Args:
        db_path: Database file path
        table_name: Table name
        fast_save: Use `'PRAGMA synchronous = 0;' <http://www.sqlite.org/pragma.html#pragma_synchronous>`_
            to speed up cache saving, but with the potential for data loss
        timeout: Timeout for acquiring a database lock
    """

    def __init__(
        self, db_path, table_name='http_cache', fast_save=False, use_temp: bool = False, **kwargs
    ):
        super().__init__(**kwargs)
        self.connection_kwargs = get_valid_kwargs(sqlite_template, kwargs)
        self.db_path = _get_db_path(db_path, use_temp)
        self.fast_save = fast_save
        self.table_name = table_name

        self._lock = threading.RLock()
        self._can_commit = True
        self._local_context = threading.local()
        self.init_db()

    def init_db(self):
        """Initialize the database, if it hasn't already been.
        This must be done in shared connection, but all subsequent queries can use thread-local connections.
        """
        self.close()
        with self._lock, sqlite3.connect(self.db_path, **self.connection_kwargs) as con:
            con.execute(f'CREATE TABLE IF NOT EXISTS {self.table_name} (key PRIMARY KEY, value)')

    @contextmanager
    def connection(self, commit=False) -> Iterator[sqlite3.Connection]:
        """Get a thread-local database connection"""
        if not getattr(self._local_context, 'con', None):
            logger.debug(f'Opening connection to {self.db_path}:{self.table_name}')
            self._local_context.con = sqlite3.connect(self.db_path, **self.connection_kwargs)
            if self.fast_save:
                self._local_context.con.execute('PRAGMA synchronous = 0;')
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

            >>> d1 = DbDict('test')
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
        return row[0]

    def __setitem__(self, key, value):
        with self.connection(commit=True) as con:
            con.execute(
                f'INSERT OR REPLACE INTO {self.table_name} (key,value) VALUES (?,?)',
                (key, value),
            )

    def __iter__(self):
        with self.connection() as con:
            for row in con.execute(f'SELECT key FROM {self.table_name}'):
                yield row[0]

    def __len__(self):
        with self.connection() as con:
            return con.execute(f'SELECT COUNT(key) FROM  {self.table_name}').fetchone()[0]

    def bulk_delete(self, keys=None, values=None):
        """Delete multiple keys from the cache, without raising errors for any missing keys.
        Also supports deleting by value.
        """
        if not keys and not values:
            return

        column = 'key' if keys else 'value'
        with self.connection(commit=True) as con:
            # Split into small enough chunks for SQLite to handle
            for chunk in chunkify(keys or values):
                marks, args = _format_sequence(chunk)
                statement = f'DELETE FROM {self.table_name} WHERE {column} IN ({marks})'
                con.execute(statement, args)

    def clear(self):
        with self.connection(commit=True) as con:
            con.execute(f'DROP TABLE IF EXISTS {self.table_name}')
        self.init_db()
        self.vacuum()

    def vacuum(self):
        with self.connection(commit=True) as con:
            con.execute('VACUUM')


class DbPickleDict(DbDict):
    """Same as :class:`DbDict`, but serializes values before saving"""

    def __setitem__(self, key, value):
        serialized_value = self.serializer.dumps(value)
        if isinstance(serialized_value, bytes):
            serialized_value = sqlite3.Binary(serialized_value)
        super().__setitem__(key, serialized_value)

    def __getitem__(self, key):
        return self.serializer.loads(super().__getitem__(key))


def chunkify(iterable: Iterable, max_size=SQLITE_MAX_VARIABLE_NUMBER) -> Iterator[List]:
    """Split an iterable into chunks of a max size"""
    iterable = list(iterable)
    for index in range(0, len(iterable), max_size):
        yield iterable[index : index + max_size]


def _format_sequence(values: Collection) -> Tuple[str, List]:
    """Get SQL parameter marks for a sequence-based query, and ensure value is a sequence"""
    if not isinstance(values, Iterable):
        values = [values]
    return ','.join(['?'] * len(values)), list(values)


def _get_db_path(db_path: Union[Path, str], use_temp: bool) -> str:
    """Get resolved path for database file"""
    # Save to a temp directory, if specified
    if use_temp and not isabs(db_path):
        db_path = join(gettempdir(), db_path)

    # Expand relative and user paths (~/*), and add file extension if not specified
    db_path = abspath(expanduser(str(db_path)))
    if '.' not in basename(db_path):
        db_path += '.sqlite'

    # Make sure parent dirs exist
    makedirs(dirname(db_path), exist_ok=True)
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
