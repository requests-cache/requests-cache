#!/usr/bin/env python
# -*- coding: utf-8 -*-
#date: 08.04.12
from requests_cache.backends.sqlite import DbCache
from requests_cache.backends.base import MemoryCache

registry = {
    'sqlite': DbCache,
    'memory': MemoryCache,
    }
