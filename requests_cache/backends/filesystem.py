#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.filesystem
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``filesystem`` cache backend
"""
from .base import BaseCache
from .storage.filesystemdict import FilesystemDict


class FilesystemCache(BaseCache):
    """ ``filesystem`` cache backend.
    """
    def __init__(self, name, **options):
        super(FilesystemCache, self).__init__(**options)

        fs_class = FilesystemDict(
            options.get('cache_dir', '/tmp/{0}'.format(name)),
            options.get('mode', 0600),
            options.get('threshold', 500))

        self.responses = fs_class
        self.keys_map = fs_class
