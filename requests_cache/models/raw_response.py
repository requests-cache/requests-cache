from io import BytesIO
from logging import getLogger

from attr import define, field, fields_dict
from requests import Response
from urllib3.response import HTTPHeaderDict, HTTPResponse, is_fp_closed

logger = getLogger(__name__)


@define(auto_attribs=False, slots=False)
class CachedHTTPResponse(HTTPResponse):
    """A serializable dataclass that extends/emulates :py:class:`~urllib3.response.HTTPResponse`.
    Supports streaming requests and generator usage.

    The only action this doesn't support is explicitly calling :py:meth:`.read` with
    ``decode_content=False``, but a use case for this has not come up yet.
    """

    decode_content: bool = field(default=None)
    headers: HTTPHeaderDict = field(factory=dict)
    reason: str = field(default=None)
    request_url: str = field(default=None)
    status: int = field(default=0)
    strict: int = field(default=0)
    version: int = field(default=0)

    def __init__(self, *args, body: bytes = None, **kwargs):
        """First initialize via HTTPResponse, then via attrs"""
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        super().__init__(body=BytesIO(body or b''), preload_content=False, **kwargs)
        self._body = body
        self.__attrs_init__(*args, **kwargs)

    @classmethod
    def from_response(cls, original_response: Response):
        """Create a CachedHTTPResponse based on an original response"""
        # Copy basic attributes
        raw = original_response.raw
        kwargs = {k: getattr(raw, k, None) for k in fields_dict(cls).keys()}

        # Note: _request_url is not available in urllib <=1.21
        kwargs['request_url'] = getattr(raw, '_request_url', None)

        # Copy response data and restore response object to its original state
        if hasattr(raw, '_fp') and not is_fp_closed(raw._fp):
            body = raw.read(decode_content=False)
            kwargs['body'] = body
            raw._fp = BytesIO(body)
            original_response.content  # This property reads, decodes, and stores response content

            # After reading, reset file pointer on original raw response
            raw._fp = BytesIO(body)
            raw._fp_bytes_read = 0
            raw.length_remaining = len(body)

        return cls(**kwargs)

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

    def reset(self, body: bytes = None):
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
