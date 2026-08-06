"""Dosya depolama arayüzü (şartname Bölüm 3).

*"Profil fotoğrafları MVP'de yerel bir klasöre yazılır. Ancak kod bunu doğrudan
yapmaz — arada bir depolama arayüzü olur (yükle, sil, adres al). Böylece proje
devredildiğinde bulut depolamaya geçmek tek dosya değiştirmekle olur."*

Uygulama katmanı yalnızca `Storage` arayüzünü görür; diskin nerede olduğunu
bilmez. S3'e geçmek için `Storage`'ı uygulayan yeni bir sınıf yazıp
`get_storage()` içindeki eşlemeye eklemek yeterli.

## Anahtar mı, adres mi

Veritabanında **anahtar** saklanır (`profiles.photo_key`), tam adres değil.
Adres depolama arkasına ve ortama göre değişir (`STORAGE_PUBLIC_BASE_URL`);
kaydedilmiş bir adres, sunucu taşındığında kırılırdı.
"""

import mimetypes
import secrets
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings

# Profil fotoğrafı için kabul edilen türler. Liste dar tutuluyor: tarayıcıda
# çalışması garanti olan biçimler yeterli, SVG bilerek yok (içine betik gömülebilir).
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Profil fotoğrafı için üst sınır. Telefon kamerasından gelen ham dosya bunu
# aşabilir; istemci küçültmeden gönderirse sunucu reddeder.
MAX_IMAGE_BYTES = 5 * 1024 * 1024


class StorageError(Exception):
    """Dosya yazılamadı veya silinemedi."""


class Storage(ABC):
    """Depolama sözleşmesi: yükle, sil, adres al."""

    @abstractmethod
    async def save(self, content: bytes, *, folder: str, content_type: str) -> str:
        """Dosyayı yazar ve **anahtarını** döndürür."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Dosyayı siler. Yoksa sessizce geçer."""

    @abstractmethod
    def public_url(self, key: str) -> str:
        """Anahtardan dışarıya verilecek adresi üretir."""


class LocalDiskStorage(Storage):
    """Dosyaları yerel bir klasöre yazar (MVP).

    Klasör yolu ve dışarıdan görünen adres ortam değişkeninden gelir; kodda
    sabit yol yok (Bölüm 0).
    """

    def __init__(self, root: Path, public_base_url: str) -> None:
        self._root = root
        self._public_base_url = public_base_url.rstrip("/")

    async def save(self, content: bytes, *, folder: str, content_type: str) -> str:
        extension = ALLOWED_IMAGE_TYPES.get(content_type)
        if extension is None:
            extension = mimetypes.guess_extension(content_type) or ".bin"

        # Ad rastgele: kullanıcının gönderdiği dosya adı hem yol kaçışı (../)
        # hem de başkasının dosyasını tahmin etme riski taşır.
        key = f"{folder}/{secrets.token_urlsafe(16)}{extension}"
        destination = self._resolve(key)

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        except OSError as error:
            raise StorageError(f"Dosya yazılamadı: {error}") from error

        return key

    async def delete(self, key: str) -> None:
        try:
            self._resolve(key).unlink(missing_ok=True)
        except OSError as error:
            raise StorageError(f"Dosya silinemedi: {error}") from error

    def public_url(self, key: str) -> str:
        return f"{self._public_base_url}/{key}"

    def _resolve(self, key: str) -> Path:
        """Anahtarı disk yoluna çevirir ve kök dışına çıkışı engeller.

        Anahtarlar bizim ürettiğimiz için normalde güvenli; yine de veritabanından
        gelen bir değer bozulmuş olabilir ve `../` içeren bir anahtar kök dışında
        dosya silebilirdi.
        """
        candidate = (self._root / key).resolve()
        root = self._root.resolve()
        if not candidate.is_relative_to(root):
            raise StorageError("Geçersiz dosya anahtarı.")
        return candidate


def _build_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalDiskStorage(
            root=Path(settings.storage_local_path),
            public_base_url=settings.storage_public_base_url,
        )
    # Bulut depolamaya geçildiğinde eklenecek tek yer burası.
    raise ValueError(f"Bilinmeyen depolama arka ucu: {settings.storage_backend}")


@lru_cache
def get_storage() -> Storage:
    return _build_storage(get_settings())
