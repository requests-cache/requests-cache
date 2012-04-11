#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends
    ~~~~~~~~~~~~~~~~~~~~~~~

    Classes and functions for cache persistence
"""

from requests_cache.backends.sqlite import DbCache
from requests_cache.backends.base import BaseCache

registry = {
    'sqlite': DbCache,
    'memory': BaseCache,
}
try:
    from requests_cache.backends.mongo import MongoCache
    registry['mongo'] = registry['mongodb'] = MongoCache
except ImportError:
    MongoCache = None
