# flake8: noqa: E402,F401
from logging import getLogger
from os import getenv

__version__ = '0.6.4'

try:
    from .response import AnyResponse, CachedHTTPResponse, CachedResponse, ExpirationTime
    from .session import ALL_METHODS, CachedSession, CacheMixin
    from .patcher import (
        clear,
        disabled,
        enabled,
        get_cache,
        install_cache,
        is_installed,
        remove_expired_responses,
        uninstall_cache,
    )
# Quietly ignore ImportError, if setup.py is invoked outside a virtualenv
except ImportError:
    pass


def get_prerelease_version(version: str) -> str:
    """If we're running in a GitHub Action job on the dev branch, get a prerelease semantic version
    using the current build number. For example: ``1.0.0 -> 1.0.0-dev.123``
    """
    if getenv('GITHUB_REF') == 'refs/heads/dev':
        build_number = getenv('GITHUB_RUN_NUMBER', '0')
        version = f'{version}.dev{build_number}'
        getLogger(__name__).info(f'Using pre-release version: {version}')
    return version


# This won't modify the version outside of a GitHub Action
__version__ = get_prerelease_version(__version__)
