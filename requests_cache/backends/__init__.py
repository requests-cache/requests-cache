#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends
    ~~~~~~~~~~~~~~~~~~~~~~~

    Classes and functions for cache persistence
"""

from .sqlite import DbCache
from .base import BaseCache

registry = {
    'sqlite': DbCache,
    'memory': BaseCache,
}
try:
    from .mongo import MongoCache
    registry['mongo'] = registry['mongodb'] = MongoCache
except ImportError:
    MongoCache = None
