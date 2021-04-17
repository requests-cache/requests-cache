#!/usr/bin/env python3
"""
An example of testing the cache to prove that it's not making more requests than expected.
"""
from contextlib import contextmanager
from logging import basicConfig, getLogger
from unittest.mock import patch

import requests

from requests_cache import CachedSession
from requests_cache.session import OriginalSession, set_response_defaults

basicConfig(level='INFO')
logger = getLogger('requests_cache.examples')
# Uncomment for more verbose debug output
# getLogger('requests_cache').setLevel('DEBUG')


@contextmanager
def log_requests():
    """Context manager that mocks and logs all non-cached requests"""
    real_response = set_response_defaults(requests.get('http://httpbin.org/get'))
    with patch.object(OriginalSession, 'send', return_value=real_response) as mock_send:
        session = CachedSession('cache-test', backend='sqlite')
        session.cache.clear()
        yield session
        cached_responses = session.cache.responses.values()

    logger.debug('All calls to Session._request():')
    logger.debug(mock_send.mock_calls)

    logger.info(f'Responses cached: {len(cached_responses)}')
    logger.info(f'Requests sent: {mock_send.call_count}')


def main():
    """Example usage; replace with any other requests you want to test"""
    with log_requests() as session:
        for i in range(10):
            response = session.get('http://httpbin.org/get')
            logger.debug(f'Response {i}: {type(response).__name__}')


if __name__ == '__main__':
    main()
