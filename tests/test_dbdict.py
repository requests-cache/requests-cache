#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

import unittest
from requests_cache.backends.dbdict import DbDict, DbPickleDict

class DbdictTestCase(unittest.TestCase):
    def test_reusable_dicts(self):
        d1 = DbDict('test', 'table1')
        d2 = DbDict('test', 'table2', d1)
        d3 = DbDict('test', 'table3', d1)
        d1[1] = 1
        d2[2] = 2
        d3[3] = 3
        self.assertEqual(list(d1.keys()), [1])
        self.assertEqual(list(d2.keys()), [2])
        self.assertEqual(list(d3.keys()), [3])

        with self.assertRaises(ValueError):
            d4 = DbDict('test', 'table1', d1)

    def test_bulk_commit(self):
        d = DbDict('test', 'test')
        d.clear()
        with d.bulk_commit():
            for i in range(100):
                d[i] = i
        self.assertEqual(list(d.keys()), list(range(100)))

    def test_switch_commit(self):
        d = DbDict('test')
        d.clear()
        d[1] = 1
        d = DbDict('test')
        self.assertIn(1, d)

        d.can_commit = False
        d[2] = 2
        self.assertEqual(d[2], 2)

        d = DbDict('test')
        self.assertNotIn(2, d)
        self.assert_(d.can_commit)

    def test_str(self):
        d = DbDict('test')
        d.clear()
        d[1] = 1
        d[2] = 2
        self.assertEqual(str(d), '{1: 1, 2: 2}')

    def test_del(self):
        d = DbDict('test')
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
        d = DbPickleDict('test')
        d[1] = ForPickle()
        d = DbPickleDict('test')
        self.assertEqual(d[1].a, 1)
        self.assertEqual(d[1].b, 2)

    def test_len(self):
        n = 5
        d = DbDict('test')
        for i in range(n):
            d[i] = i
        self.assertEqual(len(d), 5)


class ForPickle(object):
    a = 1
    b = 2

if __name__ == '__main__':
    unittest.main()
