import os
import unittest
from threading import Thread
from unittest.mock import patch

from requests_cache.backends.sqlite import DbDict, DbPickleDict
from tests.integration.test_backends import BaseStorageTestCase


class SQLiteTestCase(BaseStorageTestCase):
    def tearDown(self):
        try:
            os.unlink(self.NAMESPACE)
        except Exception:
            pass

    def test_bulk_commit(self):
        d = self.storage_class(self.NAMESPACE, self.TABLES[0])
        with d.bulk_commit():
            pass
        d.clear()
        n = 1000
        with d.bulk_commit():
            for i in range(n):
                d[i] = i
        assert list(d.keys()) == list(range(n))

    def test_switch_commit(self):
        d = self.storage_class(self.NAMESPACE)
        d.clear()
        d[1] = 1
        d = self.storage_class(self.NAMESPACE)
        assert 1 in d

        d._can_commit = False
        d[2] = 2

        d = self.storage_class(self.NAMESPACE)
        assert 2 not in d
        assert d._can_commit is True

    def test_fast_save(self):
        d1 = self.storage_class(self.NAMESPACE, fast_save=True)
        d2 = self.storage_class(self.NAMESPACE, self.TABLES[1], fast_save=True)
        d1.clear()
        n = 1000
        for i in range(n):
            d1[i] = i
            d2[i * 2] = i
        # HACK if we will not sort, fast save can produce different order of records
        assert sorted(d1.keys()) == list(range(n))
        assert sorted(d2.values()) == list(range(n))

    def test_usage_with_threads(self):
        def do_test_for(d, n_threads=5):
            d.clear()

            def do_inserts(values):
                for v in values:
                    d[v] = v

            def values(x, n):
                return [i * x for i in range(n)]

            threads = [Thread(target=do_inserts, args=(values(i, n_threads),)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            for i in range(n_threads):
                for x in values(i, n_threads):
                    assert d[x] == x

        do_test_for(self.storage_class(self.NAMESPACE))
        do_test_for(self.storage_class(self.NAMESPACE, fast_save=True), 20)
        do_test_for(self.storage_class(self.NAMESPACE, fast_save=True))
        do_test_for(self.storage_class(self.NAMESPACE, self.TABLES[1], fast_save=True))


class DbDictTestCase(SQLiteTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=DbDict, **kwargs)


class DbPickleDictTestCase(SQLiteTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=DbPickleDict, picklable=True, **kwargs)


@patch('requests_cache.backends.sqlite.sqlite3')
def test_timeout(mock_sqlite):
    """Just make sure the optional 'timeout' param gets passed to sqlite3.connect"""
    DbDict('test', timeout=0.5)
    mock_sqlite.connect.assert_called_with('test', timeout=0.5)
