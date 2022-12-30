#!/usr/bin/env python3
"""
An example of keeping a history of cached responses, for later comparison or analysis
"""
from time import sleep

from requests_cache import CachedSession


class CachedHistorySession(CachedSession):
    """A CachedSession that keeps a copy of all previously cached responses"""

    def send(self, *args, **kwargs):
        """Save a copy of every new response"""
        response = super().send(*args, **kwargs)
        if not response.from_cache:
            self.cache.save_response(response, f'{response.cache_key}_{response.created_at}')
        return response

    def get_response_history(self, response):
        """Get a history of previously cached versions of the given response"""
        return [
            self.cache.responses[k]
            for k in self.cache.responses.keys()
            if k.startswith(response.cache_key) and k != response.cache_key
        ]


def demo():
    session = CachedHistorySession(expire_after=1)
    n_history_items = 3
    for i in range(n_history_items):
        response = session.get('https://httpbin.org/get')
        if i < n_history_items - 1:
            sleep(1)

    for r in session.get_response_history(response):
        print(r)


if __name__ == '__main__':
    demo()
