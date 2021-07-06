# flake8: noqa: F401
from typing import Union

from requests import PreparedRequest, Response

from .raw_response import CachedHTTPResponse
from .request import CachedRequest
from .response import CachedResponse, set_response_defaults

AnyResponse = Union[Response, CachedResponse]
AnyRequest = Union[PreparedRequest, CachedRequest]
