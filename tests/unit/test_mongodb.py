from unittest.mock import patch

import pytest

from requests_cache import CachedSession
from requests_cache.backends import GridFSCache, GridFSDict, MongoCache, MongoDict

MongoClient = pytest.importorskip('pymongo').MongoClient


@pytest.mark.parametrize('storage_class', [MongoDict, GridFSDict])
def test_storage_closes_only_owned_client(storage_class):
    owner = storage_class('owner', host='127.0.0.1', connect=False)
    client = owner.connection
    try:
        borrower = storage_class('borrower', connection=client)
        assert borrower.connection is client
        with patch.object(client, 'close', wraps=client.close) as close:
            borrower.close()
            close.assert_not_called()
            owner.close()
            close.assert_called_once_with()
    finally:
        client.close()


@pytest.mark.parametrize('cache_class', [MongoCache, GridFSCache])
@pytest.mark.parametrize('autoclose', [True, False])
def test_owned_cache_client_cleanup(cache_class, autoclose):
    cache = cache_class('owned', host='127.0.0.1', connect=False)
    client = cache.responses.connection
    try:
        assert cache.redirects.connection is client
        with patch.object(client, 'close', wraps=client.close) as close:
            cache.redirects.close()
            close.assert_not_called()
            with CachedSession(backend=cache, autoclose=autoclose):
                pass
            if not autoclose:
                close.assert_not_called()
                cache.close()
            close.assert_called_once_with()
    finally:
        client.close()


def test_sessions_leave_application_shared_client_open():
    client = MongoClient(host='127.0.0.1', connect=False)
    try:
        mongo = MongoCache('mongo', connection=client)
        gridfs = GridFSCache('gridfs', connection=client)
        for cache in (mongo, gridfs):
            assert cache.responses.connection is client
            assert cache.redirects.connection is client
        with patch.object(client, 'close', wraps=client.close) as close:
            first = CachedSession(backend=mongo)
            with CachedSession(backend=gridfs):
                first.close()
                close.assert_not_called()
            close.assert_not_called()
            first.close()
            close.assert_not_called()
    finally:
        client.close()
