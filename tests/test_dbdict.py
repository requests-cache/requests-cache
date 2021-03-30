#!/usr/bin/env python
import unittest
from threading import Thread
from unittest.mock import patch

from requests_cache.backends.sqlite import DbDict, DbPickleDict
from tests.test_custom_dict import BaseCustomDictTestCase


class DbdictTestCase(BaseCustomDictTestCase, unittest.TestCase):
    def test_bulk_commit(self):
        d = DbDict(self.NAMESPACE, self.TABLES[0])
        with d.bulk_commit():
            pass
        d.clear()
        n = 1000
        with d.bulk_commit():
            for i in range(n):
                d[i] = i
        self.assertEqual(list(d.keys()), list(range(n)))

    def test_switch_commit(self):
        d = DbDict(self.NAMESPACE)
        d.clear()
        d[1] = 1
        d = DbDict(self.NAMESPACE)
        self.assertIn(1, d)

        d._can_commit = False
        d[2] = 2

        d = DbDict(self.NAMESPACE)
        self.assertNotIn(2, d)
        self.assertTrue(d._can_commit)

    def test_fast_save(self):
        d1 = DbDict(self.NAMESPACE, fast_save=True)
        d2 = DbDict(self.NAMESPACE, self.TABLES[1], fast_save=True)
        d1.clear()
        n = 1000
        for i in range(n):
            d1[i] = i
            d2[i * 2] = i
        # HACK if we will not sort, fast save can produce different order of records
        self.assertEqual(sorted(d1.keys()), list(range(n)))
        self.assertEqual(sorted(d2.values()), list(range(n)))

    def test_usage_with_threads(self):
        def do_test_for(d, n_threads=5):
            d.clear()
            fails = []

            def do_inserts(values):
                try:
                    for v in values:
                        d[v] = v
                except Exception:
                    fails.append(1)
                    raise

            def values(x, n):
                return [i * x for i in range(n)]

            threads = [Thread(target=do_inserts, args=(values(i, n_threads),)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertFalse(fails)
            for i in range(n_threads):
                for x in values(i, n_threads):
                    self.assertEqual(d[x], x)

        do_test_for(DbDict(self.NAMESPACE, fast_save=True), 20)
        do_test_for(DbPickleDict(self.NAMESPACE, fast_save=True), 10)
        d1 = DbDict(self.NAMESPACE, fast_save=True)
        d2 = DbDict(self.NAMESPACE, self.TABLES[1], fast_save=True)
        do_test_for(d1)
        do_test_for(d2)
        do_test_for(DbDict(self.NAMESPACE))


@patch('requests_cache.backends.sqlite.sqlite3')
def test_timeout(mock_sqlite):
    """Just make sure the optional 'timeout' param gets passed to sqlite3.connect"""
    DbDict('test', timeout=0.5)
    mock_sqlite.connect.assert_called_with('test', timeout=0.5)


if __name__ == '__main__':
    unittest.main()
