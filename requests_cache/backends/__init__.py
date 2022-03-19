"""Classes and functions for cache persistence. See :ref:`backends` for general usage info."""
# flake8: noqa: F401
from logging import getLogger
from typing import Callable, Dict, Iterable, Optional, Type, Union

from .._utils import get_placeholder_class, get_valid_kwargs
from ..models.settings import CacheSettings
from .base import BaseCache, BaseStorage, DictStorage

# Backend-specific keyword arguments equivalent to 'cache_name'
CACHE_NAME_KWARGS = ['db_path', 'db_name', 'namespace', 'table_name']

# All backend-specific keyword arguments
BACKEND_KWARGS = CACHE_NAME_KWARGS + [
    'connection',
    'endpoint_url',
    'fast_save',
    'ignored_parameters',
    'match_headers',
    'name',
    'read_capacity_units',
    'region_name',
    'salt',
    'secret_key',
    'write_capacity_units',
]

BackendSpecifier = Union[str, BaseCache, Type[BaseCache]]
logger = getLogger(__name__)


# Import all backend classes for which dependencies are installed
try:
    from .dynamodb import DynamoDbCache, DynamoDbDict
except ImportError as e:
    DynamoDbCache = DynamoDbDict = get_placeholder_class(e)  # type: ignore
try:
    from .gridfs import GridFSCache, GridFSPickleDict
except ImportError as e:
    GridFSCache = GridFSPickleDict = get_placeholder_class(e)  # type: ignore
try:
    from .mongodb import MongoCache, MongoDict, MongoPickleDict
except ImportError as e:
    MongoCache = MongoDict = MongoPickleDict = get_placeholder_class(e)  # type: ignore
try:
    from .redis import RedisCache, RedisDict, RedisHashDict
except ImportError as e:
    RedisCache = RedisDict = RedisHashDict = get_placeholder_class(e)  # type: ignore
try:
    # Note: Heroku doesn't support SQLite due to ephemeral storage
    from .sqlite import SQLiteCache, SQLiteDict, SQLitePickleDict
except ImportError as e:
    SQLiteCache = SQLiteDict = SQLitePickleDict = get_placeholder_class(e)  # type: ignore
try:
    from .filesystem import FileCache, FileDict
except ImportError as e:
    FileCache = FileDict = get_placeholder_class(e)  # type: ignore

# Aliases for backwards-compatibility
DbCache = SQLiteCache
DbDict = SQLiteDict
DbPickleDict = SQLitePickleDict

BACKEND_CLASSES = {
    'dynamodb': DynamoDbCache,
    'filesystem': FileCache,
    'gridfs': GridFSCache,
    'memory': BaseCache,
    'mongodb': MongoCache,
    'redis': RedisCache,
    'sqlite': SQLiteCache,
}


# TODO: Make this less of a mess
# TODO: Backend instance: Handle both settings already on instance, and settings passed via kwargs
def init_backend(
    cache_name: str, backend: Optional[BackendSpecifier], settings: CacheSettings = None, **kwargs
) -> BaseCache:
    """Initialize a backend from a name, class, or instance"""
    logger.debug(f'Initializing backend: {backend} {cache_name}')
    settings = settings or CacheSettings(**kwargs)

    # The 'cache_name' arg has a different purpose depending on the backend. If an equivalent
    # backend-specific keyword arg is specified, handle that here to avoid conflicts. A consistent
    # positional-only or keyword-only arg would be better, but probably not worth a breaking change.
    cache_name_kwargs = [kwargs.pop(k) for k in CACHE_NAME_KWARGS if k in kwargs]
    cache_name = cache_name or cache_name_kwargs[0]

    # Determine backend class
    if isinstance(backend, BaseCache):
        if cache_name:
            backend.cache_name = cache_name
        backend.settings = settings
        return backend
    elif isinstance(backend, type):
        return backend(cache_name, settings=settings, **kwargs)
    elif not backend:
        sqlite_supported = issubclass(BACKEND_CLASSES['sqlite'], BaseCache)
        backend = 'sqlite' if sqlite_supported else 'memory'

    backend = str(backend).lower()
    if backend not in BACKEND_CLASSES:
        raise ValueError(f'Invalid backend: {backend}. Choose from: {BACKEND_CLASSES.keys()}')

    cls = BACKEND_CLASSES[backend]
    return cls(cache_name, settings=settings, **kwargs)
