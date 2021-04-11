import sqlite3
import threading
from contextlib import contextmanager
from logging import getLogger
from os import makedirs
from os.path import abspath, basename, dirname, expanduser
from pathlib import Path
from typing import Union

from .base import BaseCache, BaseStorage

logger = getLogger(__name__)


class DbCache(BaseCache):
    """SQLite cache backend.

    Reading is fast, saving is a bit slower. It can store big amount of data with low memory usage.

    Args:
        db_path: Database file path (expands user paths and creates parent dirs)
        fast_save: Speedup cache saving up to 50 times but with possibility of data loss.
            See :py:class:`.DbDict` for more info
        timeout: Timeout for acquiring a database lock
    """

    def __init__(self, db_path: Union[Path, str] = 'http_cache', fast_save: bool = False, **kwargs):
        super().__init__(**kwargs)
        kwargs.setdefault('suppress_warnings', True)
        db_path = _get_db_path(db_path)
        self.responses = DbPickleDict(db_path, table_name='responses', fast_save=fast_save, **kwargs)
        self.redirects = DbDict(db_path, table_name='redirects', **kwargs)

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

    def __init__(self, db_path, table_name='http_cache', fast_save=False, timeout=5.0, **kwargs):
        super().__init__(**kwargs)
        self.db_path = db_path
        self.fast_save = fast_save
        self.table_name = table_name
        self.timeout = timeout

        self._bulk_commit = False
        self._can_commit = True
        self._pending_connection = None
        self._lock = threading.RLock()
        with self.connection() as con:
            con.execute("create table if not exists `%s` (key PRIMARY KEY, value)" % self.table_name)

    @contextmanager
    def connection(self, commit_on_success=False):
        logger.debug(f'Opening connection to {self.db_path}:{self.table_name}')
        with self._lock:
            if self._bulk_commit:
                if self._pending_connection is None:
                    self._pending_connection = sqlite3.connect(self.db_path, timeout=self.timeout)
                con = self._pending_connection
            else:
                con = sqlite3.connect(self.db_path, timeout=self.timeout)
            try:
                if self.fast_save:
                    con.execute("PRAGMA synchronous = 0;")
                yield con
                if commit_on_success and self._can_commit:
                    con.commit()
            finally:
                if not self._bulk_commit:
                    con.close()

    def commit(self, force=False):
        """
        Commits pending transaction if :attr:`can_commit` or `force` is `True`

        :param force: force commit, ignore :attr:`can_commit`
        """
        if force or self._can_commit:
            if self._pending_connection is not None:
                self._pending_connection.commit()

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
        self._bulk_commit = True
        self._can_commit = False
        try:
            yield
            self.commit(True)
        finally:
            self._bulk_commit = False
            self._can_commit = True
            if self._pending_connection is not None:
                self._pending_connection.close()
                self._pending_connection = None

    def __getitem__(self, key):
        with self.connection() as con:
            row = con.execute("select value from `%s` where key=?" % self.table_name, (key,)).fetchone()
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
            con.execute("drop table `%s`" % self.table_name)
            con.execute("create table `%s` (key PRIMARY KEY, value)" % self.table_name)
            con.execute("vacuum")

    def vacuum(self):
        with self.connection(True) as con:
            con.execute("vacuum")

    def __str__(self):
        return str(dict(self.items()))


class DbPickleDict(DbDict):
    """Same as :class:`DbDict`, but pickles values before saving"""

    def __setitem__(self, key, item):
        super().__setitem__(key, sqlite3.Binary(self.serialize(item)))

    def __getitem__(self, key):
        return self.deserialize(super().__getitem__(key))


def _get_db_path(db_path):
    """Get resolved path for database file"""
    # Allow paths with user directories (~/*), and add file extension if not specified
    db_path = abspath(expanduser(str(db_path)))
    if '.' not in basename(db_path):
        db_path += '.sqlite'
    # Make sure parent dirs exist
    makedirs(dirname(db_path), exist_ok=True)
    return db_path
