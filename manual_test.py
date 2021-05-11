import logging
import pickle

import requests
from cattr import structure, unstructure

from requests_cache import CachedSession
from requests_cache.models import CachedHTTPResponse, CachedRequest, CachedResponse
from requests_cache.serializers import BaseSerializer, PickleSerializer, SafePickleSerializer

# from requests_cache.serializers.json_serializer import *

logging.basicConfig(level='INFO')
logging.getLogger('requests_cache').setLevel('DEBUG')

session = CachedSession('manual_test')
session.cache.clear()

s = BaseSerializer()
# js = ResponseJSONSerializer()

r = session.get('https://httpbin.org/get')
r = session.get('https://httpbin.org/get')

r2 = requests.get('https://httpbin.org/bytes/1024')
req = CachedRequest.from_request(r2.request)

r_dict = s.unstructure(r)
r_again = s.structure(r_dict)
print(r_dict)
print(r_again)
