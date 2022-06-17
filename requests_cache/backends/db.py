"""Generic relational database backend that works with any dialect supported by SQLAlchemy

import json

**Example (PostgreSQL):**

::

    >>> from requests_cache import CachedSession, DbCache
    >>> from sqlalchemy import create_engine
    >>>
    >>> engine = create_engine('postgresql://user@localhost:5432/postgres')
    >>> session = CachedSession(backend=DbCache(engine))

"""

import json
from datetime import timedelta
from logging import getLogger
from typing import Iterable, Iterator, List, Optional, Type, TypeAlias

from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict
from sqlalchemy import Column, DateTime, Float, Integer, LargeBinary, String, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SA_Session
from sqlalchemy.orm import declarative_base

from ..models import AnyRequest, CachedRequest, CachedResponse
from ..policy import ExpirationTime, get_expiration_datetime
from . import BaseCache, BaseStorage

Base: TypeAlias = declarative_base()  # type: ignore
logger = getLogger(__name__)


# TODO: Benchmark read & write with ORM model vs. creating a CachedResponse from raw SQL query
# TODO: Separate class for handling redirects
# TODO: Concurrency
class DbCache(BaseCache):
    def __init__(self, engine: Engine, **kwargs):
        super().__init__(**kwargs)
        # Create tables if they don't exist
        Base.metadata.create_all(engine)
        session = SA_Session(engine, future=True)

        self.responses: DbDict = DbDict(session, model=DbResponse, **kwargs)
        # self.redirects = DbDict(session, model=DbRedirect, **kwargs)

    @property
    def session(self) -> SA_Session:
        return self.responses.session

    def delete(
        self,
        *keys: str,
        expired: bool = False,
        invalid: bool = False,
        older_than: ExpirationTime = None,
        requests: Iterable[AnyRequest] = None,
    ):
        """A more efficient implementation of :py:meth:`BaseCache.delete`"""
        delete_keys: List[str] = list(keys) if keys else []
        if requests:
            delete_keys += [self.create_key(request) for request in requests]
        if delete_keys:
            self.responses.bulk_delete(delete_keys)
        if expired:
            self._delete_expired()
        if invalid:
            return super().delete(invalid=True)
        if older_than:
            self._delete_older_than(older_than)

        self._prune_redirects()
        self.responses.vacuum()

    def _delete_expired(self):
        """A more efficient implementation of deleting expired responses"""
        stmt = delete(DbResponse).where(DbResponse.expires < func.now())
        self.session.execute(stmt)

    def _delete_older_than(self, older_than: ExpirationTime):
        """A more efficient implementation of deleting responses older than a given time"""
        older_than_dt = get_expiration_datetime(older_than, negative_delta=True)
        stmt = delete(DbResponse).where(DbResponse.created_at < older_than_dt)
        self.session.execute(stmt)

    def _prune_redirects(self):
        """A more efficient implementation of removing invalid redirects"""
        self.session.execute(
            'DELETE FROM redirects WHERE key IN ('
            '    SELECT redirects.key FROM redirects'
            '    LEFT JOIN responses ON responses.key = redirects.value'
            '    WHERE responses.key IS NULL'
            ')'
        )

    def filter(
        self,
        valid: bool = True,
        expired: bool = True,
        invalid: bool = False,
        older_than: ExpirationTime = None,
    ) -> Iterator[CachedResponse]:
        """A more efficient implementation of :py:meth:`BaseCache.filter`.
        ``invalid`` is not supported.
        """
        stmt = select(DbResponse)
        if not expired:
            stmt = stmt.where(DbResponse.expires > func.now())
        elif not valid:
            stmt = stmt.where(DbResponse.expires < func.now())
        if invalid:
            logger.warning('Filtering by invalid responses is not supported for this backend')

        if older_than:
            older_than = get_expiration_datetime(older_than, negative_delta=True)
            stmt = stmt.where(DbResponse.created_at < older_than)

        for result in self.session.execute(stmt).all():
            yield result[0].to_cached_response()


