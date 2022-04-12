"""
.. image::
    ../_static/sqlite.png

`SQLite <https://www.sqlite.org/>`_ is a fast and lightweight SQL database engine that stores data
either in memory or in a single file on disk.

Use Cases
^^^^^^^^^
Despite its simplicity, SQLite is a powerful tool. For example, it's the primary storage system for
a number of common applications including Dropbox, Firefox, and Chrome. It's well suited for
caching, and requires no extra configuration or dependencies, which is why it's the default backend
for requests-cache.

Cache Files
^^^^^^^^^^^
* See :ref:`files` for general info on specifying cache paths
* If you specify a name without an extension, the default extension ``.sqlite`` will be used

In-Memory Caching
~~~~~~~~~~~~~~~~~
SQLite also supports `in-memory databases <https://www.sqlite.org/inmemorydb.html>`_.
You can enable this (in "shared" memory mode) with the ``use_memory`` option:

    >>> session = CachedSession('http_cache', use_memory=True)

Or specify a memory URI with additional options:

    >>> session = CachedSession(':file:memdb1?mode=memory')

Or just ``:memory:``, if you are only using the cache from a single thread:

    >>> session = CachedSession(':memory:')

Performance
^^^^^^^^^^^
When working with average-sized HTTP responses (< 1MB) and using a modern SSD for file storage, you
can expect speeds of around:

* Write: 2-8ms
* Read: 0.2-0.6ms

Of course, this will vary based on hardware specs, response size, and other factors.

Concurrency
^^^^^^^^^^^
SQLite supports concurrent access, so it is safe to use from a multi-threaded and/or multi-process
application. It supports unlimited concurrent reads. Writes, however, are queued and run in serial,
so if you need to make large volumes of concurrent requests, you may want to consider a different
backend that's specifically made for that kind of workload, like :py:class:`.RedisCache`.

Hosting Services and Filesystem Compatibility
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
There are some caveats to using SQLite with some hosting services, based on what kind of storage is
available:

* NFS:
    * SQLite may be used on a NFS, but is usually only safe to use from a single process at a time.
      See the `SQLite FAQ <https://www.sqlite.org/faq.html#q5>`_ for details.
    * PythonAnywhere is one example of a host that uses NFS-backed storage. Using SQLite from a
      multiprocess application will likely result in ``sqlite3.OperationalError: database is locked``.
* Ephemeral storage:
    * Heroku `explicitly disables SQLite <https://devcenter.heroku.com/articles/sqlite3>`_ on its dynos.
    * AWS `EC2 <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html>`_,
      `Lambda (depending on configuration) <https://aws.amazon.com/blogs/compute/choosing-between-aws-lambda-data-storage-options-in-web-apps/>`_,
      and some other AWS services use ephemeral storage that only persists for the lifetime of the
      instance. This is fine for short-term caching. For longer-term persistance, you can use an
      `attached EBS volume <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-attaching-volume.html>`_.

Connection Options
^^^^^^^^^^^^^^^^^^
The SQLite backend accepts any keyword arguments for :py:func:`sqlite3.connect`. These can be passed
via :py:class:`.CachedSession`:

    >>> session = CachedSession('http_cache', timeout=30)

Or via :py:class:`.SQLiteCache`:

    >>> backend = SQLiteCache('http_cache', timeout=30)
    >>> session = CachedSession(backend=backend)

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.sqlite
   :classes-only:
   :nosignatures:
"""
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from logging import getLogger
from os import unlink
from os.path import isfile
from pathlib import Path
from tempfile import gettempdir
from typing import Collection, Iterable, Iterator, List, Tuple, Type, Union

from platformdirs import user_cache_dir

