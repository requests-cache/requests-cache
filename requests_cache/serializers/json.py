# TODO: Handle CachedHTTPResponse, PreparedRequest, RequestsCookieJar, CachedResponse (history)
import json
from base64 import b64decode, b64encode
from datetime import datetime, timedelta
from json import JSONDecoder, JSONEncoder
from typing import Union

from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict

from ..response import CachedResponse


class ResponseJSONSerializer:
    def dumps(self, response: CachedResponse) -> str:
        """Serialize a CachedResponse into JSON"""
        return json.dumps(response.to_dict(), cls=ResponseJSONEncoder, indent=2)

    def loads(self, obj: str) -> CachedResponse:
        """Deserialize a CachedResponse from JSON"""
        response = json.loads(obj, cls=ResponseJSONDecoder)

        response['_content'] = b64decode(response['_content'].encode())
        response['_raw_response_attrs'] = response.pop('raw')
        response['_request_attrs'] = response.pop('request')
        response['cookies'] = cookiejar_from_dict(response.get('cookies', {}))
        response['headers'] = CaseInsensitiveDict(response.get('headers', {}))
        response['history'] = [self.loads(redirect) for redirect in response.get('history', [])]

        return CachedResponse(**response)


class ResponseJSONEncoder(JSONEncoder):
    """Serialize a CachedResponse as JSON"""

    def default(self, obj):
        if isinstance(obj, bytes):
            return b64encode(obj).decode()
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, RequestsCookieJar):
            return dict(obj)
        # elif isinstance(obj, CookieJar):
        #     cookies = RequestsCookieJar()
        #     cookies.update(obj)
        #     return dict(cookies)
        elif isinstance(obj, timedelta):
            return {
                '__type__': 'timedelta',
                'days': obj.days,
                'seconds': obj.seconds,
                'microseconds': obj.microseconds,
            }
        return super().default(obj)


class ResponseJSONDecoder(JSONDecoder):
    """Deserialize a CachedResponse from JSON"""

    def __init__(self, **kwargs):
        super().__init__(object_hook=self.object_hook, **kwargs)

    def object_hook(self, obj):
        """Check for and handle custom types before they get deserialized by JSONDecoder"""
        if isinstance(obj, str):
            return try_parse_isoformat(obj)
        elif isinstance(obj, dict) and obj.get('__type__', None) == 'timedelta':
            obj.pop('__type__')
            return timedelta(**obj)
        return obj


def try_parse_isoformat(obj: str) -> Union[datetime, str]:
    """Attempt to parse an ISO-formatted datetime string; if it fails, just return the string"""
    try:
        return datetime.fromisoformat(obj)
    except (AttributeError, TypeError, ValueError):
        return obj
