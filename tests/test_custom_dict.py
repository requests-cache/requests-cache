#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

from requests_cache.backends.storage.dbdict import DbDict, DbPickleDict

NAMESPACE = 'requests-cache-temporary-db-test-will-be-deleted'


class BaseCustomDictTestCase(object):

    dict_class = DbDict
    pickled_dict_class = DbPickleDict

    def test_set_get(self):
        d1 = self.dict_class(NAMESPACE, 'table1')
        d2 = self.dict_class(NAMESPACE, 'table2')
        d3 = self.dict_class(NAMESPACE, 'table3')
        d1[1] = 1
        d2[2] = 2
        d3[3] = 3
        self.assertEqual(list(d1.keys()), [1])
        self.assertEqual(list(d2.keys()), [2])
        self.assertEqual(list(d3.keys()), [3])

        with self.assertRaises(KeyError):
            a = d1[4]

    def test_str(self):
        d = self.dict_class(NAMESPACE)
        d.clear()
        d[1] = 1
        d[2] = 2
        self.assertEqual(str(d), '{1: 1, 2: 2}')

    def test_del(self):
        d = self.dict_class('test')
        d.clear()
        for i in range(5):
            d[i] = i
        del d[0]
        del d[1]
        del d[2]
        self.assertEqual(list(d.keys()), list(range(3, 5)))
        self.assertEqual(list(d.values()), list(range(3, 5)))

        with self.assertRaises(KeyError):
            del d[0]

    def test_picklable_dict(self):
        d = self.pickled_dict_class(NAMESPACE)
        d[1] = ForPickle()
        d = self.pickled_dict_class(NAMESPACE)
        self.assertEqual(d[1].a, 1)
        self.assertEqual(d[1].b, 2)

    def test_clear_and_work_again(self):
        d = self.dict_class(NAMESPACE)
        for _ in range(3):
            d.clear()
            d.clear()
            self.assertEqual(len(d), 0)
            n = 5
            for i in range(n):
                d[i] = i * 2
            self.assertEqual(len(d), n)
            self.assertEqual(d[2], 4)
            d.clear()
            self.assertEqual(len(d), 0)

    def test_same_settings(self):
        d1 = self.dict_class(NAMESPACE)
        d2 = self.dict_class(NAMESPACE, connection=d1.connection)
        d1.clear()
        d2.clear()
        d1[1] = 1
        d2[2] = 2
        self.assertEqual(d1, d2)

    def test_len(self):
        n = 5
        d = self.dict_class(NAMESPACE)
        d.clear()
        for i in range(n):
            d[i] = i
        self.assertEqual(len(d), 5)


class ForPickle(object):
    a = 1
    b = 2
