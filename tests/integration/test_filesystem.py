import pytest
import unittest
from os.path import isfile
from shutil import rmtree

from requests_cache.backends import FileDict
from tests.integration.test_backends import BaseStorageTestCase


class FilesystemTestCase(BaseStorageTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=FileDict, picklable=True, **kwargs)

    def tearDown(self):
        rmtree(self.NAMESPACE)

    def test_set_get(self):
        cache = self.storage_class(self.NAMESPACE)
        cache['key'] = 'value'
        assert list(cache.keys()) == ['key']
        assert list(cache.values()) == ['value']

        with pytest.raises(KeyError):
            cache[4]

    def test_paths(self):
        cache = self.storage_class(self.NAMESPACE)
        for i in range(10):
            cache[f'key_{i}'] = f'value_{i}'

        for path in cache.paths():
            assert isfile(path)
