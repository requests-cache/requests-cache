#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

from threading import Thread
import unittest
from requests_cache.backends.dbdict import DbDict, DbPickleDict

DB_NAME = 'test'


class DbdictTestCase(unittest.TestCase):
    def test_reusable_dicts(self):
        d1 = DbDict(DB_NAME, 'table1')
        d2 = DbDict(DB_NAME, 'table2', d1)
        d3 = DbDict(DB_NAME, 'table3', d1)
        d1[1] = 1
        d2[2] = 2
        d3[3] = 3
        self.assertEqual(list(d1.keys()), [1])
        self.assertEqual(list(d2.keys()), [2])
        self.assertEqual(list(d3.keys()), [3])

        with self.assertRaises(ValueError):
            d4 = DbDict(DB_NAME, 'table1', d1)

    def test_bulk_commit(self):
        d = DbDict(DB_NAME, 'table')
        d.clear()
        n = 1000
        with d.bulk_commit():
            for i in range(n):
                d[i] = i
        self.assertEqual(list(d.keys()), list(range(n)))

    def test_switch_commit(self):
        d = DbDict(DB_NAME)
        d.clear()
        d[1] = 1
        d = DbDict(DB_NAME)
        self.assertIn(1, d)

        d.can_commit = False
        d[2] = 2

        d = DbDict(DB_NAME)
        self.assertNotIn(2, d)
        self.assert_(d.can_commit)

    def test_str(self):
        d = DbDict(DB_NAME)
        d.clear()
        d[1] = 1
        d[2] = 2
        self.assertEqual(str(d), '{1: 1, 2: 2}')

    def test_del(self):
        d = DbDict(DB_NAME)
        d.clear()
        for i in range(5):
            d[i] = i
        del d[0]
        del d[1]
        del d[2]
        self.assertEqual(list(d.keys()), list(range(3, 5)))

        with self.assertRaises(KeyError):
            del d[0]

    def test_picklable_dict(self):
        d = DbPickleDict(DB_NAME)
        d[1] = ForPickle()
        d = DbPickleDict(DB_NAME)
        self.assertEqual(d[1].a, 1)
        self.assertEqual(d[1].b, 2)

    def test_len(self):
        d = DbDict(DB_NAME)
        d.clear()
        n = 5
        for i in range(n):
            d[i] = i
        self.assertEqual(len(d), n)

    def test_fast_save(self):
        d1 = DbDict(DB_NAME, fast_save=True)
        d2 = DbDict(DB_NAME, 'data2', d1, fast_save=True)
        d1.clear()
        n = 1000
        for i in range(n):
            d1[i] = i
            d2[i * 2] = i
        # TODO HACK if we will not sort, fast save can produce different order of records
        self.assertEqual(sorted(d1.keys()), list(range(n)))
        self.assertEqual(sorted(d2.values()), list(range(n)))

    def test_usage_with_threads(self):
        d = DbDict(DB_NAME)
        d.clear()
        n = 10
        fails = []
        def do_inserts(values):
            try:
                for v in values:
                    print v
                    d[v] = v
            except Exception:
                fails.append(1)
                raise

        threads = [Thread(target=do_inserts, args=(range(n),)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assert_(not fails)
        for i in range(n):
            self.assert_(i in d)


class ForPickle(object):
    a = 1
    b = 2

if __name__ == '__main__':
    unittest.main()
