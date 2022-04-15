"""
.. image::
    ../_static/mongodb.png

`MongoDB <https://www.mongodb.com>`_ is a NoSQL document database. It stores data in collections
of documents, which are more flexible and less strictly structured than tables in a relational
database.

Use Cases
^^^^^^^^^
MongoDB scales well and is a good option for larger applications. For raw caching performance,
it is not quite as fast as :py:mod:`~requests_cache.backends.redis`, but may be preferable if you
already have a MongoDB instance you're using for other purposes, or if you find it easier to use.

Expiration
^^^^^^^^^^
MongoDB `natively supports TTL <https://www.mongodb.com/docs/v4.0/core/index-ttl>`_, and can
automatically remove expired responses from the cache.

**Notes:**

* TTL is set for a whole collection, and cannot be set on a per-document basis.
* It will persist until explicitly removed or overwritten, or if the collection is deleted.
* Expired items are
  `not guaranteed to be removed immediately <https://www.mongodb.com/docs/v4.0/core/index-ttl/#timing-of-the-delete-operation>`_.
  Typically it happens within 60 seconds.
* If you want, you can rely entirely on MongoDB TTL instead of requests-cache
  :ref:`expiration settings <expiration>`.
* Or you can set both values, to be certain that you don't get an expired response before MongoDB
  removes it.
* If you intend to reuse expired responses, e.g. with :ref:`conditional-requests` or ``stale_if_error``,
  you can set TTL to a larger value than your session ``expire_after``, or disable it altogether.

**Examples:**

Create a TTL index:

>>> backend = MongoCache()
>>> backend.set_ttl(3600)

Overwrite it with a new value:

>>> backend = MongoCache()
>>> backend.set_ttl(timedelta(days=1), overwrite=True)

Remove the TTL index:

>>> backend = MongoCache()
>>> backend.set_ttl(None, overwrite=True)

Use both MongoDB TTL and requests-cache expiration:

>>> ttl = timedelta(days=1)
>>> backend = MongoCache()
>>> backend.set_ttl(ttl)
>>> session = CachedSession(backend=backend, expire_after=ttl)

**Recommended:** Set MongoDB TTL to a longer value than your :py:class:`.CachedSession` expiration.
This allows expired responses to be eventually cleaned up, but still be reused for conditional
requests for some period of time:

    >>> backend = MongoCache()
    >>> backend.set_ttl(timedelta(days=7))
    >>> session = CachedSession(backend=backend, expire_after=timedelta(days=1))

Connection Options
^^^^^^^^^^^^^^^^^^
The MongoDB backend accepts any keyword arguments for :py:class:`pymongo.mongo_client.MongoClient`.
These can be passed via :py:class:`.MongoCache`:

    >>> backend = MongoCache(host='192.168.1.63', port=27017)
    >>> session = CachedSession('http_cache', backend=backend)

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.mongodb
   :classes-only:
   :nosignatures:
"""
from datetime import timedelta
from logging import getLogger
from typing import Iterable, Mapping, Union

from pymongo import MongoClient
from pymongo.errors import OperationFailure

from .._utils import get_valid_kwargs
from ..expiration import NEVER_EXPIRE, get_expiration_seconds
from ..serializers import SerializerPipeline
from ..serializers.preconf import bson_preconf_stage
from . import BaseCache, BaseStorage

document_serializer = SerializerPipeline([bson_preconf_stage], is_binary=False)
logger = getLogger(__name__)


# TODO: TTL tests
# TODO: Example of viewing responses with MongoDB VSCode plugin or other GUI
# TODO: Is there any reason to support custom serializers here?
# TODO: Save items with different cache keys to avoid conflicts with old serialization format?
# TODO: Set TTL for redirects? Or just clean up with remove_invalid_redirects()?
class MongoCache(BaseCache):
    """MongoDB cache backend

    Args:
        db_name: Database name
        connection: :py:class:`pymongo.MongoClient` object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`pymongo.mongo_client.MongoClient`
    """

    def __init__(self, db_name: str = 'http_cache', connection: MongoClient = None, **kwargs):
        super().__init__(**kwargs)
        self.responses: MongoDict = MongoPickleDict(
            db_name,
            collection_name='responses',
            connection=connection,
            **kwargs,
        )
        self.redirects: MongoDict = MongoDict(
            db_name,
            collection_name='redirects',
            connection=self.responses.connection,
            **kwargs,
        )

    def set_ttl(self, ttl: Union[int, timedelta], overwrite: bool = False):
        """Set MongoDB TTL for all collections. Notes:

        * This will have no effect if TTL is already set
        * To overwrite an existing TTL index, use ``overwrite=True``
        * Use ``ttl=None, overwrite=True`` to remove the TTL index
        * This may take some time to complete, depending on the size of your cache
        """
        self.responses.set_ttl(ttl, overwrite=overwrite)
        self.redirects.set_ttl(ttl, overwrite=overwrite)


class MongoDict(BaseStorage):
    """A dictionary-like interface for a MongoDB collection

    Args:
        db_name: Database name
        collection_name: Collection name
        connection: :py:class:`pymongo.MongoClient` object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`pymongo.MongoClient`
    """

    def __init__(
        self,
        db_name: str,
        collection_name: str = 'http_cache',
        connection: MongoClient = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(MongoClient, kwargs)
        self.connection = connection or MongoClient(**connection_kwargs)
        self.collection = self.connection[db_name][collection_name]

    def set_ttl(self, ttl: Union[int, timedelta], overwrite: bool = False):
        if overwrite:
            try:
                self.collection.drop_index('ttl_idx')
                logger.info('Dropped TTL index')
            except OperationFailure:
                pass

        ttl = get_expiration_seconds(ttl)
        if ttl and ttl != NEVER_EXPIRE:
            logger.info(f'Creating TTL index for {ttl} seconds')
            self.collection.create_index('created_at', name='ttl_idx', expireAfterSeconds=ttl)

    def __getitem__(self, key):
        result = self.collection.find_one({'_id': key})
        if result is None:
            raise KeyError
        return result['data'] if 'data' in result else result

    def __setitem__(self, key, item):
        """If ``item`` is already a dict, its values will be stored under top-level keys.
        Otherwise, it will be stored under a 'data' key.
        """
        if not isinstance(item, Mapping):
            item = {'data': item}
        self.collection.replace_one({'_id': key}, item, upsert=True)

    def __delitem__(self, key):
        result = self.collection.find_one_and_delete({'_id': key}, {'_id': True})
        if result is None:
            raise KeyError

    def __len__(self):
        return self.collection.estimated_document_count()

    def __iter__(self):
        for d in self.collection.find({}, {'_id': True}):
            yield d['_id']

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache. Does not raise errors for missing keys."""
        self.collection.delete_many({'_id': {'$in': list(keys)}})

    def clear(self):
        self.collection.drop()


class MongoPickleDict(MongoDict):
    """Same as :class:`MongoDict`, but serializes values before saving.

    By default, responses are only partially serialized into a MongoDB-compatible document mapping.
    """

    def __init__(self, *args, serializer=None, **kwargs):
        super().__init__(*args, serializer=serializer or document_serializer, **kwargs)

    def __getitem__(self, key):
        return self.serializer.loads(super().__getitem__(key))

    def __setitem__(self, key, item):
        super().__setitem__(key, self.serializer.dumps(item))
