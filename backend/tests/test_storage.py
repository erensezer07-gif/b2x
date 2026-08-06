"""Dosya depolama arayüzü (şartname Bölüm 3).

*"Kod bunu doğrudan yapmaz — arada bir depolama arayüzü olur (yükle, sil, adres
al). Böylece proje devredildiğinde bulut depolamaya geçmek tek dosya
değiştirmekle olur."*

Bu testler veritabanı istemez; geçici bir klasörle çalışır.
"""

from pathlib import Path

import pytest

from app.services.storage import LocalDiskStorage, Storage, StorageError

PIXEL = b"\x89PNG\r\n\x1a\n" + b"sahte gorsel icerigi"


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskStorage:
    return LocalDiskStorage(root=tmp_path, public_base_url="https://ornek.com/files")


async def test_saved_file_lands_on_disk(storage: LocalDiskStorage, tmp_path: Path) -> None:
    key = await storage.save(PIXEL, folder="profile-photos", content_type="image/png")

    written = tmp_path / key
    assert written.exists()
    assert written.read_bytes() == PIXEL


async def test_key_carries_the_right_extension(storage: LocalDiskStorage) -> None:
    png = await storage.save(PIXEL, folder="foto", content_type="image/png")
    jpeg = await storage.save(PIXEL, folder="foto", content_type="image/jpeg")

    assert png.endswith(".png")
    assert jpeg.endswith(".jpg")


async def test_keys_are_unpredictable(storage: LocalDiskStorage) -> None:
    """Ad rastgele: başkasının fotoğrafının adresi tahmin edilememeli."""
    keys = {await storage.save(PIXEL, folder="foto", content_type="image/png") for _ in range(5)}
    assert len(keys) == 5


async def test_uploaded_filename_is_never_used(storage: LocalDiskStorage) -> None:
    """Kullanıcının verdiği ad yol kaçışı taşıyabilir; hiç kullanılmıyor."""
    key = await storage.save(PIXEL, folder="foto", content_type="image/png")
    assert "../" not in key
    assert key.startswith("foto/")


async def test_public_url_is_built_from_the_configured_base(
    storage: LocalDiskStorage,
) -> None:
    """Adres saklanmıyor, anahtardan üretiliyor: sunucu taşınınca kırılmasın."""
    key = await storage.save(PIXEL, folder="foto", content_type="image/png")
    assert storage.public_url(key) == f"https://ornek.com/files/{key}"


async def test_delete_removes_the_file(storage: LocalDiskStorage, tmp_path: Path) -> None:
    key = await storage.save(PIXEL, folder="foto", content_type="image/png")
    await storage.delete(key)
    assert not (tmp_path / key).exists()


async def test_deleting_a_missing_file_is_not_an_error(
    storage: LocalDiskStorage,
) -> None:
    """Silme çağrısı temizlik amaçlı; olmayan dosya için hata atmamalı."""
    await storage.delete("foto/olmayan-dosya.png")


async def test_key_cannot_escape_the_storage_root(storage: LocalDiskStorage) -> None:
    """Bozuk bir anahtar kök dışında dosya silememeli."""
    with pytest.raises(StorageError):
        await storage.delete("../../gizli.txt")


def test_local_disk_storage_satisfies_the_contract() -> None:
    """Uygulama katmanı somut sınıfı değil arayüzü görüyor."""
    assert issubclass(LocalDiskStorage, Storage)
