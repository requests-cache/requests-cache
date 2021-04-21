import pytest
from os import getenv
from threading import Thread
from time import time

from requests_cache.backends import BACKEND_CLASSES
from requests_cache.session import CachedSession
from tests.conftest import AWS_OPTIONS, httpbin

# Allow running longer stress tests with an environment variable
MULTIPLIER = int(getenv('STRESS_TEST_MULTIPLIER', '1'))
N_THREADS = 2 * MULTIPLIER
N_ITERATIONS = 4 * MULTIPLIER


@pytest.mark.parametrize('iteration', range(N_ITERATIONS))
@pytest.mark.parametrize('backend', BACKEND_CLASSES.keys())
def test_caching_with_threads(backend, iteration):
    """Run a multi-threaded stress test for each backend"""
    start = time()
    session = CachedSession(backend=backend, **AWS_OPTIONS)
    session.cache.clear()
    url = httpbin('anything')

    def send_requests():
        for i in range(N_ITERATIONS):
            session.get(url, params={f'key_{i}': f'value_{i}'})

    threads = [Thread(target=send_requests) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time() - start
    average = (elapsed * 1000) / (N_ITERATIONS * N_THREADS)
    print(f'{backend}: Ran {N_ITERATIONS} iterations with {N_THREADS} threads each in {elapsed} s')
    print(f'Average time per request: {average} ms')

    for i in range(N_ITERATIONS):
        assert session.cache.has_url(f'{url}?key_{i}=value_{i}')
