#!/usr/bin/env python3
# flake8: noqa: E402
"""Generate a SQLite cache with some content for testing behavior during version upgrades"""

import sys
from importlib.metadata import version as pkg_version
from os.path import abspath, join

sys.path.insert(0, abspath('.'))

from requests_cache import CachedSession
from tests.conftest import HTTPBIN_FORMATS, SAMPLE_DATA_DIR

DB_PATH = join(SAMPLE_DATA_DIR, f'sample.db.{pkg_version("requests_cache")}')


def make_sample_db():
    session = CachedSession(DB_PATH)

    for format in HTTPBIN_FORMATS:
        session.get(f'https://httpbin.org/{format}')
    print(session.cache.urls())


if __name__ == '__main__':
    make_sample_db()
