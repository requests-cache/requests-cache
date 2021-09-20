"""Data models used to serialize response data"""
# flake8: noqa: F401
from typing import Union

from requests import PreparedRequest, Request, Response

from .raw_response import CachedHTTPResponse
from .request import CachedRequest
from .response import CachedResponse, set_response_defaults

AnyResponse = Union[Response, CachedResponse]
AnyRequest = Union[Request, PreparedRequest, CachedRequest]
AnyPreparedRequest = Union[PreparedRequest, CachedRequest]
