#!/usr/bin/env/python
"""
    requests_cache.per_request
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    The :mod:`per_request` module allows caching on a per request basis.

    .. seealso::

        Refer to the :ref:`Usage guide <request_caching>` for more information.
"""

from datetime import datetime, timedelta

from .core import CachedSession


class RequestRegistry(dict):
    """A dictionary to store cache times."""

    def __setitem__(self, key, value):
        """Sets the value of the dictionary.

        ``None``, ``'default'`` and :class:`~datetime.timedelta`
        values are simply set, other values are assumed to be seconds and are
        used to create a :class:`~datetime.timedelta` instance to store.

        If a value was set for that key before and it changed, the key
        is added to :attr:`PerRequestCachedSession.changed_for`.

        While this should be used with request cache_keys as created by the
        :class:`~.core.CachedSession`, the :class:`PerRequestCachedSession`
        takes care of converting requests to cache_keys.

        :param key: The cache_key to cache.
        :type key: str
        :param value: The expiration: ``None`` for never, ``'default'`` to inherit the
                      cache's default, a float in seconds or
                      :class:`~datetime.timedelta` to set an expiry time.
                      Negative values (e.g., ``-1``) essentially disable caching.
        :type value: Union[None, str, float, datetime.timedelta]
        """
        if value is not None and value != 'default' and not isinstance(value, timedelta):
            value = timedelta(seconds=value)

        try:
            old_value = super().__getitem__(key)
        except KeyError:
            old_value = None

        if old_value != value:
            PerRequestCachedSession.changed_for.add(key)

        super().__setitem__(key, value)


class PerRequestCachedSession(CachedSession):
    """A Session to be used a custom session factory.

    It uses the RequestRegistry stored in registry to determine
    if a url has a custom cache time or uses the cache's default time.
    """

    registry = RequestRegistry()
    changed_for = set()

    def send(self, request, **kwargs):
        """Performs the super()'s send method with the same arguments, but
        adjusts the :attr:`_cache_expire_after` times before the call (and resets it
        after).

        This method checks the :attr:`registry` (an instance of :class:`RequestRegistry`)
        for the request cache_key and retrieves the associated time.

        :kwarg kwargs: Arguments to be passed to :meth:`requests_cache.core.CachedSession.send` method.
        """
        cache_key = self.cache.create_key(request)

        # Register by requests keyword
        if self.expire_after != 'default':
            PerRequestCachedSession.registry[cache_key] = self.expire_after

        expire_after = PerRequestCachedSession.registry.get(cache_key, 'default')

        # Clear from cache on change
        if cache_key in PerRequestCachedSession.changed_for:
            self.cache.delete(cache_key)
            PerRequestCachedSession.registry[cache_key] = expire_after
            try:
                PerRequestCachedSession.changed_for.remove(cache_key)
            except KeyError:
                pass

        if expire_after == 'default':
            return super().send(request, **kwargs)

        old, self._cache_expire_after = self._cache_expire_after, expire_after
        try:
            return super().send(request, **kwargs)
        finally:
            self._cache_expire_after = old

    def request(self, method, url, **kwargs):
        """Adds an additional keyword argument to :func:`requests.request`: ``expire_after``.

        This keyword is used to set the expiry time for that request, and can
        be omitted on subsequent calls. Subsequent calls with different
        times invalidate the cache, calls with the same time don't.

        If the string ``'default'`` is used, the default expiry from the
        installed cache is used.

        .. seealso::

            Possible values are explained in :func:`RequestRegistry.__setitem__`.
        """
        try:
            self.expire_after = kwargs.pop('expire_after', 'default')
        except KeyError:
            self.expire_after = 'default'
        try:
            return super().request(method, url, **kwargs)
        finally:
            self.expire_after = 'default'

    def remove_expired_responses(self):
        """Removes expired responses, taking into account individual request
        expiry times."""
        now = datetime.utcnow()

        keys_to_delete = set()
        for key in self.cache.responses:

            # get cache entry or continue
            try:
                response, created = self.cache.responses[key]
            except KeyError:
                continue

            # delete by custom expiry and continue
            try:
                expiry = PerRequestCachedSession.registry[key]
                if now - expiry > created:
                    keys_to_delete.add(key)
                continue
            except KeyError:
                pass

            # delete by default expiry, if it's not None
            if self._cache_expire_after and now - self._cache_expire_after > created:
                keys_to_delete.add(key)

        for key in keys_to_delete:
            self.cache.delete(key)
