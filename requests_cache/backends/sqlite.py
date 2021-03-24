import sqlite3
import threading
from contextlib import contextmanager
from os.path import expanduser

from .base import BaseCache, BaseStorage


class DbCache(BaseCache):
    """SQLite cache backend.

    Reading is fast, saving is a bit slower. It can store big amount of data with low memory usage.

    Args:
        location: database filename prefix
        extension: Database file extension
        fast_save: Speedup cache saving up to 50 times but with possibility of data loss.
            See :ref:`backends.DbDict <backends_dbdict>` for more info
    """

    def __init__(self, location='http_cache', extension='.sqlite', fast_save=False, **kwargs):
        super().__init__(**kwargs)
        db_path = expanduser(str(location) + extension)
        self.responses = DbPickleDict(db_path, table_name='responses', fast_save=fast_save, **kwargs)
        self.redirects = DbDict(db_path, table_name='redirects', **kwargs)


class DbDict(BaseStorage):
    """DbDict - a dictionary-like object for saving large datasets to `sqlite` database

    It's possible to create multiply DbDict instances, which will be stored as separate
    tables in one database::

        d1 = DbDict('test', 'table1')
        d2 = DbDict('test', 'table2')
        d3 = DbDict('test', 'table3')

    all data will be stored in ``test.sqlite`` database into
    correspondent tables: ``table1``, ``table2`` and ``table3``
    """

    def __init__(self, filename, table_name='http_cache', fast_save=False, **kwargs):
        """
        :param filename: filename for database (without extension)
        :param table_name: table name
        :param fast_save: If it's True, then sqlite will be configured with
                          `"PRAGMA synchronous = 0;" <http://www.sqlite.org/pragma.html#pragma_synchronous>`_
                          to speedup cache saving, but be careful, it's dangerous.
                          Tests showed that insertion order of records can be wrong with this option.
        """
        super().__init__(**kwargs)
        self.filename = filename
        self.table_name = table_name
        self.fast_save = fast_save

        #: Transactions can be committed if this property is set to `True`
        self.can_commit = True

        self._bulk_commit = False
        self._pending_connection = None
        self._lock = threading.RLock()
        with self.connection() as con:
            con.execute("create table if not exists `%s` (key PRIMARY KEY, value)" % self.table_name)

    @contextmanager
    def connection(self, commit_on_success=False):
        with self._lock:
            if self._bulk_commit:
                if self._pending_connection is None:
                    self._pending_connection = sqlite3.connect(self.filename)
                con = self._pending_connection
            else:
                con = sqlite3.connect(self.filename)
            try:
                if self.fast_save:
                    con.execute("PRAGMA synchronous = 0;")
                yield con
                if commit_on_success and self.can_commit:
                    con.commit()
            finally:
                if not self._bulk_commit:
                    con.close()

    def commit(self, force=False):
        """
        Commits pending transaction if :attr:`can_commit` or `force` is `True`

        :param force: force commit, ignore :attr:`can_commit`
        """
        if force or self.can_commit:
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
        self.can_commit = False
        try:
            yield
            self.commit(True)
        finally:
            self._bulk_commit = False
            self.can_commit = True
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

    def __str__(self):
        return str(dict(self.items()))


class DbPickleDict(DbDict):
    """Same as :class:`DbDict`, but pickles values before saving"""

    def __setitem__(self, key, item):
        super().__setitem__(key, sqlite3.Binary(self.serialize(item)))

    def __getitem__(self, key):
        return self.deserialize(super().__getitem__(key))
