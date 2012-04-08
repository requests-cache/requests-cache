#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends
    ~~~~~~~~~~~~~~~~~~~~~~~

    Classes and functions for cache persistence
"""

from requests_cache.backends.sqlite import DbCache
from requests_cache.backends.base import MemoryCache

registry = {
    'sqlite': DbCache,
    'memory': MemoryCache,
    }
