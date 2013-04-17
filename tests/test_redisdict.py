#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

import unittest
from requests_cache.backends.storage.redisdict import RedisDict, RedisPickleDict

NAMESPACE = 'requests-cache-temporary-db-test-will-be-deleted'


class DbdictTestCase(unittest.TestCase):

    def test_set_get(self):
        d1 = RedisDict(NAMESPACE, 'table1')
        d2 = RedisDict(NAMESPACE, 'table2')
        d3 = RedisDict(NAMESPACE, 'table3')
        d1[1] = 1
        d2[2] = 2
        d3[3] = 3
        self.assertEqual(list(d1.keys()), [1])
        self.assertEqual(list(d2.keys()), [2])
        self.assertEqual(list(d3.keys()), [3])

        with self.assertRaises(KeyError):
            a = d1[4]

    def test_str(self):
        d = RedisDict('test')
        d.clear()
        d[1] = 1
        d[2] = 2
        self.assertEqual(str(d), '{1: 1, 2: 2}')

    def test_del(self):
        d = RedisDict('test')
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
        d = RedisPickleDict(NAMESPACE)
        d[1] = ForPickle()
        d = RedisPickleDict(NAMESPACE)
        self.assertEqual(d[1].a, 1)
        self.assertEqual(d[1].b, 2)

    def test_clear_and_work_again(self):
        d = RedisDict(NAMESPACE)
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
        d1 = RedisDict(NAMESPACE)
        d2 = RedisDict(NAMESPACE, connection=d1.connection)
        d1.clear()
        d2.clear()
        d1[1] = 1
        d2[2] = 2
        self.assertEqual(d1, d2)

    def test_len(self):
        n = 5
        d = RedisDict('test')
        for i in range(n):
            d[i] = i
        self.assertEqual(len(d), 5)


class ForPickle(object):
    a = 1
    b = 2

if __name__ == '__main__':
    unittest.main()
