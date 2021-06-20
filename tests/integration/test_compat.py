import pytest
from shutil import copyfile

from requests_cache import CachedSession
from tests.conftest import HTTPBIN_FORMATS, SAMPLE_CACHE_FILES


@pytest.mark.parametrize('db_path', SAMPLE_CACHE_FILES)
def test_version_upgrade(db_path, tempfile_path):
    """Load SQLite cache files created with older versions of requests-cache.
    Expected behavior: either
    1. Serialization format is incompatible, and all cache items have been invalidated, or
    2. Serialization format is compatible, and all cache items are valid

    The previously cached responses should be either replaced or retrieved without any errors.
    """
    copyfile(db_path, tempfile_path)
    session = CachedSession(tempfile_path)

    if list(session.cache.urls) == []:
        for response_format in HTTPBIN_FORMATS:
            assert session.get(f'https://httpbin.org/{response_format}').from_cache is False
            assert session.get(f'https://httpbin.org/{response_format}').from_cache is True
    else:
        assert len(list(session.cache.urls)) == len(HTTPBIN_FORMATS)
        for response_format in HTTPBIN_FORMATS:
            assert session.get(f'https://httpbin.org/{response_format}').from_cache is True
