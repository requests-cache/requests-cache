"""Classes to wrap cached response objects"""
# TODO: Move expiration logic here and in CachedSession to a separate module
from copy import copy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from logging import getLogger
from typing import Any, Dict, Optional, Union

from requests import Response
from urllib3.response import HTTPResponse, is_fp_closed

from .cache_control import get_expiration_datetime

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
CACHE_ATTRS = ['from_cache', 'created_at', 'expires', 'is_expired']

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S %Z'
DO_NOT_CACHE = 0
ExpirationTime = Union[None, int, float, datetime, timedelta]
logger = getLogger(__name__)


class CachedResponse(Response):
    """A serializable wrapper for :py:class:`requests.Response`. CachedResponse objects will behave
    the same as the original response, but with some additional cache-related details. This class is
    responsible for converting and setting cache expiration times, and converting response info into
    a serializable format.

    Args:
        original_response: Response object
        expires: Time after which this cached response will expire
    """

    def __init__(self, original_response: Response, expires: datetime = None):
        """Create a CachedResponse based on an original Response"""
        super().__init__()
        # Set cache-specific attrs
        self.created_at = datetime.utcnow()
        self.expires = expires
        self.from_cache = True

        # Copy basic response attrs and original request
        for k in RESPONSE_ATTRS:
            setattr(self, k, getattr(original_response, k, None))
        self.request = copy(original_response.request)
        self.request.hooks = []

        if not is_fp_closed(getattr(original_response.raw, '_fp', None)):
            # Store raw response data
            raw_data = original_response.raw.read(decode_content=False)
            original_response.raw._fp = BytesIO(raw_data)
            self._content = original_response.content
            # Reset file pointer on original raw response
            original_response.raw._fp = BytesIO(raw_data)
            original_response.raw._fp_bytes_read = 0
            original_response.raw.length_remaining = len(raw_data)
        else:
            self._content = original_response.content

        # Copy remaining raw response attributes
        self._raw_response = None
        self._raw_response_attrs: Dict[str, Any] = {}
        for k in RAW_RESPONSE_ATTRS:
            if hasattr(original_response.raw, k):
                self._raw_response_attrs[k] = getattr(original_response.raw, k)

        # Copy redirect history, if any; avoid recursion by not copying redirects of redirects
        self.history = []
        if not self.is_redirect:
            for redirect in original_response.history:
                self.history.append(CachedResponse(redirect))

    def __getstate__(self):
        """Override pickling behavior in ``requests.Response.__getstate__``"""
        return self.__dict__

    def reset(self):
        """Reset raw response file handler, if previously initialized"""
        self._raw_response = None

    @property
    def is_expired(self) -> bool:
        """Determine if this cached response is expired"""
        return self.expires is not None and datetime.utcnow() >= self.expires

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
        self.expires = get_expiration_datetime(expire_after)
        return self.is_expired

    @property
    def size(self) -> int:
        """Get the size of the response body in bytes"""
        return len(self.content) if self.content else 0

    def __str__(self):
        return (
            f'request: {self.request.method} {self.request.url}, response: {self.status_code} '
            f'({format_file_size(self.size)}), created: {format_datetime(self.created_at)}, '
            f'expires: {format_datetime(self.expires)} ({"stale" if self.is_expired else "fresh"})'
        )

    def __repr__(self):
        repr_attrs = set(RESPONSE_ATTRS + CACHE_ATTRS) - {'_content', 'elapsed'}
        attr_strs = [f'{k}={getattr(self, k)}' for k in repr_attrs]
        return f'<{self.__class__.__name__}({", ".join(attr_strs)})>'


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

    def read(self, amt=None, decode_content=None, **kwargs):
        """Simplified reader for cached content that emulates
        :py:meth:`urllib3.response.HTTPResponse.read()`
        """
        if 'content-encoding' in self.headers and decode_content is False:
            logger.warning('read() returns decoded data, even with decode_content=False')

        data = self._fp.read(amt)
        # "close" the file to inform consumers to stop reading from it
        if not data:
            self._fp.close()
        return data

    def stream(self, amt=None, **kwargs):
        """Simplified generator over cached content that emulates
        :py:meth:`urllib3.response.HTTPResponse.stream()`
        """
        while not self._fp.closed:
            yield self.read(amt=amt, **kwargs)


AnyResponse = Union[Response, CachedResponse]


def format_datetime(value: Optional[datetime]) -> str:
    """Get a formatted datetime string in the local time zone"""
    if not value:
        return "N/A"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime(DATETIME_FORMAT)


def format_file_size(n_bytes: int) -> str:
    """Convert a file size in bytes into a human-readable format"""
    filesize = float(n_bytes or 0)

    def _format(unit):
        return f'{int(filesize)} {unit}' if unit == 'bytes' else f'{filesize:.2f} {unit}'

    for unit in ['bytes', 'KiB', 'MiB', 'GiB']:
        if filesize < 1024 or unit == 'GiB':
            return _format(unit)
        filesize /= 1024


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
