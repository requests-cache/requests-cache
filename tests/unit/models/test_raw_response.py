from io import BytesIO

from requests_cache.models import CachedHTTPResponse
from tests.conftest import MOCKED_URL


def test_from_response(mock_session):
    response = mock_session.get(MOCKED_URL)
    response.raw._fp = BytesIO(b'mock response')
    raw = CachedHTTPResponse.from_response(response)

    assert dict(response.raw.headers) == dict(raw.headers) == {'Content-Type': 'text/plain'}
    assert raw.read(None) == b'mock response'
    assert response.raw.decode_content is raw.decode_content is False
    assert response.raw.reason is raw.reason is None
    if hasattr(response.raw, '_request_url'):
        assert response.raw._request_url is raw.request_url is None
    assert response.raw.status == raw.status == 200
    assert response.raw.strict == raw.strict == 0
    assert response.raw.version == raw.version == 0


def test_read():
    raw = CachedHTTPResponse(body=b'mock response')
    assert raw.read(10) == b'mock respo'
    assert raw.read(None) == b'nse'
    assert raw.read(1) == b''
    assert raw._fp.closed is True


def test_close():
    raw = CachedHTTPResponse(body=b'mock response')
    raw.close()
    assert raw._fp.closed is True


def test_reset():
    raw = CachedHTTPResponse(body=b'mock response')
    raw.read(None)
    assert raw.read(1) == b''
    assert raw._fp.closed is True

    raw.reset()
    assert raw.read(None) == b'mock response'


def test_set_content():
    raw = CachedHTTPResponse(body=None)
    raw.set_content(b'mock response')
    assert raw.read() == b'mock response'


def test_stream():
    raw = CachedHTTPResponse(body=b'mock response')
    data = b''
    for chunk in raw.stream(1):
        data += chunk
    assert data == b'mock response'
    assert raw._fp.closed
