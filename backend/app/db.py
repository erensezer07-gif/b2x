"""Veritabanı bağlantısı: async motor ve oturum üreteci.

Bağlantı adresi `app.config` üzerinden ortamdan gelir, burada sabit değer yoktur.
Motor ve oturum üreteci ilk kullanımda kurulur; API, arka plan işçisi ve Alembic
aynı yapıyı kullanır.

ORM temeli ve tablolar `app.models` altındadır.
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Uygulama ömrü boyunca tek olan bağlantı havuzu."""
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI bağımlılığı: istek başına bir oturum, istek bitince kapanır."""
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    """Uygulama kapanırken bağlantı havuzunu bırakır."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
