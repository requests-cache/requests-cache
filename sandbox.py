#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
from requests_cache.core import CachedSession

cs = CachedSession(allowable_methods=('GET', 'POST'))
cs.cache.clear()
for i in range(2):
    r = cs.get("http://httpbin.org/")
    print r
    print r.from_cache

