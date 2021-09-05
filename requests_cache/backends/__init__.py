"""Classes and functions for cache persistence. See :ref:`backends` for general usage info."""
# flake8: noqa: F401
from inspect import signature
from logging import getLogger
from typing import Callable, Dict, Iterable, Type, Union

from .. import get_placeholder_class, get_valid_kwargs
from .base import BaseCache, BaseStorage

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
    from .redis import RedisCache, RedisDict
except ImportError as e:
    RedisCache = RedisDict = get_placeholder_class(e)  # type: ignore
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
DbPickeDict = SQLitePickleDict

BACKEND_CLASSES = {
    'dynamodb': DynamoDbCache,
    'filesystem': FileCache,
    'gridfs': GridFSCache,
    'memory': BaseCache,
    'mongodb': MongoCache,
    'redis': RedisCache,
    'sqlite': SQLiteCache,
}


def init_backend(backend: BackendSpecifier = None, *args, **kwargs) -> BaseCache:
    """Initialize a backend from a name, class, or instance"""
    logger.debug(f'Initializing backend: {backend}')

    # Omit 'cache_name' positional arg if an equivalent backend-specific kwarg is specified
    # TODO: The difference in parameter names here can be problematic. A better solution for this
    #       would be nice, if it can be done without breaking backwards-compatibility.
    if any([k in kwargs for k in CACHE_NAME_KWARGS]):
        args = tuple()

    # Determine backend class
    if isinstance(backend, BaseCache):
        return backend
    elif isinstance(backend, type):
        return backend(*args, **kwargs)
    elif not backend:
        backend = 'sqlite' if BACKEND_CLASSES['sqlite'] else 'memory'

    backend = str(backend).lower()
    if backend not in BACKEND_CLASSES:
        raise ValueError(f'Invalid backend: {backend}. Choose from: {BACKEND_CLASSES.keys()}')

    return BACKEND_CLASSES[backend](*args, **kwargs)
