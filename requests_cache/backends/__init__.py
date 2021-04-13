"""Classes and functions for cache persistence"""
# flake8: noqa: F401
from logging import getLogger
from typing import Type, Union

from .base import BaseCache, BaseStorage

# Backend-specific keyword arguments equivalent to 'cache_name'
CACHE_NAME_KWARGS = ['db_path', 'db_name', 'namespace', 'table_name']

# All backend-specific keyword arguments
BACKEND_KWARGS = CACHE_NAME_KWARGS + [
    'connection',
    'endpoint_url',
    'fast_save',
    'ignored_parameters',
    'include_get_headers',
    'name',
    'read_capacity_units',
    'region_name',
    'salt',
    'secret_key',
    'suppress_warnings',
    'write_capacity_units',
]

BackendSpecifier = Union[str, BaseCache, Type[BaseCache], None]
logger = getLogger(__name__)


def get_placeholder_backend(original_exception: Exception = None) -> Type[BaseCache]:
    """Create a placeholder type for a backend class that does not have dependencies installed.
    This allows delaying ImportErrors until init time, rather than at import time.
    """

    class PlaceholderBackend(BaseCache):
        def __init__(*args, **kwargs):
            msg = 'Dependencies are not installed for this backend'
            logger.error(msg)
            raise original_exception or ImportError(msg)

    return PlaceholderBackend


# Import all backend classes for which dependencies are installed
try:
    from .dynamodb import DynamoDbCache, DynamoDbDict
except ImportError as e:
    DynamoDbCache = DynamoDbDict = get_placeholder_backend(e)  # type: ignore
try:
    from .gridfs import GridFSCache, GridFSPickleDict
except ImportError as e:
    GridFSCache = GridFSPickleDict = get_placeholder_backend(e)  # type: ignore
try:
    from .mongo import MongoCache, MongoDict, MongoPickleDict
except ImportError as e:
    MongoCache = MongoDict = MongoPickleDict = get_placeholder_backend(e)  # type: ignore
try:
    from .redis import RedisCache, RedisDict
except ImportError as e:
    RedisCache = RedisDict = get_placeholder_backend(e)  # type: ignore
try:
    # Note: Heroku doesn't support SQLite due to ephemeral storage
    from .sqlite import DbCache, DbDict, DbPickleDict
except ImportError as e:
    DbCache = DbDict = DbPickleDict = get_placeholder_backend(e)  # type: ignore


BACKEND_CLASSES = {
    'dynamodb': DynamoDbCache,
    'gridfs': GridFSCache,
    'memory': BaseCache,
    'mongo': MongoCache,
    'redis': RedisCache,
    'sqlite': DbCache,
}


def init_backend(backend: BackendSpecifier, *args, **kwargs) -> BaseCache:
    """Initialize a backend given a name, class, or instance"""
    logger.debug(f'Initializing backend: {backend}')

    # Omit 'cache_name' positional arg if an equivalent backend-specific kwarg is specified
    if any([k in kwargs for k in CACHE_NAME_KWARGS]):
        args = tuple()

    # Determine backend class
    if isinstance(backend, BaseCache):
        return backend
    elif isinstance(backend, type):
        return backend(*args, **kwargs)
    elif not backend:
        backend = 'sqlite' if BACKEND_CLASSES['sqlite'] else 'memory'

    backend = str(backend).lower().replace('mongodb', 'mongo')
    if backend not in BACKEND_CLASSES:
        raise ValueError(f'Invalid backend: {backend}. Choose from: {BACKEND_CLASSES.keys()}')

    return BACKEND_CLASSES[backend](*args, **kwargs)
