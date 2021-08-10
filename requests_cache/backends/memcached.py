# TODO: Currently only supports text-based serialization formats.
#   pymemcache does not yet have support for binary or meta protocol.
#   pylibmc does, but requires libmemcached binaries on the host machine,
#   so it's not compatible with memcached running in a Docker container.
import re
from telnetlib import Telnet
from typing import Optional

from pymemcache.client.base import Client

from . import BaseCache, BaseStorage, get_valid_kwargs

KEY_PATTERN = re.compile(rb'ITEM (\S*)')


class FileCache(BaseCache):
    """Memcached backend"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.responses = MemcacheDict('responses', **kwargs)
        self.redirects = MemcacheDict('redirects', connection=self.responses.connection, **kwargs)


class MemcacheDict(BaseStorage):
    """A dictionary-like interface to memcached"""

    def __init__(
        self,
        key_prefix: Optional[str] = None,
        connection=None,
        host='localhost',
        timeout: float = 5,
        **kwargs,
    ):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(Client, kwargs)
        self.connection = connection or Client(
            host,
            key_prefix=key_prefix,
            encoding='utf-8',
            timeout=timeout,
            **connection_kwargs,
        )

    def __getitem__(self, key):
        item = self.connection.get(key)
        if not item:
            raise KeyError
        return item

    def __setitem__(self, key, value):
        self.connection.set(key, value)

    def __delitem__(self, key):
        if not self.connection.delete(key):
            raise KeyError

    # TODO: Is there a cleaner way to do this?
    def __iter__(self):
        host, port = self.client.server
        stats_client = Telnet(host, port)
        stats_client.write(b'stats cachedump 1 10000\n')
        output = stats_client.read_until(b'END')
        return KEY_PATTERN.findall(output)

    def __len__(self):
        return self.connection.stats().get(b'curr_items', 0)

    def clear(self):
        self.connection.flush_all()


class MemcachePickleDict(MemcacheDict):
    """Same as :class:`MemcacheDict`, but serializes values before saving"""

    def __setitem__(self, key, value):
        serialized_value = self.serializer.dumps(value)
        # if isinstance(serialized_value, bytes):
        #     serialized_value = '?'
        super().__setitem__(key, serialized_value)

    def __getitem__(self, key):
        return self.serializer.loads(super().__getitem__(key))
