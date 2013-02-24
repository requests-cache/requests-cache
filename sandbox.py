#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
from requests_cache import CachedSession

cs = CachedSession(allowable_methods=('GET', 'POST'))
cs.cache.clear()
for i in range(2):
    r = cs.get("http://httpbin.org/get?p1=v1", params={'p2': 'v2', 'p3': 'cyrЯЯ'})
    print r
    print r.from_cache

