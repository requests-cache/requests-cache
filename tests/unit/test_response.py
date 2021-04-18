import pytest
from datetime import datetime, timedelta
from io import BytesIO
from time import sleep

from urllib3.response import HTTPResponse

from requests_cache import CachedHTTPResponse, CachedResponse
from tests.conftest import MOCKED_URL


def test_basic_attrs(mock_session):
    response = CachedResponse(mock_session.get(MOCKED_URL))

    assert response.from_cache is True
    assert response.url == MOCKED_URL
    assert response.status_code == 200
    assert response.reason is None
    assert response.encoding == 'ISO-8859-1'
    assert response.headers['Content-Type'] == 'text/plain'
    assert response.text == 'mock response'
    assert response.created_at is not None
    assert response.expires is None
    assert response.is_expired is False


@pytest.mark.parametrize(
    'expire_after, is_expired',
    [
        (None, False),
        (datetime.utcnow() + timedelta(days=1), False),
        (datetime.utcnow() - timedelta(days=1), True),
    ],
)
def test_expiration(expire_after, is_expired, mock_session):
    response = CachedResponse(mock_session.get(MOCKED_URL), expire_after)
    assert response.from_cache is True
    assert response.is_expired == is_expired


def test_history(mock_session):
    original_response = mock_session.get(MOCKED_URL)
    original_response.history = [mock_session.get(MOCKED_URL)] * 3
    response = CachedResponse(original_response)
    assert len(response.history) == 3
    assert all([isinstance(r, CachedResponse) for r in response.history])


def test_raw_response__read(mock_session):
    response = CachedResponse(mock_session.get(MOCKED_URL))
    assert isinstance(response.raw, CachedHTTPResponse)
    assert response.raw.read(10) == b'mock respo'
    assert response.raw.read(None) == b'nse'
    assert response.raw.read(1) == b''
    assert response.raw._fp.closed is True


def test_raw_response__close(mock_session):
    response = CachedResponse(mock_session.get(MOCKED_URL))
    response.close()
    assert response.raw._fp.closed is True


def test_raw_response__reset(mock_session):
    response = CachedResponse(mock_session.get(MOCKED_URL))
    response.raw.read(None)
    assert response.raw.read(1) == b''
    assert response.raw._fp.closed is True

    response.reset()
    assert response.raw.read(None) == b'mock response'


def test_raw_response__stream(mock_session):
    response = CachedResponse(mock_session.get(MOCKED_URL))
    data = b''
    for chunk in response.raw.stream(1):
        data += chunk
    assert data == b'mock response'
    assert response.raw._fp.closed


def test_raw_response__iterator(mock_session):
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
    response = CachedResponse(
        mock_session.get(MOCKED_URL),
        expire_after=datetime.utcnow() - timedelta(seconds=0.01),
    )
    assert response.is_expired is True

    # Set expiration in the future and revalidate
    is_expired = response.revalidate(datetime.utcnow() + timedelta(seconds=0.01))
    assert is_expired is response.is_expired is False
    sleep(0.1)
    assert response.is_expired is True


def test_revalidate__shorten_expiration(mock_session):
    # Start with a non-expired response
    response = CachedResponse(
        mock_session.get(MOCKED_URL),
        expire_after=datetime.utcnow() + timedelta(seconds=1),
    )
    assert response.is_expired is False

    # Set expiration in the past and revalidate
    is_expired = response.revalidate(datetime.utcnow() - timedelta(seconds=1))
    assert is_expired is response.is_expired is True
