"""Filesystem cache backend. For usage details, see :ref:`Backends: Filesystem <filesystem>`.

.. automodsumm:: requests_cache.backends.filesystem
   :classes-only:
   :nosignatures:
"""

from contextlib import contextmanager
from os import makedirs
from pathlib import Path
from pickle import PickleError
from shutil import rmtree
from threading import RLock
from typing import Any, Iterator, Optional, Tuple

from ..serializers import SerializerType, json_serializer
from . import BaseCache, BaseStorage, StrOrPath
from .sqlite import SQLiteDict, get_cache_path


class FileCache(BaseCache):
    """Filesystem cache backend.

    Args:
        cache_name: Base directory for cache files
        use_cache_dir: Store database in a user cache directory (e.g., `~/.cache/`)
        use_temp: Store cache files in a temp directory (e.g., ``/tmp/http_cache/``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
        decode_content: Decode JSON or text response body into a human-readable format
        extension: Extension for cache files. If not specified, the serializer default extension
            will be used.
        maximum_cache_bytes: Maximum total size of all cached responses on the file system in bytes
            If a response is larger than this, it will not be cached.
            If a response would make the cache bigger than this, the oldest response gets dropped.
            By default, the size is not limited.
        block_bytes: The size of a block of data on the file system.
            The file size will be computed as multiples of this.
            Default is 1 byte.
            Only used if ``maximum_cache_bytes`` is set.
        maximum_file_bytes: The maximum size of a single file.
            By default, this is the same as ``maximum_cache_bytes``.
            Only used if ``maximum_cache_bytes`` is set.
        lock: An optional lock to use for the directory.
            By default, this is a :class:`threading.RLock`.
            You can also use :attr:`filelock.FileLock` and a :class:`multiprocessing.RLock`.
    """

    def __init__(
        self,
        cache_name: StrOrPath = 'http_cache',
        use_temp: bool = False,
        decode_content: bool = True,
        serializer: Optional[SerializerType] = None,
        **kwargs,
    ):
        super().__init__(cache_name=str(cache_name), **kwargs)
        skwargs = {'serializer': serializer, **kwargs} if serializer else kwargs
        self.responses: FileDict = (
            LimitedFileDict if 'maximum_cache_bytes' in kwargs else FileDict
        )(cache_name, use_temp=use_temp, decode_content=decode_content, **skwargs)
        with self.lock:
            self.redirects: SQLiteDict = SQLiteDict(
                self.cache_dir / 'redirects.sqlite', 'redirects', serializer=None, **kwargs
            )

    @property
    def lock(self) -> RLock:
        """The lock used by the cache."""
        return self.responses.lock

    @property
    def cache_dir(self) -> Path:
        """Base directory for cache files"""
        return Path(self.responses.cache_dir)

    def paths(self) -> Iterator[Path]:
        """Get absolute file paths to all cached responses"""
        return self.responses.paths()

    def clear(self):
        """Clear the cache"""
        # FileDict.clear() removes the cache directory, including redirects.sqlite
        self.responses.clear()
        with self.lock:
            self.redirects.init_db()

    def delete(self, *args, **kwargs):
        with self.lock:
            return super().delete(*args, **kwargs)


class FileDict(BaseStorage):
    """A dictionary-like interface to files on the local filesystem.

    The cache directory will be created if it doesn't already exist.
    """

    def __init__(
        self,
        cache_name: StrOrPath,
        use_temp: bool = False,
        use_cache_dir: bool = False,
        extension: Optional[str] = None,
        serializer: Optional[SerializerType] = json_serializer,
        lock: Optional[RLock] = None,
        **kwargs,
    ):
        super().__init__(serializer=serializer, **kwargs)
        self.cache_dir = get_cache_path(cache_name, use_cache_dir=use_cache_dir, use_temp=use_temp)
        self.extension = _get_extension(extension, self.serializer)
        self.is_binary = getattr(self.serializer, 'is_binary', False)
        self._lock = lock if lock is not None else RLock()
        makedirs(self.cache_dir, exist_ok=True)

    @property
    def lock(self) -> RLock:
        """The lock used by the cache."""
        return self._lock

    @contextmanager
    def _try_io(self, key: Optional[str] = None, ignore_errors: bool = False):
        """Attempt an I/O operation, and either ignore errors or re-raise them as KeyErrors"""
        try:
            with self._lock:
                yield
        except (EOFError, IOError, OSError, PickleError) as e:
            if not ignore_errors:
                raise KeyError(f'File for key {key!r} not found.') from e

    def _key2path(self, key: str) -> Path:
        return self.cache_dir / f'{key}{self.extension}'

    def __getitem__(self, key: str):
        mode = 'rb' if self.is_binary else 'r'
        with self._try_io(key):
            with self._key2path(key).open(mode) as f:
                return self.deserialize(key, f.read())

    def __delitem__(self, key):
        with self._try_io(key):
            self._key2path(key).unlink()

    def __setitem__(self, key, value):
        with self._try_io(key):
            with self._key2path(key).open(mode='wb' if self.is_binary else 'w') as f:
                f.write(self.serialize(value))

    def __iter__(self) -> Iterator[str]:
        yield from self.keys()

    def __len__(self) -> int:
        return sum(1 for _ in self.paths())

    def clear(self) -> None:
        """Empty the cache directory."""
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir()

    def keys(self):
        return [path.stem for path in self.paths()]

    def paths(self) -> Iterator[Path]:
        """Get absolute file paths to all cached responses"""
        with self._lock:
            return self.cache_dir.glob(f'*{self.extension}')


