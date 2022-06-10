import json
from typing import Dict

from requests.exceptions import JSONDecodeError

from requests_cache.models.response import CachedResponse
from requests_cache.serializers.cattrs import CattrStage


class DecodeBodyStage(CattrStage):
    """Converter that decodes the response body into a human-readable format when serializing
    (if possible), and re-encodes it to reconstruct the original response. Supported Content-Types
    are ``application/json`` and ``text/*``. All other types will be saved as-is.

    This needs access to the CachedResponse object for decoding, so this is used _instead_ of
    CattrStage, not before/after it.
    """

    def dumps(self, value: CachedResponse) -> Dict:
        response_dict = super().dumps(value)
        # Decode body as JSON
        if value.headers.get('Content-Type') == 'application/json':
            try:
                response_dict['content'] = value.json()
                response_dict.pop('_content', None)
            except JSONDecodeError:
                pass

        # Decode body as text
        if value.headers.get('Content-Type', '').startswith('text/'):
            response_dict['content'] = value.text
            response_dict.pop('_content', None)

        # Otherwise, it is most likely a binary body
        return response_dict

    def loads(self, value: Dict) -> CachedResponse:
        if value.get('content'):
            value['_content'] = value.pop('content')
        value.setdefault('_content', None)

        # Re-encode JSON and text bodies
        if isinstance(value['_content'], dict):
            value['_content'] = json.dumps(value['_content'])
        if isinstance(value['_content'], str):
            value['_content'] = value['_content'].encode('utf-8')
            response = super().loads(value)
            # Since we know the encoding, set that explicitly so requests doesn't have to guess it
            response.encoding = 'utf-8'
            return response
        else:
            return super().loads(value)
