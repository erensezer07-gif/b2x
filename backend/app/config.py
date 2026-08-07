"""Ortam değişkenlerinden okunan uygulama ayarları.

Şartname Bölüm 0: hiçbir ortam bilgisi koda gömülmez. Sunucu adresi, veritabanı
bilgisi, gizli anahtarlar ve portlar yalnızca ortam değişkeninden gelir.

İki tür alan var:

* **Varsayılanı olmayanlar** — makineye özel veya gizli olanlar. Eksikse uygulama
  hiç açılmaz. Yanlış bir varsayılanla sessizce çalışmaktansa açılmaması gerekir.
* **Varsayılanı olanlar** — makineden makineye değişmeyen değerler (dinleme
  arayüzü, standart portlar, motor ayarları). Yine de doğru kaynak `.env`
  dosyasıdır; buradaki değerler yalnızca yedektir.

Ayarlar depo kökündeki `.env` dosyasından okunur. Docker imajında böyle bir dosya
yoktur, değerler doğrudan konteynerin ortamından gelir — ikisi de çalışır.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/app -> backend -> depo kökü
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """`.env` dosyasındaki değişkenlerin tipli karşılığı."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Uygulama ---
    app_env: str = "development"
    app_debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = ""

    # --- Veritabanı ---
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str
    postgres_port: int = 5432

    # Veritabanı bağlantısı ve sorgusu için üst sınır.
    #
    # `pool_pre_ping` kapanmış bağlantıyı yakalıyor ama **kara deliğe düşmüş**
    # bağlantıyı yakalayamıyor: veritabanı kaybolduğunda (konteyner yeniden
    # başladı, ağ koptu) paketler cevapsız kalıyor ve soket işletim sisteminin
    # zaman aşımına kadar bekliyor. O sırada uygulama hata da vermiyor, cevap
    # da: kullanıcı sonsuz dönen bir göstergeye bakıyor. Sınır konunca istek
    # düzgün bir hatayla biter ve ekran "tekrar dene" gösterir.
    db_timeout_seconds: int = 30

    # --- Redis ---
    redis_host: str
    redis_port: int = 6379

    # --- Kimlik (Aşama 3'te kullanılacak, şimdilik yalnızca okunuyor) ---
    jwt_secret: SecretStr
    jwt_access_token_minutes: int = 30
    jwt_refresh_token_days: int = 30

    # --- Dosya depolama (Aşama 3) ---
    storage_backend: str = "local"
    storage_local_path: str = "./storage"
    storage_public_base_url: str = ""

    # --- Eşleştirme motoru varsayılanları (Aşama 2 ve 7) ---
    matching_min_meetings_per_person: int = 4
    matching_quality_threshold: float = 0.35
    matching_default_seed: int = 42
    matching_max_iterations: int = 100_000
    matching_move_penalty: float = 5.0

    # --- Talep sistemi (Aşama 10) ---
    request_quota_per_participant: int = 3

    @property
    def database_url(self) -> str:
        """SQLAlchemy async bağlantı adresi.

        Kullanıcı adı ve parola URL'e gömüldüğü için özel karakterler kaçırılır;
        aksi halde parolada geçen bir `@` veya `/` adresi bozar.
        """
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password.get_secret_value())
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def cors_origin_list(self) -> list[str]:
        """`CORS_ORIGINS` değerini listeye çevirir. Boşsa CORS hiç kurulmaz."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Ayarları bir kez okuyup önbelleğe alır."""
    return Settings()  # type: ignore[call-arg]  # değerler ortamdan gelir
