"""Generic relational database backend that works with any dialect supported by SQLAlchemy

import json

**Example (PostgreSQL):**

::

    >>> from requests_cache import CachedSession, DBCache
    >>> from sqlalchemy import create_engine
    >>>
    >>> engine = create_engine('postgresql://user@localhost:5432/postgres')
    >>> session = CachedSession(backend=DBCache(engine))

"""

import json
from datetime import timedelta
from typing import Optional, Type, TypeAlias

from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict
from sqlalchemy import Column, DateTime, Float, Integer, LargeBinary, String, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as SA_Session
from sqlalchemy.orm import declarative_base

from ..models import CachedRequest, CachedResponse
from . import BaseCache, BaseStorage

Base: TypeAlias = declarative_base()  # type: ignore


# TODO: Benchmark read & write with ORM model vs. creating a CachedResponse from raw SQL query
class DBResponse(Base):
    """Database model based on :py:class:`.CachedResponse`. Instead of full serialization, this maps
    request attributes to database columns. The corresponding table is generated based on this model.
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


class DBRedirect(Base):
    __tablename__ = 'redirect'
    key = Column(String, primary_key=True)
    response_key = Column(String, index=True)


class DBCache(BaseCache):
    def __init__(self, engine: Engine, **kwargs):
        super().__init__(**kwargs)
        # Create tables if they don't exist
        Base.metadata.create_all(engine)
        session = SA_Session(engine, future=True)

        self.responses = DBStorage(session, model=DBResponse, **kwargs)
        # TODO: Separate class for handling redirects
        self.redirects = BaseStorage()  # DBStorage(session, model=DBRedirect, **kwargs)


class DBStorage(BaseStorage):
    def __init__(self, session: SA_Session, model: Type[Base], **kwargs):
        super().__init__(no_serializer=True, **kwargs)
        self.session = session
        self.model = model

    def __getitem__(self, key: str) -> CachedResponse:
        with self.session:
            stmt = select(DBResponse).where(DBResponse.key == key)
            result = self.session.execute(stmt).fetchone()
        if not result:
            raise KeyError
        return result[0].to_cached_response()

    def __setitem__(self, key: str, value: CachedResponse):
        value.cache_key = key
        self.session.merge(DBResponse.from_cached_response(value))
        self.session.commit()

    def __delitem__(self, key: str):
        stmt = delete(DBResponse).where(DBResponse.key == key)
        if not self.session.execute(stmt).rowcount:
            raise KeyError

    def __iter__(self):
        for row in self.session.execute(select(DBResponse)).all():
            yield row

    def __len__(self) -> int:
        stmt = select([func.count()]).select_from(DBResponse)
        return self.session.execute(stmt).scalar()

    def clear(self):
        self.session.execute(delete(DBResponse))


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