from .._utils import chunkify, get_valid_kwargs
from ..expiration import ExpirationTime
from ..models import CachedResponse
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
            loss. See `pragma: synchronous <http://www.sqlite.org/pragma.html#pragma_synchronous>`_
            for details.
        wal: Use `Write Ahead Logging <https://sqlite.org/wal.html>`_, so readers do not block writers.
        kwargs: Additional keyword arguments for :py:func:`sqlite3.connect`
    """

    def __init__(self, db_path: AnyPath = 'http_cache', **kwargs):
        super().__init__(**kwargs)
        self.responses: SQLiteDict = SQLitePickleDict(db_path, table_name='responses', **kwargs)
        self.redirects: SQLiteDict = SQLiteDict(db_path, table_name='redirects', **kwargs)

    @property
    def db_path(self) -> AnyPath:
        return self.responses.db_path

    def bulk_delete(self, keys):
        """Remove multiple responses and their associated redirects from the cache, with additional cleanup"""
        self.responses.bulk_delete(keys=keys)
        self.responses.vacuum()

        self.redirects.bulk_delete(keys=keys)
        self.redirects.bulk_delete(values=keys)
        self.redirects.vacuum()

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

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        if expire_after is not None:
            with self.responses._lock, self.redirects._lock:
                return super().remove_expired_responses(expire_after=expire_after)
        else:
            self.responses.clear_expired()
            self.remove_invalid_redirects()

    def remove_invalid_redirects(self):
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

    def sorted(
        self,
        key: str = 'expires',
        reversed: bool = False,
        limit: int = None,
        exclude_expired=False,
    ):
        """Get cached responses, with sorting and other query options.

        Args:
            key: Key to sort by; either 'expires', 'size', or 'key'
            reversed: Sort in descending order
            limit: Maximum number of responses to return
            exclude_expired: Only return unexpired responses
        """
        return self.responses.sorted(key, reversed, limit, exclude_expired)


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
        return row[0]

    def __setitem__(self, key, value):
        self._insert(key, value)

    def _insert(self, key, value, expires: datetime = None):
        posix_expires = round(expires.timestamp()) if expires else None
        with self.connection(commit=True) as con:
            con.execute(
                f'INSERT OR REPLACE INTO {self.table_name} (key,value,expires) VALUES (?,?,?)',
                (key, value, posix_expires),
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

    def clear_expired(self):
        """Remove expired items from the cache"""
        posix_now = round(datetime.utcnow().timestamp())
        with self._lock, self.connection(commit=True) as con:
            con.execute(f"DELETE FROM {self.table_name} WHERE expires <= ?", (posix_now,))
        self.vacuum()

    def sorted(
        self, key: str = 'expires', reversed: bool = False, limit: int = None, exclude_expired=False
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
        if exclude_expired:
            posix_now = round(datetime.utcnow().timestamp())
            filter_expr = 'WHERE expires is null or expires > ?'
            params = (posix_now,)

        with self.connection(commit=True) as con:
            for row in con.execute(
                f'SELECT value FROM {self.table_name} {filter_expr}'
                f'  ORDER BY {key} {direction} {limit_expr}',
                params,
            ):
                yield row[0]

    def vacuum(self):
        with self.connection(commit=True) as con:
            con.execute('VACUUM')


class SQLitePickleDict(SQLiteDict):
    """Same as :class:`SQLiteDict`, but serializes values before saving"""

    def __setitem__(self, key, value: CachedResponse):
        serialized_value = self.serializer.dumps(value)
        if isinstance(serialized_value, bytes):
            serialized_value = sqlite3.Binary(serialized_value)
        super()._insert(key, serialized_value, getattr(value, 'expires', None))

    def __getitem__(self, key):
        return self.serializer.loads(super().__getitem__(key))

    def sorted(
        self,
        key: str = 'expires',
        reversed: bool = False,
        limit: int = None,
        exclude_expired: bool = False,
    ):
        for value in super().sorted(key, reversed, limit, exclude_expired):
            yield self.serializer.loads(value)


def _format_sequence(values: Collection) -> Tuple[str, List]:
    """Get SQL parameter marks for a sequence-based query, and ensure value is a sequence"""
    if not isinstance(values, Iterable):
        values = [values]
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


# Aliases for backwards-compatibility
DbCache = SQLiteCache
DbDict = SQLiteDict
DbPickeDict = SQLitePickleDict
