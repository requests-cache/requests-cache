import pytest
from datetime import datetime, timedelta
from io import BytesIO
from time import sleep

from urllib3.response import HTTPResponse

from requests_cache.models.response import CachedResponse, format_file_size
from tests.conftest import MOCKED_URL


def test_basic_attrs(mock_session):
    response = CachedResponse.from_response(mock_session.get(MOCKED_URL), cache_key='5ff64e')

    assert response.from_cache is True
    assert response.cache_key == '5ff64e'
    assert response.url == MOCKED_URL
    assert response.status_code == 200
    assert response.reason is None
    assert response.encoding == 'ISO-8859-1'
    assert response.headers['Content-Type'] == 'text/plain'
    assert response.text == 'mock response'
    assert response.created_at is not None
    assert response.expires is None
    assert response.is_expired is False


def test_history(mock_session):
    original_response = mock_session.get(MOCKED_URL)
    original_response.history = [mock_session.get(MOCKED_URL)] * 3
    response = CachedResponse.from_response(original_response)
    assert len(response.history) == 3
    assert all([isinstance(r, CachedResponse) for r in response.history])


@pytest.mark.parametrize(
    'expires, is_expired',
    [
        (datetime.utcnow() + timedelta(days=1), False),
        (datetime.utcnow() - timedelta(days=1), True),
    ],
)
def test_is_expired(expires, is_expired, mock_session):
    response = CachedResponse.from_response(mock_session.get(MOCKED_URL), expires=expires)
    assert response.from_cache is True
    assert response.is_expired == is_expired


def test_iterator(mock_session):
    # Set up mock response with streamed content
    url = f'{MOCKED_URL}/stream'
    mock_raw_response = HTTPResponse(
        body=BytesIO(b'mock response'),
        status=200,
        request_method='GET',
        decode_content=False,
        preload_content=False,
    )
    mock_session.mock_adapter.register_uri(
        'GET',
        url,
        status_code=200,
        raw=mock_raw_response,
    )

    # Expect the same chunks of data from the original response and subsequent cached responses
    last_request_chunks = None
    for i in range(3):
        response = mock_session.get(url, stream=True)
        chunks = list(response.iter_lines())
        if i == 0:
            assert response.from_cache is False
        else:
            assert response.from_cache is True
            assert chunks == last_request_chunks
        last_request_chunks = chunks


def test_revalidate__extend_expiration(mock_session):
    # Start with an expired response
    response = CachedResponse.from_response(
        mock_session.get(MOCKED_URL),
        expires=datetime.utcnow() - timedelta(seconds=0.01),
    )
    assert response.is_expired is True

    # Set expiration in the future and revalidate
    is_expired = response.revalidate(datetime.utcnow() + timedelta(seconds=0.01))
    assert is_expired is response.is_expired is False
    sleep(0.1)
    assert response.is_expired is True


def test_revalidate__shorten_expiration(mock_session):
    # Start with a non-expired response
    response = CachedResponse.from_response(
        mock_session.get(MOCKED_URL),
        expires=datetime.utcnow() + timedelta(seconds=1),
    )
    assert response.is_expired is False

    # Set expiration in the past and revalidate
    is_expired = response.revalidate(datetime.utcnow() - timedelta(seconds=1))
    assert is_expired is response.is_expired is True


def test_size(mock_session):
    response = CachedResponse.from_response(mock_session.get(MOCKED_URL))
    response._content = None
    assert response.size == 0
    response._content = b'1' * 1024
    assert response.size == 1024


def test_str(mock_session):
    """Just ensure that a subset of relevant attrs get included in the response str; the format
    may change without breaking the test.
    """
    response = CachedResponse.from_response(mock_session.get(MOCKED_URL))
    response._content = b'1010'
    expected_values = ['GET', MOCKED_URL, 200, '4 bytes', 'created', 'expires', 'fresh']
    assert all([str(v) in str(response) for v in expected_values])


def test_repr(mock_session):
    """Just ensure that a subset of relevant attrs get included in the response repr"""
    response = CachedResponse.from_response(mock_session.get(MOCKED_URL))
    expected_values = ['GET', MOCKED_URL, 200, 'ISO-8859-1', response.headers]
    print(repr(response))
    assert repr(response).startswith('CachedResponse(') and repr(response).endswith(')')
    assert all([str(v) in repr(response) for v in expected_values])


@pytest.mark.parametrize(
    'n_bytes, expected_size',
    [
        (None, '0 bytes'),
        (5, '5 bytes'),
        (3 * 1024, '3.00 KiB'),
        (1024 * 3000, '2.93 MiB'),
        (1024 * 1024 * 5000, '4.88 GiB'),
    ],
)
def test_format_file_size(n_bytes, expected_size):
    assert format_file_size(n_bytes) == expected_size
