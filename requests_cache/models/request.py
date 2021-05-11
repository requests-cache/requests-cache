"""Classes to wrap cached response objects"""
from logging import getLogger
from typing import Any

import attr
from requests import PreparedRequest
from requests.cookies import RequestsCookieJar
from requests.structures import CaseInsensitiveDict

from . import dataclass

logger = getLogger(__name__)


@dataclass
class CachedRequest:
    """A serializable dataclass that emulates :py:class:`requests.PreparedResponse`"""

    body: Any = attr.ib(default=None)
    cookies: RequestsCookieJar = attr.ib(factory=dict)
    headers: CaseInsensitiveDict = attr.ib(factory=CaseInsensitiveDict)
    method: str = attr.ib(default=None)
    url: str = attr.ib(default=None)

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
        kwargs['data'] = kwargs.pop('body')
        req.prepare(**kwargs)
        return req

    @property
    def _cookies(self):
        return self.cookies

    def __str__(self):
        return f'{self.method} {self.url}'
