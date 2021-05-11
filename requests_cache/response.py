# TODO: Maybe split this into separate modules
"""Classes to wrap cached response objects"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from logging import getLogger
from typing import Dict, List, Optional, Tuple, Union

import attr
import cattr
from requests import PreparedRequest, Response
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPResponse, is_fp_closed

from .cache_control import get_expiration_datetime

logger = getLogger(__name__)

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S %Z'  # Format used for __str__ only
DO_NOT_CACHE = 0

ExpirationTime = Union[None, int, float, datetime, timedelta]
HeaderList = List[Tuple[str, str]]

# Aliases for the most common attr options
dataclass = attr.s(
    auto_attribs=False,
    auto_detect=True,
    collect_by_mro=True,
    kw_only=True,
    slots=True,
    weakref_slot=False,
)
public_attr = attr.ib(default=None)
bytes_attr = attr.ib(default=b'', repr=False, converter=lambda x: x or b'')


@dataclass
class CachedHTTPResponse(HTTPResponse):
    """A serializable dataclass that emulates :py:class:`~urllib3.response.HTTPResponse`.
    Supports streaming requests and generator usage.

    The only action this doesn't support is explicitly calling :py:meth:`.read` with
    ``decode_content=False``, but a use case for this has not come up yet.
    """

    decode_content: bool = public_attr
    headers: CaseInsensitiveDict = attr.ib(factory=dict)
    reason: str = public_attr
    request_url: str = public_attr
    status: int = public_attr
    strict: int = public_attr
    version: int = public_attr

    def __attrs_post_init__(self, body: bytes = None, **kwargs):
        kwargs.setdefault('preload_content', False)
        super().__init__(body=BytesIO(body or b''), **kwargs)
        self._body = body

    @classmethod
    def from_response(cls, original_response: Response):
        """Create a CachedHTTPResponse based on an original response object's raw response"""
        # Copy basic attributes
        raw = original_response.raw
        kwargs = {k: getattr(raw, k, None) for k in attr.fields_dict(cls).keys()}
        # TODO: Better means of handling naming differences between class attrs and method kwargs
        kwargs['request_url'] = raw._request_url

        # Copy response data and restore response object to its original state
        if not is_fp_closed(getattr(original_response.raw, '_fp', None)):
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

    def reset(self):
        """Reset raw response file pointer"""
        self._fp = BytesIO(self._body)

    def stream(self, amt=None, **kwargs):
        """Simplified generator over cached content that emulates
        :py:meth:`urllib3.response.HTTPResponse.stream()`
        """
        while not self._fp.closed:
            yield self.read(amt=amt, **kwargs)


@dataclass
class CachedRequest:
    """A serializable dataclass that emulates :py:class:`requests.PreparedResponse`"""

    body: bytes = bytes_attr
    cookies: RequestsCookieJar = public_attr
    headers: CaseInsensitiveDict = attr.ib(factory=CaseInsensitiveDict)
    method: str = public_attr
    url: str = public_attr

    @classmethod
    def from_request(cls, original_request: PreparedRequest):
        """Create a CachedRequest based on an original request object"""
        kwargs = {k: getattr(original_request, k, None) for k in attr.fields_dict(cls).keys()}
        # TODO: Better means of handling naming differences between class attrs and method kwargs
        kwargs['cookies'] = original_request._cookies
        return cls(**kwargs)

    # TODO: Is this necessary, or will cattr.structure() be sufficient?
    @classmethod
    def prepare(self, obj) -> PreparedRequest:
        """Turn a CachedRequest object back into a PreparedRequest. This lets PreparedRequest do the
        work of normalizing any values that may have changed during (de)serialization.
        """
        req = PreparedRequest()
        kwargs = attr.asdict(obj)
        # TODO: Better means of handling naming differences between class attrs and method kwargs
        kwargs['_cookies'] = kwargs.pop('cookies')
        kwargs['body'] = kwargs.pop('data')
        req.prepare(**kwargs)
        return req

    @property
    def _cookies(self):
        return self.cookies


# TODO: Make this fully take advantage of slots
# Make a slotted copy of Response to subclass; we don't need its attrs, only its methods

