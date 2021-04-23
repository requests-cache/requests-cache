import sqlite3
import threading
from contextlib import contextmanager
from logging import getLogger
from os import makedirs
from os.path import abspath, basename, dirname, expanduser, isabs, join
from pathlib import Path
from tempfile import gettempdir
from typing import Type, Union

from . import BaseCache, BaseStorage, get_valid_kwargs

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
        self, db_path: Union[Path, str] = 'http_cache', use_temp: bool = False, fast_save: bool = False, **kwargs
    ):
        super().__init__(**kwargs)
        self.responses = DbPickleDict(db_path, table_name='responses', use_temp=use_temp, fast_save=fast_save, **kwargs)
        self.redirects = DbDict(db_path, table_name='redirects', use_temp=use_temp, **kwargs)

    def remove_expired_responses(self, *args, **kwargs):
        """Remove expired responses from the cache, with additional cleanup"""
        super().remove_expired_responses(*args, **kwargs)
        self.responses.vacuum()
        self.redirects.vacuum()


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
        fast_save: Use `"PRAGMA synchronous = 0;" <http://www.sqlite.org/pragma.html#pragma_synchronous>`_
            to speed up cache saving, but with the potential for data loss
        timeout: Timeout for acquiring a database lock
    """

    def __init__(self, db_path, table_name='http_cache', fast_save=False, use_temp: bool = False, **kwargs):
        kwargs.setdefault('suppress_warnings', True)
        super().__init__(**kwargs)
        self.connection_kwargs = get_valid_kwargs(sqlite_template, kwargs)
        self.db_path = _get_db_path(db_path, use_temp)
        self.fast_save = fast_save
        self.table_name = table_name

        self._can_commit = True
        self._local_context = threading.local()
        with sqlite3.connect(self.db_path, **self.connection_kwargs) as con:
            con.execute("create table if not exists `%s` (key PRIMARY KEY, value)" % self.table_name)

    @contextmanager
    def connection(self, commit_on_success=False):
        if not hasattr(self._local_context, "con"):
            logger.debug(f'Opening connection to {self.db_path}:{self.table_name}')
            self._local_context.con = sqlite3.connect(self.db_path, **self.connection_kwargs)
            if self.fast_save:
                self._local_context.con.execute("PRAGMA synchronous = 0;")
        yield self._local_context.con
        if commit_on_success and self._can_commit:
            self._local_context.con.commit()

    def __del__(self):
        if hasattr(self._local_context, "con"):
            self._local_context.con.close()

    @contextmanager
    def bulk_commit(self):
        """
        Context manager used to speedup insertion of big number of records
        ::

            >>> d1 = DbDict('test')
            >>> with d1.bulk_commit():
            ...     for i in range(1000):
            ...         d1[i] = i * 2

        """
        self._can_commit = False
        try:
            yield
            if hasattr(self._local_context, "con"):
                self._local_context.con.commit()
        finally:
            self._can_commit = True

    def __getitem__(self, key):
        with self.connection() as con:
            row = con.execute("select value from `%s` where key=?" % self.table_name, (key,)).fetchone()
        # raise error after the with block, otherwise the connection will be locked
        if not row:
            raise KeyError
        return row[0]

    def __setitem__(self, key, item):
        with self.connection(True) as con:
            con.execute(
                "insert or replace into `%s` (key,value) values (?,?)" % self.table_name,
                (key, item),
            )

    def __delitem__(self, key):
        with self.connection(True) as con:
            cur = con.execute("delete from `%s` where key=?" % self.table_name, (key,))
        if not cur.rowcount:
            raise KeyError

    def __iter__(self):
        with self.connection() as con:
            for row in con.execute("select key from `%s`" % self.table_name):
                yield row[0]

    def __len__(self):
        with self.connection() as con:
            return con.execute("select count(key) from `%s`" % self.table_name).fetchone()[0]

    def clear(self):
        with self.connection(True) as con:
            con.execute("drop table if exists `%s`" % self.table_name)
            con.execute("create table `%s` (key PRIMARY KEY, value)" % self.table_name)
            con.execute("vacuum")

    def vacuum(self):
        with self.connection(True) as con:
            con.execute("vacuum")


class DbPickleDict(DbDict):
    """Same as :class:`DbDict`, but pickles values before saving"""

    def __setitem__(self, key, item):
        super().__setitem__(key, sqlite3.Binary(self.serialize(item)))

    def __getitem__(self, key):
        return self.deserialize(super().__getitem__(key))


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
