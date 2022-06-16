"""Generic relational database backend that works with any dialect supported by SQLAlchemy"""

import json

from sqlalchemy import Column, DateTime, Integer, LargeBinary, String
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base

from ..models import CachedRequest, CachedResponse
from . import BaseCache, BaseStorage

Base = declarative_base()


# TODO: Benchmark read & write with ORM model vs. creating a CachedResponse from raw SQL query
class SQLResponse(Base):
    """Database model based on :py:class:`.CachedResponse`. Instead of full serialization, this maps
    request attributes to database columns. The corresponding table is generated based on this model.
    """

    __tablename__ = 'response'

    key = Column(String, primary_key=True)
    cookies = Column(String)
    content = Column(LargeBinary)
    created_at = Column(DateTime, nullable=False, index=True)
    elapsed = Column(Integer)
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

    @classmethod
    def from_cached_response(cls, response: CachedResponse):
        """Convert from db model into CachedResponse (to emulate the original response)"""
        return cls(
            key=response.cache_key,
            cookies=json.dumps(response.cookies),
            content=response.content,
            created_at=response.created_at,
            elapsed=response.elapsed,
            expires=response.expires,
            encoding=response.encoding,
            headers=json.dumps(response.headers),
            reason=response.reason,
            request_body=response.request.body,
            request_cookies=json.dumps(response.request.cookies),
            request_headers=json.dumps(response.request.headers),
            request_method=response.request.method,
            request_url=response.request.url,
            status_code=response.status_code,
            url=response.url,
        )

    def to_cached_response(self) -> CachedResponse:
        """Convert from CachedResponse to db model (so SA can handle dialect-specific types, etc.)"""
        request = CachedRequest(
            body=self.request_body,
            cookies=json.loads(self.request_cookies) if self.request_cookies else None,
            headers=json.loads(self.request_headers) if self.request_headers else None,
            method=self.request_method,
            url=self.request_url,
        )
        obj = CachedResponse(
            cookies=json.loads(self.cookies) if self.cookies else None,
            content=self.content,
            created_at=self.created_at,
            elapsed=self.elapsed,
            expires=self.expires,
            encoding=self.encoding,
            headers=json.loads(self.headers) if self.headers else None,
            reason=self.reason,
            request=request,
            status_code=self.status_code,
            url=self.url,
        )
        obj.cache_key = self.key  # Can't be set in init
        return obj


class SQLRedirect(Base):
    __tablename__ = 'redirect'
    redirect_key = Column(String, primary_key=True)
    response_key = Column(String, index=True)


class DbCache(BaseCache):
    def __init__(self, engine: Engine, **kwargs):
        super().__init__(**kwargs)
        self.redirects = DbStorage(engine, model=SQLResponse, **kwargs)
        self.responses = DbStorage(engine, model=SQLRedirect, **kwargs)


class DbStorage(BaseStorage):
    def __init__(self, engine: Engine, model, **kwargs):
        super().__init__(no_serializer=True, **kwargs)
        self.engine = engine
        self.model = model

    def __getitem__(self, key):
        pass

    def __setitem__(self, key, value):
        pass

    def __delitem__(self, key):
        pass

    def __iter__(self):
        pass

    def __len__(self):
        pass

    def clear(self):
        pass
