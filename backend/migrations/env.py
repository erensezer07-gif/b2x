"""Alembic çalışma ortamı.

Bağlantı adresi `alembic.ini` içinde durmaz; `app.config` üzerinden ortam
değişkeninden gelir. Böylece uygulama ile migration'lar aynı yapılandırmayı
kullanır, iki ayrı doğruluk kaynağı oluşmaz.

Tablolar Aşama 1'de eklenecek. Şu an `Base.metadata` boş ve `versions/` klasöründe
revizyon yok — `alembic upgrade head` bu haliyle hatasız çalışır, yapacak işi olmaz.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings

# app.models tüm model modüllerini içeri alır; import edilmezse Base.metadata boş
# kalır ve autogenerate "her tabloyu sil" diye bir revizyon üretir.
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Adres ortamdan gelir. alembic.ini bir ConfigParser dosyası olduğu için '%'
# karakteri biçimlendirme belirteci sayılır; parolada geçebileceğinden kaçırılır.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

# autogenerate bu şemaya bakarak fark üretir.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Bağlantı kurmadan, yalnızca SQL üreterek çalıştırır."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Async motor kurup migration'ları o bağlantı üzerinde çalıştırır."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
