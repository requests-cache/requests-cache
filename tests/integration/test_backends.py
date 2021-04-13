# TODO: Refactor with pytest fixtures
import os

from requests_cache.backends.base import BaseStorage
from requests_cache.backends.sqlite import DbDict, DbPickleDict


class BaseBackendTestCase:
    """Base class for testing backends"""

    dict_class: BaseStorage = DbDict
    pickled_dict_class: BaseStorage = DbPickleDict

    NAMESPACE = 'requests-cache-temporary-db-test-will-be-deleted'
    TABLES = ['table%s' % i for i in range(5)]

    def tearDown(self):
        if self.dict_class is DbDict:
            try:
                os.unlink(self.NAMESPACE)
            except Exception:
                pass
            return
        for table in self.TABLES:
            d = self.dict_class(self.NAMESPACE, table)
            d.clear()
        super().tearDown()

    def test_set_get(self):
        d1 = self.dict_class(self.NAMESPACE, self.TABLES[0])
        d2 = self.dict_class(self.NAMESPACE, self.TABLES[1])
        d3 = self.dict_class(self.NAMESPACE, self.TABLES[2])
        d1[1] = 1
        d2[2] = 2
        d3[3] = 3
        self.assertEqual(list(d1.keys()), [1])
        self.assertEqual(list(d2.keys()), [2])
        self.assertEqual(list(d3.keys()), [3])

        with self.assertRaises(KeyError):
            d1[4]

    def test_str(self):
        d = self.dict_class(self.NAMESPACE)
        d.clear()
        d[1] = 1
        d[2] = 2
        self.assertEqual(str(d), '{1: 1, 2: 2}')

    def test_del(self):
        d = self.dict_class(self.NAMESPACE)
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
        d = self.pickled_dict_class(self.NAMESPACE)
        d[1] = ForPickle()
        d = self.pickled_dict_class(self.NAMESPACE)
        self.assertEqual(d[1].a, 1)
        self.assertEqual(d[1].b, 2)

    def test_clear_and_work_again(self):
        d1 = self.dict_class(self.NAMESPACE)
        d2 = self.pickled_dict_class(self.NAMESPACE, connection=d1.connection)
        d1.clear()
        d2.clear()

        for i in range(5):
            d1[i] = i
            d2[i] = i

        assert len(d1) == len(d2) == 5
        d1.clear()
        d2.clear()
        assert len(d1) == len(d2) == 0

    def test_same_settings(self):
        d1 = self.dict_class(self.NAMESPACE)
        d2 = self.dict_class(self.NAMESPACE, connection=d1.connection)
        d1.clear()
        d2.clear()
        d1[1] = 1
        d2[2] = 2
        assert d1 == d2


class ForPickle(object):
    a = 1
    b = 2
