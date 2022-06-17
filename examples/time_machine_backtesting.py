#!/usr/bin/env python3
"""
An example of using the [time-machine](https://github.com/adamchainz/time-machine) library for backtesting,
e.g., testing with cached responses that were available at an arbitrary time in the past.
"""
from datetime import datetime

import requests
import time_machine

from requests_cache import CachedSession, set_response_defaults


class BacktestCachedSession(CachedSession):
    def request(self, method: str, url: str, **kwargs):
        response = super().request(method, url, **kwargs)

        # Response was cached after the (simulated) current time, so ignore it and send a new request
        if response.created_at and response.created_at > datetime.utcnow():
            new_response = requests.request(method, url, **kwargs)
            return set_response_defaults(new_response)
        else:
            return response


def demo():
    session = BacktestCachedSession()
    response = session.get('https://httpbin.org/get')
    response = session.get('https://httpbin.org/get')
    assert response.from_cache is True

    # Response was not cached yet at this point, so we should get a fresh one
    with time_machine.travel(datetime(2020, 1, 1)):
        response = session.get('https://httpbin.org/get')
        assert response.from_cache is False


if __name__ == '__main__':
    demo()
