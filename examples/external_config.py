#!/usr/bin/env python
"""
An example of loading CachedSession settings from an external config file.

Limitations:
* Does not include backend or serializer settings
* Does not include settings specified as python expressions, for example `timedelta` objects or
  callback functions
"""
from pathlib import Path

import yaml

from requests_cache import CachedSession, CacheSettings

CONFIG_FILE = Path(__file__).parent / 'external_config.yml'


def load_settings() -> CacheSettings:
    """Load settings from a YAML config file"""
    with open(CONFIG_FILE) as f:
        settings = yaml.safe_load(f)
    return CacheSettings(**settings['cache_settings'])


if __name__ == '__main__':
    session = CachedSession()
    session.settings = load_settings()
    print('Loaded settings:\n', session.settings)
