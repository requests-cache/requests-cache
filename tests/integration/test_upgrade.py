from shutil import copyfile

import pytest

from requests_cache import CachedSession
from tests.conftest import HTTPBIN_FORMATS, SAMPLE_CACHE_FILES, httpbin


@pytest.mark.parametrize('db_path', SAMPLE_CACHE_FILES)
def test_version_upgrade(db_path, tempfile_path):
    """Load SQLite cache files created with older versions of requests-cache.
    Expected behavior: either
    1. Serialization format is incompatible, and previous cache items have been invalidated, or
    2. Serialization format is compatible, and previous cache items are valid

    The previously cached responses should be either replaced or retrieved without any errors.
    """
    copyfile(db_path, tempfile_path)
    session = CachedSession(tempfile_path)

    for response_format in HTTPBIN_FORMATS:
        session.get(httpbin(response_format)).from_cache
        assert session.get(httpbin(response_format)).from_cache is True