class DbDict(BaseStorage):
    def __init__(self, session: SA_Session, model: Type[Base], **kwargs):
        super().__init__(no_serializer=True, **kwargs)
        self.session = session
        self.model = model

    def __getitem__(self, key: str) -> CachedResponse:
        with self.session:
            stmt = select(DbResponse).where(DbResponse.key == key)
            result = self.session.execute(stmt).fetchone()
        if not result:
            raise KeyError
        return result[0].to_cached_response()

    def __setitem__(self, key: str, value: CachedResponse):
        value.cache_key = key
        self.session.merge(DbResponse.from_cached_response(value))
        self.session.commit()

    def __delitem__(self, key: str):
        stmt = delete(DbResponse).where(DbResponse.key == key)
        if not self.session.execute(stmt).rowcount:
            raise KeyError
        self.session.commit()

    def __iter__(self):
        for result in self.session.execute(select(DbResponse)).all():
            yield result[0]

    def __len__(self) -> int:
        stmt = select([func.count()]).select_from(DbResponse)
        return self.session.execute(stmt).scalar()

    def bulk_delete(self, keys: Iterable[str]):
        stmt = delete(DbResponse).where(DbResponse.key.in_(keys))
        self.session.execute(stmt)
        self.session.commit()

    def clear(self):
        self.session.execute(delete(DbResponse))
        self.session.commit()

    def vacuum(self):
        self.session.execute('VACUUM')


class DbResponse(Base):
    """Database model based on :py:class:`.CachedResponse`, used for serializing a response into
    a database row instead of a single binary value.
    """

    __tablename__ = 'response'

    key = Column(String, primary_key=True)
    cookies = Column(String)
    content = Column(LargeBinary)
    created_at = Column(DateTime, nullable=False, index=True)
    elapsed = Column(Float)
    expires = Column(DateTime, index=True)
    encoding = Column(String)
    headers = Column(String)
    reason = Column(String)
    request_body = Column(LargeBinary)
    request_cookies = Column(String)
    request_headers = Column(String)
    request_method = Column(String, nullable=False)
    request_url = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    url = Column(String, nullable=False, index=True)

    # TODO: Maybe these conversion methods should be moved to a different module as a "serializer"?
    @classmethod
    def from_cached_response(cls, response: CachedResponse):
        """Convert from db model into CachedResponse (to emulate the original response)"""
        return cls(
            key=response.cache_key,
            cookies=_save_cookies(response.cookies),
            content=response.content,
            created_at=response.created_at,
            elapsed=response.elapsed.total_seconds(),
            expires=response.expires,
            encoding=response.encoding,
            headers=_save_headers(response.headers),
            reason=response.reason,
            request_body=response.request.body,
            request_cookies=_save_cookies(response.request.cookies),
            request_headers=_save_headers(response.request.headers),
            request_method=response.request.method,
            request_url=response.request.url,
            status_code=response.status_code,
            url=response.url,
        )

    def to_cached_response(self) -> CachedResponse:
        """Convert from CachedResponse to db model (so SA can handle dialect-specific behavior)"""
        request = CachedRequest(
            body=self.request_body,
            cookies=_load_cookies(self.request_cookies),
            headers=_load_headers(self.request_headers),
            method=self.request_method,
            url=self.request_url,
        )
        obj = CachedResponse(
            cookies=_load_cookies(self.cookies),
            content=self.content,
            created_at=self.created_at,
            elapsed=timedelta(seconds=float(self.elapsed)),
            expires=self.expires,
            encoding=self.encoding,
            headers=_load_headers(self.headers),
            reason=self.reason,
            request=request,
            status_code=self.status_code,
            url=self.url,
        )
        obj.cache_key = self.key  # Can't be set in init
        return obj


class DbRedirect(Base):
    __tablename__ = 'redirect'
    key = Column(String, primary_key=True)
    response_key = Column(String, index=True)


def _load_cookies(cookies_str: str) -> RequestsCookieJar:
    try:
        return cookiejar_from_dict(json.loads(cookies_str))
    except (TypeError, ValueError):
        return RequestsCookieJar()


def _save_cookies(cookies: RequestsCookieJar) -> Optional[str]:
    return json.dumps(cookies.get_dict()) if cookies else None


def _load_headers(headers_str: str) -> CaseInsensitiveDict:
    try:
        return json.loads(headers_str)
    except (TypeError, ValueError):
        return CaseInsensitiveDict()


def _save_headers(headers: CaseInsensitiveDict) -> Optional[str]:
    return json.dumps(dict(headers)) if headers else None
