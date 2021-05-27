"""Classes to wrap cached response objects"""
from logging import getLogger
from typing import Any

from attr import define, field, fields_dict
from requests import PreparedRequest
from requests.cookies import RequestsCookieJar
from requests.structures import CaseInsensitiveDict

logger = getLogger(__name__)


@define(auto_attribs=False)
class CachedRequest:
    """A serializable dataclass that emulates :py:class:`requests.PreparedResponse`"""

    body: Any = field(default=None)
    cookies: RequestsCookieJar = field(factory=dict)
    headers: CaseInsensitiveDict = field(factory=CaseInsensitiveDict)
    method: str = field(default=None)
    url: str = field(default=None)

    @classmethod
    def from_request(cls, original_request: PreparedRequest):
        """Create a CachedRequest based on an original request object"""
        kwargs = {k: getattr(original_request, k, None) for k in fields_dict(cls).keys()}
        kwargs['cookies'] = original_request._cookies
        return cls(**kwargs)

    @property
    def _cookies(self):
        """For compatibility with PreparedRequest, which has an attribute named '_cookies', and a
        keyword argument named 'cookies'.
        """
        return self.cookies

    def __str__(self):
        return f'{self.method} {self.url}'