# from requests import Response as OriginalResponse
# Response = attr.s(slots=True)(OriginalResponse)
# @attr.s(kw_only=True, slots=True)
@dataclass
class CachedResponse(Response):
    """A serializable dataclass that emulates :py:class:`requests.Response`. Public attributes and
    methods on CachedResponse objects will behave the same as those from the original response, but
    with different internals optimized for serialization.

    This means doing some pre- and post-initialization steps common to all serializers, such as
    breaking nested objects down into their basic attributes and lazily re-initializing them, which
    saves a bit of memory and deserialization steps when those objects aren't accessed.
    """

    _content: bytes = bytes_attr
    url: str = public_attr
    status_code: int = public_attr
    cookies: RequestsCookieJar = public_attr
    created_at: datetime = attr.ib(factory=datetime.utcnow)
    elapsed: timedelta = attr.ib(factory=timedelta)
    expires: datetime = public_attr
    encoding: str = public_attr
    headers: CaseInsensitiveDict = attr.ib(factory=dict)
    history: List = attr.ib(factory=list)
    reason: str = public_attr
    request: CachedRequest = public_attr
    raw: CachedHTTPResponse = attr.ib(default=None, repr=False)

    @classmethod
    def from_response(cls, original_response: Response, **kwargs):
        """Create a CachedResponse based on an original response object"""
        obj = cls(**kwargs)

        # Copy basic attributes
        for k in Response.__attrs__:
            setattr(obj, k, getattr(original_response, k, None))

        # Store request and raw response
        obj.request = CachedRequest.from_request(original_response.request)
        obj.raw = CachedHTTPResponse.from_response(original_response)

        # Store response body, which will have been read & decoded by requests.Response by now
        obj._content = original_response.content

        # Copy redirect history, if any; avoid recursion by not copying redirects of redirects
        obj.history = []
        if not obj.is_redirect:
            for redirect in original_response.history:
                obj.history.append(cls.from_response(redirect))

        return obj

    @property
    def from_cache(self) -> bool:
        return True

    @property
    def is_expired(self) -> bool:
        """Determine if this cached response is expired"""
        return self.expires is not None and datetime.utcnow() >= self.expires

    def revalidate(self, expire_after: ExpirationTime) -> bool:
        """Set a new expiration for this response, and determine if it is now expired"""
        self.expires = get_expiration_datetime(expire_after)
        return self.is_expired

    def reset(self):
        if self.raw:
            self.raw.reset()

    @property
    def size(self) -> int:
        """Get the size of the response body in bytes"""
        return len(self.content) if self.content else 0

    # TODO: Behavior will be different for slotted classes
    # def __getstate__(self):
    #     """Override pickling behavior in ``requests.Response.__getstate__``"""
    #     return self.__dict__

    def __str__(self):
        return (
            f'request: {self.request.method} {self.request.url}, response: {self.status_code} '
            f'({format_file_size(self.size)}), created: {format_datetime(self.created_at)}, '
            f'expires: {format_datetime(self.expires)} ({"stale" if self.is_expired else "fresh"})'
        )


# TODO: Should this go in a base serializer class instead?
def get_converter():
    """Make a converter to structure and unstructure some of the nested objects within a response"""
    converter = cattr.Converter()

    # Convert datetimes to and from iso-formatted strings
    converter.register_unstructure_hook(datetime, lambda obj: obj.isoformat() if obj else None)
    converter.register_structure_hook(
        datetime, lambda obj, cls: datetime.fromisoformat(obj) if obj else None
    )

    # Convert timedeltas to and from float values in seconds
    converter.register_unstructure_hook(timedelta, lambda obj: obj.total_seconds() if obj else None)
    converter.register_structure_hook(
        timedelta, lambda obj, cls: timedelta(seconds=obj) if obj else None
    )

    # Convert dict-like objects to and from plain dicts
    converter.register_unstructure_hook(RequestsCookieJar, lambda obj: dict(obj.items()))
    converter.register_structure_hook(RequestsCookieJar, lambda obj, cls: cookiejar_from_dict(obj))
    converter.register_unstructure_hook(CaseInsensitiveDict, dict)
    converter.register_structure_hook(CaseInsensitiveDict, lambda obj, cls: CaseInsensitiveDict(obj))

    # Not sure yet if this will be needed
    # converter.register_unstructure_hook(PreparedRequest, CachedRequest.from_request)
    # converter.register_structure_hook(PreparedRequest, CachedRequest.prepare)
    # converter.register_unstructure_hook(HTTPResponse, lambda obj, cls: CachedHTTPResponse.from_response(obj))
    # converter.register_structure_hook(HTTPResponse, lambda obj, cls: CachedHTTPResponse(obj))

    return converter


AnyResponse = Union[Response, CachedResponse]
ResponseConverter = get_converter()


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
