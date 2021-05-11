from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Dict

import cattr
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict

from ..models import CachedResponse


class BaseSerializer:
    """Base serializer class for :py:class:`.CachedResponse` that does pre/post-processing with cattrs.
    This does the majority of the work to break objects down into builtin types and reassemble them
    without data loss. Subclasses just need to provide ``dumps`` and ``loads`` methods.
    """

    is_binary = True  # TODO: This may or may not be needed to determine return type in backends

    def __init__(self, *args, **kwargs):
        """Make a converter to structure and unstructure some of the nested objects within a response"""
        super().__init__(*args, **kwargs)
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
        # converter.register_structure_hook(PreparedRequest, lambda obj, cls: CachedRequest.prepare(obj))
        # converter.register_unstructure_hook(HTTPResponse, lambda obj, cls: CachedHTTPResponse.from_response(obj))
        # converter.register_structure_hook(HTTPResponse, lambda obj, cls: CachedHTTPResponse(obj))
        # converter.register_structure_hook(CachedRequest, lambda obj, cls: cls.prepare(obj))

        self.converter = converter

    def unstructure(self, response: CachedResponse) -> Dict:
        return self.converter.unstructure(response)

    def structure(self, obj: Dict) -> CachedResponse:
        return self.converter.structure(obj, CachedResponse)

    @abstractmethod
    def dumps(self, response: CachedResponse):
        pass

    @abstractmethod
    def loads(self, obj) -> CachedResponse:
        pass