def _get_extension(extension: Optional[str] = None, serializer=None) -> str:
    """Use either the provided file extension, or get the serializer's default extension"""
    if extension:
        return f'.{extension}'
    subs = {
        'bson': 'bson',
        'safe_pickle': 'pkl',
        'pickle': 'pkl',
        'orjson': 'json',
        'ujson': 'json',
    }
    if serializer and (name := serializer.name):
        for k, v in subs.items():
            name = name.replace(k, v)
        return f'.{name}'
    return '.dat'


TEN_MB = 10 * 1024 * 1024


class LimitedFileDict(FileDict):
    """A size-restricted version of the file-dict.

    Args:
        maximum_cache_bytes: The maximum total size of all files in the cache.
            This is 10MB by default.
        block_bytes: The size of a block of data on the file system.
            The file size will be computed as multiples of this.
            This is 1 by default.
        maximum_file_bytes: The maximum size of a single file.
            By default, this is the same as ``maximum_cache_bytes``.

    File system layout::

        cache_dir/
            last.int -> int; last file <id>
            size.int -> int; size of all files added up
            <key>.<ext>/<id> -> bytes; content
            ids/<id> -> <key>.<ext>; ordered ids to find oldest fast
    """

    def __init__(
        self,
        *args,
        maximum_cache_bytes: int = TEN_MB,
        block_bytes: int = 1,
        maximum_file_bytes: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.maximum_cache_bytes = maximum_cache_bytes
        self.block_bytes = block_bytes
        self.maximum_file_bytes = (
            maximum_file_bytes if maximum_file_bytes is not None else maximum_cache_bytes
        )
        if self.maximum_file_bytes > self.maximum_cache_bytes:
            raise ValueError(
                f'maximum_file_bytes must be smaller or equal to maximum_cache_bytes ({maximum_cache_bytes})'
            )
        if self.block_bytes > self.maximum_file_bytes:
            raise ValueError(
                f'block_bytes must be smaller than maximum_file_bytes ({maximum_file_bytes})'
            )
        if self.block_bytes < 1:
            raise ValueError(f'block_bytes must be greater than 0, not {block_bytes}')
        self._oldest_id_checked: int = 0
        self.id_file = self.cache_dir / 'last.int'
        self.size_file = self.cache_dir / 'size.int'
        self.ids_dir = self.cache_dir / 'ids'
        self.ids_dir.mkdir(exist_ok=True)

    def get_new_file_id(self) -> int:
        """Return a new id for a file to store.

        Files are versioned.
        This way, we can make sure we drop them in the right order.
        """
        with self._lock:
            if not self.id_file.is_file():
                self.id_file.write_text('0')
                return 0
            new_id = self.newest_id + 1
            self.id_file.write_text(str(new_id))
            return new_id

    @property
    def newest_id(self) -> int:
        """The id of the last added file."""
        try:
            return int(self.id_file.read_text() or 0)
        except (FileNotFoundError, ValueError):
            return 0

    @property
    def total_bytes(self) -> int:
        """The total size of all the files in the cache."""
        try:
            return int(self.size_file.read_text() or 0)
        except (FileNotFoundError, ValueError):
            return 0

    def _add_to_total_bytes(self, difference_in_bytes: int):
        """Change the size of the cache."""
        with self._lock:
            difference_in_bytes = self.compute_file_size(self.block_bytes, difference_in_bytes)
            self.size_file.write_text(str(difference_in_bytes + self.total_bytes))

    def _get_raw(self, key: str):
        """Return the raw content of a key."""
        content_dir = self.cache_dir / f'{key}{self.extension}'
        with self._try_io(key):
            for content_path in content_dir.iterdir():
                # we can assume there is only one file in the directory
                return (
                    content_path.read_bytes() if self.is_binary else content_path.read_text('UTF-8')
                )
        raise KeyError(f'File for key {key!r} not found.')

    def __getitem__(self, key: str) -> Any:
        """Get a value from a key."""
        return self.deserialize(key, self._get_raw(key))

    def __delitem__(self, key: str) -> None:
        """Delete a value for a key."""
        content_dir = self.cache_dir / f'{key}{self.extension}'
        with self._try_io(key):
            had_content = False
            for content_path in content_dir.iterdir():
                version = int(content_path.stem)
                self._add_to_total_bytes(-content_path.stat().st_size)
                content_path.unlink()
                version_path = self.ids_dir / str(version)
                version_path.unlink()
                had_content = True
            content_dir.rmdir()
            if not had_content:
                raise KeyError(f'File for key {key!r} not found.')

    def get_oldest_key(self) -> Tuple[Optional[str], Optional[Path]]:
        """Return the oldest key.

        This is safe to run outside of a lock.
        """
        newest_id = self.newest_id
        oldest_checked = self._oldest_id_checked
        key = path = None
        while oldest_checked <= newest_id:
            path_to_check = self.ids_dir / str(oldest_checked)
            try:
                key = path_to_check.read_text()
            except FileNotFoundError:
                pass
            else:
                path = path_to_check
                break
            oldest_checked += 1
        self._oldest_id_checked = max(oldest_checked, self._oldest_id_checked)
        return key, path

    def __setitem__(self, key: str, value: Any) -> None:
        content = self.serialize(value)
        data = content.encode('UTF-8') if isinstance(content, str) else content
        del content
        if len(data) > self.maximum_file_bytes:
            return
        # We can make space without a lock.
        # This reduces the time to wait for others.
        try:
            del self[key]
        except KeyError:
            pass
        self.make_space(len(data))
        with self._try_io(key):
            # Inside the lock, we should make space to make sure we have it.
            try:
                del self[key]
            except KeyError:
                pass
            self.make_space(len(data))
            content_dir_name = f'{key}{self.extension}'
            file_id = str(self.get_new_file_id())
            content_file = self.cache_dir / content_dir_name / file_id
            id_file = self.ids_dir / file_id
            content_file.parent.mkdir(exist_ok=True)
            content_file.write_bytes(data)
            self._add_to_total_bytes(len(data))
            id_file.write_text(key)

    def clear(self) -> None:
        """Empty the cache directory."""
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir()
            self.ids_dir.mkdir()

    def keys(self):
        """Get all the keys in the cache."""
        return [
            path.stem for path in self.cache_dir.glob(f'*{self.extension}') if any(path.iterdir())
        ]

    def paths(self) -> Iterator[Path]:
        """Get absolute file paths to all cached responses"""
        return self.cache_dir.glob(f'*{self.extension}/*')

    def drop_oldest_key(self) -> bool:
        """Drop the oldest key.

        Returns:
            True if a key was dropped, False if not.
        """
        key, path = self.get_oldest_key()
        if key is not None:
            try:
                del self[key]
                return True
            except KeyError:
                pass
        if path is not None:
            path.unlink()
        return False

    def make_space(self, desired_free_bytes: int):
        """Make space in the cache to fit the given number of bytes.

        This starts deleting the oldest entries first.
        If you want more space than available, nothing happens.
        """
        desired_free_bytes = self.compute_file_size(self.block_bytes, desired_free_bytes)
        can_drop_a_key = True
        while (
            desired_free_bytes < self.total_bytes + desired_free_bytes > self.maximum_cache_bytes
            and can_drop_a_key
        ):
            can_drop_a_key = self.drop_oldest_key()

    def debug_state(self, max_lines=-1) -> str:
        """Return the state of the cache for debug purposes."""
        s = ''
        for file in sorted(self.cache_dir.glob('*/*')):
            if file.is_file():
                s += f'{file.relative_to(self.cache_dir)} -> {file.read_text()[:20]}\n'
                max_lines -= 1
                if max_lines == 0:
                    return s + '...'
        return s

    @staticmethod
    def compute_file_size(block_size: int, file_size: int) -> int:
        """Return the size in bytes of the file, rounded up to fit the blocks on the file system"""
        sign = -1 if file_size < 0 else 1
        return (file_size * sign + block_size - 1) // block_size * block_size * sign


___all__ = ['FileCache', 'FileDict', 'LimitedFileDict']
