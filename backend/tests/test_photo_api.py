"""Profil fotoğrafı uçları (şartname M2, Bölüm 3).

Uçlar diskin nerede olduğunu bilmiyor; `Storage` sözleşmesini çağırıyor. Testler
depolamayı geçici bir klasöre yönlendiriyor — gerçek `./storage` klasörü
kirlenmesin.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient

from app.main import app
from app.services.storage import LocalDiskStorage, get_storage

PNG = b"\x89PNG\r\n\x1a\n" + b"sahte gorsel"


@pytest.fixture(autouse=True)
def temporary_storage(tmp_path: Path) -> Iterator[LocalDiskStorage]:
    """Depolamayı test süresince geçici klasöre bağlar.

    `dependency_overrides` kullanılıyor, modül değişkeni yamalanmıyor: uçlar
    `get_storage`'ı kendi ad alanlarına import ettiği için modülü yamalamak
    onları etkilemezdi.
    """
    replacement = LocalDiskStorage(root=tmp_path, public_base_url="https://ornek.com/files")

    app.dependency_overrides[get_storage] = lambda: replacement
    try:
        yield replacement
    finally:
        app.dependency_overrides.pop(get_storage, None)


def image(content: bytes = PNG, content_type: str = "image/png") -> dict:
    return {"file": ("foto.png", content, content_type)}


async def test_uploading_a_photo_returns_its_url(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post("/profile/photo", files=image())

    assert response.status_code == 200
    photo_url = response.json()["photo_url"]
    assert photo_url is not None
    assert photo_url.startswith("https://ornek.com/files/profile-photos/")


async def test_photo_lands_in_storage(authenticated_client: AsyncClient, tmp_path: Path) -> None:
    await authenticated_client.post("/profile/photo", files=image())

    written = list(tmp_path.rglob("*.png"))
    assert len(written) == 1
    assert written[0].read_bytes() == PNG


async def test_photo_counts_towards_completion(
    authenticated_client: AsyncClient,
) -> None:
    before = (await authenticated_client.get("/profile")).json()["completion_percent"]
    after = (await authenticated_client.post("/profile/photo", files=image())).json()[
        "completion_percent"
    ]
    assert after > before


async def test_replacing_a_photo_removes_the_previous_file(
    authenticated_client: AsyncClient, tmp_path: Path
) -> None:
    """Eski dosya diskte birikmemeli."""
    await authenticated_client.post("/profile/photo", files=image())
    await authenticated_client.post("/profile/photo", files=image(b"ikinci gorsel"))

    remaining = list(tmp_path.rglob("*.png"))
    assert len(remaining) == 1
    assert remaining[0].read_bytes() == b"ikinci gorsel"


async def test_deleting_a_photo_clears_it_everywhere(
    authenticated_client: AsyncClient, tmp_path: Path
) -> None:
    await authenticated_client.post("/profile/photo", files=image())

    response = await authenticated_client.delete("/profile/photo")

    assert response.status_code == 200
    assert response.json()["photo_url"] is None
    assert not list(tmp_path.rglob("*.png"))


async def test_deleting_without_a_photo_is_harmless(
    authenticated_client: AsyncClient,
) -> None:
    """Fotoğraf adımı atlanabilir; olmayan fotoğrafı silmek hata olmamalı."""
    response = await authenticated_client.delete("/profile/photo")
    assert response.status_code == 200
    assert response.json()["photo_url"] is None


async def test_unsupported_type_is_rejected(authenticated_client: AsyncClient) -> None:
    """SVG bilerek dışarıda: içine betik gömülebilir."""
    response = await authenticated_client.post(
        "/profile/photo",
        files={"file": ("kotu.svg", b"<svg/>", "image/svg+xml")},
    )
    assert response.status_code == 415


async def test_oversized_photo_is_rejected(authenticated_client: AsyncClient) -> None:
    huge = b"x" * (5 * 1024 * 1024 + 1)
    response = await authenticated_client.post(
        "/profile/photo", files={"file": ("buyuk.png", huge, "image/png")}
    )
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE


async def test_empty_file_is_rejected(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post("/profile/photo", files=image(b""))
    assert response.status_code == 422


async def test_photo_endpoints_require_a_session(client: AsyncClient) -> None:
    """Görünürlük sunucuda uygulanır (Bölüm 7)."""
    assert (await client.post("/profile/photo", files=image())).status_code == 401
    assert (await client.delete("/profile/photo")).status_code == 401
