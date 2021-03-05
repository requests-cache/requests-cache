# noqa: F401
"""
    requests_cache.backends
    ~~~~~~~~~~~~~~~~~~~~~~~

    Classes and functions for cache persistence
"""


from .base import BACKEND_KWARGS, BaseCache

registry = {
    'memory': BaseCache,
}

_backend_dependencies = {
    'sqlite': 'sqlite3',
    'mongo': 'pymongo',
    'redis': 'redis',
    'dynamodb': 'dynamodb',
}

try:
    # Heroku doesn't allow the SQLite3 module to be installed
    from .sqlite import DbCache

    registry['sqlite'] = DbCache
except ImportError:
    DbCache = None

try:
    from .mongo import MongoCache

    registry['mongo'] = registry['mongodb'] = MongoCache
except ImportError:
    MongoCache = None


try:
    from .gridfs import GridFSCache

    registry['gridfs'] = GridFSCache
except ImportError:
    GridFSCache = None

try:
    from .redis import RedisCache

    registry['redis'] = RedisCache
except ImportError:
    RedisCache = None

try:
    from .dynamodb import DynamoDbCache

    registry['dynamodb'] = DynamoDbCache
except ImportError:
    DynamoDbCache = None


def create_backend(backend_name, cache_name, options):
    if isinstance(backend_name, BaseCache):
        return backend_name

    if backend_name is None:
        backend_name = _get_default_backend_name()
    try:
        return registry[backend_name](cache_name, **options)
    except KeyError:
        if backend_name in _backend_dependencies:
            raise ImportError('You must install the python package: %s' % _backend_dependencies[backend_name])
        else:
            raise ValueError('Unsupported backend "%s" try one of: %s' % (backend_name, ', '.join(registry.keys())))


def _get_default_backend_name():
    if 'sqlite' in registry:
        return 'sqlite'
    return 'memory'
