"""Classes to wrap cached response objects"""
from copy import copy
from datetime import datetime, timedelta
from io import BytesIO
from logging import getLogger
from typing import Any, Dict, Optional, Union

from requests import Response
from urllib3.response import HTTPResponse

# Reponse attributes to copy
RESPONSE_ATTRS = Response.__attrs__
RAW_RESPONSE_ATTRS = [
    'decode_content',
    'headers',
    'reason',
    'request_method',
    'request_url',
    'status',
    'strict',
    'version',
]

ExpirationTime = Union[None, int, float, datetime, timedelta]
logger = getLogger(__name__)


class CachedResponse(Response):
    """A serializable wrapper for :py:class:`requests.Response`. CachedResponse objects will behave
    the same as the original response, but with some additional cache-related details. This class is
    responsible for converting and setting cache expiration times, and converting response info into
    a serializable format.

    Args:
        original_response: Response object
        expire_after: Time after which this cached response will expire
    """

    def __init__(self, original_response: Response, expire_after: ExpirationTime = None):
        """Create a CachedResponse based on an original Response"""
        super().__init__()
        # Set cache-specific attrs
        self.created_at = datetime.utcnow()
        self.expires = self._get_expiration_datetime(expire_after)
        self.from_cache = True

        # Copy basic response attrs and original request
        for k in RESPONSE_ATTRS:
            setattr(self, k, getattr(original_response, k, None))
        self.request = copy(original_response.request)
        self.request.hooks = []

        # Read content to support streaming requests, and reset file pointer on original request
        self._content = original_response.content
        if hasattr(original_response.raw, '_fp'):
            original_response.raw._fp = BytesIO(self._content or b'')

        # Copy raw response
        self._raw_response = None
        self._raw_response_attrs: Dict[str, Any] = {}
        for k in RAW_RESPONSE_ATTRS:
            self._raw_response_attrs[k] = getattr(original_response.raw, k, None)

        # Copy redirect history, if any; avoid recursion by not copying redirects of redirects
        self.history = []
        if not self.is_redirect:
            for redirect in original_response.history:
                self.history.append(CachedResponse(redirect))

    def __getstate__(self):
        """Override pickling behavior in ``requests.Response.__getstate__``"""
        return self.__dict__

    def _get_expiration_datetime(self, expire_after: ExpirationTime) -> Optional[datetime]:
        """Convert a time value or delta to an absolute datetime, if it's not already"""
        logger.debug(f'Determining expiration time based on: {expire_after}')
        if expire_after is None or expire_after == -1:
            return None
        elif isinstance(expire_after, datetime):
            return expire_after

        if not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        return self.created_at + expire_after

    def reset(self):
        """Reset raw response file handler, if previously initialized"""
        self._raw_response = None

    @property
    def is_expired(self) -> bool:
        """Determine if this cached response is expired"""
        return self.expires is not None and datetime.utcnow() > self.expires

    @property
    def raw(self) -> HTTPResponse:
        """Reconstruct a raw urllib response object from stored attrs"""
        if not self._raw_response:
            logger.debug('Rebuilding raw response object')
            self._raw_response = CachedHTTPResponse(body=self._content, **self._raw_response_attrs)
        return self._raw_response

    @raw.setter
    def raw(self, value):
        """No-op to handle requests.Response attempting to set self.raw"""

    def revalidate(self, expire_after: ExpirationTime) -> bool:
        """Set a new expiration for this response, and determine if it is now expired"""
        self.expires = self._get_expiration_datetime(expire_after)
        return self.is_expired


class CachedHTTPResponse(HTTPResponse):
    """A wrapper for raw urllib response objects, which wraps cached content with support for
    streaming requests
    """

    def __init__(self, body: bytes = None, **kwargs):
        kwargs.setdefault('preload_content', False)
        super().__init__(body=BytesIO(body or b''), **kwargs)
        self._body = body

    def release_conn(self):
        """No-op for compatibility"""

    def read(self, amt=None, decode_content=False, **kwargs):
        """Simplified reader for cached content that emulates
        :py:meth:`urllib3.response.HTTPResponse.read()`
        """
        data = self._fp.read(amt)
        decode_content = self.decode_content if decode_content is None else decode_content

        # "close" the file to inform consumers to stop reading from it
        if not data:
            self._fp.close()
        # Decode binary content, if specified
        elif decode_content:
            self._init_decoder()
            data = self._decode(data, decode_content=True, flush_decoder=True)

        return data

    def stream(self, amt=None, **kwargs):
        """Simplified generator over cached content that emulates
        :py:meth:`urllib3.response.HTTPResponse.stream()`
        """
        while not self._fp.closed:
            yield self.read(amt=amt, **kwargs)


AnyResponse = Union[Response, CachedResponse]


def set_response_defaults(response: AnyResponse) -> AnyResponse:
    """Set some default CachedResponse values on a requests.Response object, so they can be
    expected to always be present
    """
    if not isinstance(response, CachedResponse):
        response.created_at = None
        response.expires = None
        response.from_cache = False
        response.is_expired = False
    return response
