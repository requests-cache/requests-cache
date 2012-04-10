#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.dbdict
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Dictionary-like objects for saving large data sets to `sqlite` database
"""
from collections import MutableMapping
import sqlite3 as sqlite
from contextlib import contextmanager
try:
    import cPickle as pickle
except ImportError:
    import pickle

from requests_cache.compat import bytes


class DbDict(MutableMapping):
    """ DbDict - a dictionary-like object for saving large datasets to `sqlite` database

    It's possible to create multiply DbDict instances, which will be stored as separate
    tables in one database through the `reusable_dbdict` parameter::

        d1 = DbDict('test', 'table1')
        d2 = DbDict('test', 'table2', d1)
        d3 = DbDict('test', 'table3', d1)

    all data will be stored in ``test.sqlite`` database into
    correspondent tables: ``table1``, ``table2`` and ``table3``
    """

    def __init__(self, filename, table_name='data', reusable_dbdict=None):
        """
        :param filename: filename for database (without extension)
        :param table_name: table name
        :param reusable_dbdict: :class:`DbDict` instance which connection will be reused
        """
        self.filename = "%s.sqlite" % filename
        self.table_name = table_name
        self._can_commit = True
        if reusable_dbdict is not None:
            if self.table_name == reusable_dbdict.table_name:
                raise ValueError("table_name can't be the same as reusable_dbdict.table_name")
            self.con = reusable_dbdict.con
        else:
            self.con = sqlite.connect(self.filename)
        self.con.execute("create table if not exists %s (key PRIMARY KEY, value)" % self.table_name)

    def commit(self, force=False):
        """
        Commits pending transaction if :attr:`can_commit` or `force` is `True`

        :param force: force commit, ignore :attr:`can_commit`
        """
        if force or self._can_commit:
            self.con.commit()

    @property
    def can_commit(self):
        """ Transactions can be commited if this property set to `True`
        """
        return self._can_commit

    @can_commit.setter
    def can_commit(self, value):
        self._can_commit = value

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
            self.commit(True)
        finally:
            self._can_commit = True


    def __getitem__(self, key):
        row = self.con.execute("select value from %s where key=?" % self.table_name, (key,)).fetchone()
        if not row:
            raise KeyError
        return row[0]

    def __setitem__(self, key, item):
        if self.con.execute("select key from %s where key=?" % self.table_name, (key,)).fetchone():
            self.con.execute("update %s set value=? where key=?" % self.table_name, (item, key))
        else:
            self.con.execute("insert into %s (key,value) values (?,?)" % self.table_name, (key, item))
        self.commit()

    def __delitem__(self, key):
        if self.con.execute("select key from %s where key=?"  % self.table_name, (key,)).fetchone():
            self.con.execute("delete from %s where key=?" % self.table_name, (key,))
            self.commit()
        else:
            raise KeyError

    def __iter__(self):
        for row in self.con.execute("select key from %s" % self.table_name).fetchall():
            yield row[0]

    def __len__(self):
        return self.con.execute("select count(key) from %s" %
                                self.table_name).fetchone()[0]

    def clear(self):
        self.con.execute("drop table %s" % self.table_name)
        self.con.execute("create table %s (key PRIMARY KEY, value)"  % self.table_name)
        self.commit()

    def __str__(self):
        return str(dict(self.items()))


class DbPickleDict(DbDict):
    """ Same as :class:`DbDict`, but pickles values before saving
    """
    def __setitem__(self, key, item):
        super(DbPickleDict, self).__setitem__(key,
                                              sqlite.Binary(pickle.dumps(item)))

    def __getitem__(self, key):
        return pickle.loads(bytes(super(DbPickleDict, self).__getitem__(key)))
