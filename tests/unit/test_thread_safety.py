import pytest
from threading import Thread

from tests.conftest import MOCKED_URL

N_THREADS = 10
N_ITERATIONS = 20


@pytest.mark.parametrize('iteration', range(N_ITERATIONS))
@pytest.mark.parametrize('backend', ['sqlite', 'mongodb', 'gridfs', 'redis', 'dynamodb'])
def test_caching_with_threads(backend, iteration, mock_session):
    """Stress test for multi-threaded caching"""

    def send_requests(url, params):
        for i in range(10):
            mock_session.get(url, params=params)

    threads = [Thread(target=send_requests, args=(MOCKED_URL, {'param': i})) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i in range(N_THREADS):
        assert mock_session.cache.has_url(f'{MOCKED_URL}?param={i}')
