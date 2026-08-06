"""Test ortamı ve veritabanı fixture'ları.

İki tür test var:

* **Veritabanı istemeyenler** — ayarlar, sağlık ucu, motor sınırı. Depoyu yeni
  klonlamış biri Docker'ı hiç çalıştırmadan `pytest` diyebilmeli.
* **Kısıt testleri** — şemanın gerçekten koruduğunu kanıtlayanlar. Bunlar ayrı
  bir test veritabanı ister; veritabanına ulaşılamazsa anlaşılır bir mesajla
  atlanırlar, diğer testleri düşürmezler.

Test veritabanı `alembic upgrade head` ile kurulur, `Base.metadata.create_all`
ile değil. Sebep: teslim edilen şey migration'dır. Modelde olup migration'a
girmemiş bir kısıt ancak böyle yakalanır.
"""

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator, Callable, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

# `.env` yoksa uygulama modülleri import bile edilemezdi (gizli ayarların
# varsayılanı yok). Bu değerler yalnızca o durumda devreye girer. `.env` varsa
# gerçek yapılandırma kullanılır ve kısıt testleri de çalışabilir.
_FALLBACK_SETTINGS = {
    "APP_ENV": "test",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "POSTGRES_HOST": "veritabani.gecersiz",
    "REDIS_HOST": "redis.gecersiz",
    "JWT_SECRET": "testler-icin-anlamsiz-bir-dize",
}

if not (REPO_ROOT / ".env").exists():
    for key, value in _FALLBACK_SETTINGS.items():
        os.environ.setdefault(key, value)


# Ayarlar okunabilir hâle geldikten sonra import edilir.
from app.config import get_settings  # noqa: E402

DATABASE_UNREACHABLE = "Kısıt testleri veritabanı ister. Başlatmak için: docker compose up -d db"


def _test_database_name() -> str:
    """Gerçek veritabanına dokunmamak için ayrı bir ad."""
    return f"{get_settings().postgres_db}_test"


async def _recreate_test_database() -> None:
    """Test veritabanını sıfırdan oluşturur.

    `CREATE DATABASE` bir işlemin içinde çalışamadığı için SQLAlchemy yerine
    doğrudan sürücü kullanılıyor.
    """
    import asyncpg

    settings = get_settings()
    connection = await asyncpg.connect(
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database="postgres",
    )
    try:
        name = _test_database_name()
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await connection.execute(f'CREATE DATABASE "{name}"')
    finally:
        await connection.close()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Boş bir test veritabanı kurar, migration'ları uygular, adresini döndürür."""
    try:
        asyncio.run(_recreate_test_database())
    except OSError:
        pytest.skip(DATABASE_UNREACHABLE, allow_module_level=True)

    name = _test_database_name()

    # Migration'lar alt süreçte, gerçek komutla çalışır. POSTGRES_DB ortam
    # değişkeni `.env` dosyasındaki değerin önüne geçer.
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "POSTGRES_DB": name},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(f"Test veritabanına migration uygulanamadı:\n{result.stderr}")

    settings = get_settings()
    yield settings.database_url.rsplit("/", 1)[0] + f"/{name}"


@pytest.fixture
async def session(database_url: str) -> AsyncGenerator[AsyncSession]:
    """Her teste kendi işlemini verir; test bitince her şey geri alınır.

    Testler birbirinin verisini görmez, sıraları önemsizdir.
    """
    engine = create_async_engine(database_url)
    connection = await engine.connect()
    transaction = await connection.begin()
    # Oturum dıştaki işleme doğrudan katılmaz, kendi savepoint'ini açar. Bir kısıt
    # ihlalinden sonra oturum kendi işlemini geri alır; savepoint olmasaydı bu
    # dıştaki işlemi de koparır ve temizlik sırasında uyarı üretirdi.
    factory = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        async with factory() as active_session:
            yield active_session
    finally:
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Uygulamayı test oturumuna bağlayan HTTP istemcisi.

    `get_session` bağımlılığı devralınıyor: uçlar testin işlemini kullanıyor,
    dolayısıyla uçların yaptığı `commit` çağrıları da testin sonunda geri
    alınıyor (oturum savepoint üzerinde çalışıyor).
    """
    from app.db import get_session
    from app.main import app

    async def use_test_session() -> AsyncGenerator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = use_test_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def unique_email() -> Callable[[], str]:
    """Testler arası çakışmayan e-posta üretir.

    Ayrılmış üst düzey alan adları (`.test`, `.local`) e-posta doğrulayıcı
    tarafından reddediliyor, bu yüzden gerçek görünümlü bir alan adı kullanılıyor.
    Şartname Bölüm 2: MVP'de e-posta **gönderilmiyor**, adres yalnızca kimlik.
    """

    def build() -> str:
        return f"deneme-{uuid.uuid4().hex[:12]}@ornek.com"

    return build


@pytest.fixture
async def authenticated_client(client: AsyncClient, unique_email: Callable[[], str]) -> AsyncClient:
    """Kayıt olmuş ve jetonu başlığa yerleşmiş istemci."""
    response = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "cok-gizli-sifre"}
    )
    assert response.status_code == 201, response.text
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return client
