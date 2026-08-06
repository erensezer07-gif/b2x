"""Şirket uçları (şartname Bölüm 6, Bölüm 10).

Kabul kriteri: *"Şirket adı seçildiğinde mevcut şirketlerle eşleşiyor, aynı
şirket iki kez oluşturulmuyor."*

Bu kural sadece derli toplu veri meselesi değil: aynı şirketten iki kişinin aynı
masaya oturmaması kuralının tamamı şirket kimliğinin tekilliğine dayanıyor (9.5).
"""

from httpx import AsyncClient


async def test_creating_a_company_returns_it(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post("/companies", json={"name": "ABC Yazılım"})
    assert response.status_code == 201
    assert response.json()["name"] == "ABC Yazılım"


async def test_same_company_written_differently_gets_one_identity(
    authenticated_client: AsyncClient,
) -> None:
    """Şartnamenin verdiği üç yazım tek kimliğe düşmeli."""
    identifiers = set()
    for written in ("ABC Yazılım", "ABC Yazılım A.Ş.", "abc yazilim"):
        response = await authenticated_client.post("/companies", json={"name": written})
        identifiers.add(response.json()["id"])

    assert len(identifiers) == 1


async def test_first_spelling_is_the_one_shown(
    authenticated_client: AsyncClient,
) -> None:
    """Kullanıcı kendi yazdığını değil, kayıtlı olanı görür — kimlik tek olsun diye."""
    await authenticated_client.post("/companies", json={"name": "ABC Yazılım"})
    second = await authenticated_client.post("/companies", json={"name": "abc yazilim a.ş."})
    assert second.json()["name"] == "ABC Yazılım"


async def test_different_companies_stay_apart(
    authenticated_client: AsyncClient,
) -> None:
    first = await authenticated_client.post("/companies", json={"name": "ABC Yazılım"})
    second = await authenticated_client.post("/companies", json={"name": "ABC Tekstil"})
    assert first.json()["id"] != second.json()["id"]


async def test_search_finds_by_normalised_form(
    authenticated_client: AsyncClient,
) -> None:
    """Kullanıcı "abc yazilim" yazınca "ABC Yazılım A.Ş." çıkmalı (Bölüm 6)."""
    await authenticated_client.post("/companies", json={"name": "ABC Yazılım A.Ş."})

    response = await authenticated_client.get("/companies", params={"q": "abc yazilim"})
    assert response.status_code == 200
    assert any(item["name"] == "ABC Yazılım A.Ş." for item in response.json())


async def test_search_ignores_turkish_letter_differences(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post("/companies", json={"name": "Işık Enerji"})

    response = await authenticated_client.get("/companies", params={"q": "isik"})
    assert any(item["name"] == "Işık Enerji" for item in response.json())


async def test_empty_query_returns_nothing(authenticated_client: AsyncClient) -> None:
    """Boş arama tüm şirketleri dökmemeli."""
    await authenticated_client.post("/companies", json={"name": "ABC Yazılım"})
    response = await authenticated_client.get("/companies", params={"q": "   "})
    assert response.json() == []


async def test_blank_name_is_rejected(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post("/companies", json={"name": ""})
    assert response.status_code == 422
