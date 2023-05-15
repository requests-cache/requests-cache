from io import BytesIO
from logging import getLogger
from typing import TYPE_CHECKING, Optional

from attr import define, field, fields_dict
from requests import Response
from urllib3.response import (  # type: ignore  # import location false positive
    HTTPHeaderDict,
    HTTPResponse,
    is_fp_closed,
)

from . import RichMixin

logger = getLogger(__name__)


if TYPE_CHECKING:
    from . import CachedResponse


@define(auto_attribs=False, repr=False, slots=False)
class CachedHTTPResponse(RichMixin, HTTPResponse):
    """A wrapper class that emulates :py:class:`~urllib3.response.HTTPResponse`.

    This enables consistent behavior for streaming requests and generator usage in the following
    cases:
    * On an original response, after reading its content to write to the cache
    * On a cached response
    """

    decode_content: bool = field(default=None)
    headers: HTTPHeaderDict = field(factory=HTTPHeaderDict)
    reason: str = field(default=None)
    request_url: str = field(default=None)
    status: int = field(default=0)
    version: int = field(default=0)

    def __init__(self, body: Optional[bytes] = None, **kwargs):
        """First initialize via HTTPResponse, then via attrs"""
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        super().__init__(body=BytesIO(body or b''), preload_content=False, **kwargs)
        self._body = body
        self.__attrs_init__(**kwargs)  # type: ignore # False positive in mypy 0.920+?

    @classmethod
    def from_response(cls, response: Response) -> 'CachedHTTPResponse':
        """Create a CachedHTTPResponse based on an original response"""
        # Copy basic attributes
        raw = response.raw
        kwargs = {k: getattr(raw, k, None) for k in fields_dict(cls).keys()}
        kwargs['request_url'] = raw._request_url

        # Read and copy raw response data, and then restore response object to its previous state
        # This is necessary so streaming responses behave consistently with or without the cache
        if getattr(raw, '_fp', None) and not is_fp_closed(raw._fp):
            # Body has already been read & decoded by requests
            if getattr(raw, '_has_decoded_content', False):
                body = response.content
                kwargs['body'] = body
                raw._fp = BytesIO(body)
                raw._fp_bytes_read = 0
                raw.length_remaining = len(body)
            # Body has not yet been read
            else:
                body = raw.read(decode_content=False)
                kwargs['body'] = body
                raw._fp = BytesIO(body)
                _ = response.content  # This property reads, decodes, and stores response content

                # After reading, reset file pointer on original raw response
                raw._fp = BytesIO(body)
                raw._fp_bytes_read = 0
                raw.length_remaining = len(body)

        return cls(**kwargs)  # type: ignore  # False positive in mypy 0.920+?

    @classmethod
    def from_cached_response(cls, response: 'CachedResponse'):
        """Create a CachedHTTPResponse based on a cached response"""
        obj = cls(
            headers=HTTPHeaderDict(response.headers),
            reason=response.reason,
            status=response.status_code,
            request_url=response.request.url,
        )
        obj.reset(response._content)
        return obj

    def release_conn(self):
        """No-op for compatibility"""

    def read(self, amt=None, decode_content=None, **kwargs):
        """Simplified reader for cached content that emulates
        :py:meth:`urllib3.response.HTTPResponse.read()`
        """
        if 'Content-Encoding' in self.headers and decode_content is False:
            logger.warning('read(decode_content=False) is not supported for cached responses')

        data = self._fp.read(amt)
        # "close" the file to inform consumers to stop reading from it
        if not data:
            self._fp.close()
        return data

    def reset(self, body: Optional[bytes] = None):
        """Reset raw response file pointer, and optionally update content"""
        if body is not None:
            self._body = body
        self._fp = BytesIO(self._body or b'')

    def set_content(self, body: bytes):
        self._body = body
        self.reset()

    def stream(self, amt=None, **kwargs):
        """Simplified generator over cached content that emulates
        :py:meth:`urllib3.response.HTTPResponse.stream()`
        """
        while not self._fp.closed:
            yield self.read(amt=amt, **kwargs)
