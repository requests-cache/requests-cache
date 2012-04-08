#!/usr/bin/env python
# -*- coding: utf-8 -*-
#date: 08.04.12
import time
import requests_cache
import requests
from requests import async


def main():
    requests_cache.configure('test')
    requests_cache.clear()

    for i in range(10):
        r = requests.get('http://httpbin.org/redirect/10')
        r = requests.get('http://httpbin.org/delay/3')
        print r.text, r.cookies

    rs = [async.get('http://httpbin.org/delay/%s' % i) for i in range(5)]
    for r in async.map(rs):
        print r.text
    print requests_cache.core._cache


if __name__ == "__main__":
    t = time.time()
    main()
    print time.time() - t