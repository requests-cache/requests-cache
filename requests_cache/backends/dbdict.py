#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.dbdict
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Dictionary-like objects for saving large data sets to `sqlite` database
"""
import UserDict
import pickle
import sqlite3 as sqlite

class DbDict(object, UserDict.DictMixin):
    """ DbDict - a dictionary-like object for saving large datasets to `sqlite` database
    """

    def __init__(self, dict_name):
        """
        :param dict_name: filename for database
        """
        self.db_filename = "%s.sqlite" % dict_name
        self.con = sqlite.connect(self.db_filename)
        self.con.execute("create table if not exists data (key PRIMARY KEY, value)")

    def __getitem__(self, key):
        row = self.con.execute("select value from data where key=?", (key,)).fetchone()
        if not row:
            raise KeyError
        return row[0]

    def __setitem__(self, key, item):
        if self.con.execute("select key from data where key=?", (key,)).fetchone():
            self.con.execute("update data set value=? where key=?", (item, key))
        else:
            self.con.execute("insert into data (key,value) values (?,?)", (key, item))
        self.con.commit()

    def __delitem__(self, key):
        if self.con.execute("select key from data where key=?", (key,)).fetchone():
            self.con.execute("delete from data where key=?", (key,))
            self.con.commit()
        else:
            raise KeyError

    def keys(self):
        return [row[0] for row in
                self.con.execute("select key from data").fetchall()]

    def clear(self):
        self.con.execute("drop table data")
        self.con.execute("create table data (key PRIMARY KEY, value)")
        self.con.commit()

    def __str__(self):
        return str(dict(self.iteritems()))


class DbPickleDict(DbDict):
    """ Same as :class:`DbDict`, but pickles values before saving
    """
    def __setitem__(self, key, item):
        super(DbPickleDict, self).__setitem__(key, sqlite.Binary(pickle.dumps(item)))

    def __getitem__(self, key):
        return pickle.loads(super(DbPickleDict, self).__getitem__(key))
