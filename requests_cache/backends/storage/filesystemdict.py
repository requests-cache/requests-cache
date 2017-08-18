#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.filesystemdict
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Dictionary-like objects for saving large data sets to ``filesystem``
"""
import os
import errno
import datetime

from collections import MutableMapping
try:
    import cPickle as pickle
except ImportError:
    import pickle


class FilesystemDict(MutableMapping):
    """A cache that stores the items on the file system.  This cache depends
    on being the only user of the `cache_dir`.
    :param cache_dir: the directory where cache files are stored.
    :param mode: the file mode wanted for the cache files, default 0600
    :param threshold: the maximum number of items the cache stores before
                      it starts deleting some.
    """

    def __init__(self, cache_dir, mode, threshold):
        self.cache_dir = cache_dir
        self.mode = mode
        self.threshold = threshold

        try:
            os.makedirs(self.cache_dir)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise


    def __getitem__(self, key):
        file_path = "{0}/{1}".format(self.cache_dir, key)
        try:
            return pickle.load(open(file_path, 'rb'))
        except (IOError, OSError, pickle.PickleError):
            raise KeyError


    def __setitem__(self, key, item):
        self._prune()
        file_path = "{0}/{1}".format(self.cache_dir, key)
        with open(file_path, 'wb') as file:
            pickle.dump(item, file, pickle.HIGHEST_PROTOCOL)
        os.chmod(file_path, self.mode)


    def __delitem__(self, key):
        try:
            file_path = "{0}/{1}".format(self.cache_dir, key)
            os.remove(file_path)
        except (IOError, OSError):
            raise KeyError


    def __len__(self):
        return len(self._list_dir())


    def __iter__(self):
        for file_path in self._list_dir:
            yield file_path


    def clear(self):
        for file in self._list_dir():
            os.remove(file)


    def _list_dir(self):
        """return a list of (fully qualified) cache filenames"""
        return [os.path.join(self.cache_dir, fn)
                for fn in os.listdir(self.cache_dir)]


    def _prune(self):
        entries = self._list_dir()
        if len(entries) > self.threshold:
            now = datetime.datetime.now()
            for idx, fname in enumerate(entries):
                print idx, fname
                try:
                    remove = False
                    with open(fname, 'rb') as f:
                        #(<requests_cache.backends.base._Store>, <datetime>))
                        _, expires = pickle.load(f)
                    remove = (expires != 0 and expires <= now) or idx % 3 == 0

                    if remove:
                        os.remove(fname)
                except (IOError, OSError):
                    pass
