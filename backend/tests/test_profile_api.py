"""Profil uçları (şartname M2, Bölüm 10).

Kabul kriteri: *"Eksik profille etkinliğe başvurulamıyor ve eksiğin ne olduğu
yazıyor."*
"""

from collections.abc import Callable

from httpx import AsyncClient


async def seeded_ids(client: AsyncClient) -> tuple[int, list[int]]:
    """Başlangıç setinden bir sektör ve birkaç etiket kimliği."""
    sectors = (await client.get("/sectors")).json()
    categories = (await client.get("/tag-categories")).json()
    tag_ids = [tag["id"] for tag in categories[0]["tags"]]
    return sectors[0]["id"], tag_ids


async def test_new_profile_is_empty_and_cannot_apply(
    authenticated_client: AsyncClient,
) -> None:
    """Kayıt sırasında profil kaydı açılıyor ama boş."""
    response = await authenticated_client.get("/profile")
    assert response.status_code == 200

    profile = response.json()
    assert profile["full_name"] is None
    assert profile["completion_percent"] == 0
    assert profile["can_apply"] is False
    assert set(profile["missing_for_application"]) == {
        "full_name",
        "company",
        "sector",
        "offered_tags",
        "sought_tags",
    }


async def test_partial_update_keeps_other_fields(
    authenticated_client: AsyncClient,
) -> None:
    """Sihirbaz adım adım kaydediyor; bir adım diğerini silmemeli (M2)."""
    await authenticated_client.patch("/profile", json={"full_name": "Ayşe Yılmaz"})
    await authenticated_client.patch("/profile", json={"city": "İzmir"})

    profile = (await authenticated_client.get("/profile")).json()
    assert profile["full_name"] == "Ayşe Yılmaz"
    assert profile["city"] == "İzmir"


async def test_explicit_null_clears_a_field(authenticated_client: AsyncClient) -> None:
    await authenticated_client.patch("/profile", json={"title": "Genel Müdür"})
    await authenticated_client.patch("/profile", json={"title": None})

    profile = (await authenticated_client.get("/profile")).json()
    assert profile["title"] is None


async def test_completion_percent_rises_as_the_wizard_progresses(
    authenticated_client: AsyncClient,
) -> None:
    before = (await authenticated_client.get("/profile")).json()["completion_percent"]

    await authenticated_client.patch(
        "/profile", json={"full_name": "Ayşe Yılmaz", "title": "Kurucu", "city": "İzmir"}
    )
    after = (await authenticated_client.get("/profile")).json()["completion_percent"]

    assert after > before


async def test_profile_becomes_eligible_when_requirements_are_met(
    authenticated_client: AsyncClient,
) -> None:
    """Bölüm 10: eksikler tamamlanınca başvuru açılmalı."""
    sector_id, tag_ids = await seeded_ids(authenticated_client)
    company = await authenticated_client.post("/companies", json={"name": "Yılmaz Yazılım A.Ş."})

    response = await authenticated_client.patch(
        "/profile",
        json={
            "full_name": "Ayşe Yılmaz",
            "company_id": company.json()["id"],
            "sector_id": sector_id,
            "offered_tag_ids": tag_ids[:3],
            "sought_tag_ids": tag_ids[3:6],
        },
    )

    profile = response.json()
    assert profile["can_apply"] is True
    assert profile["missing_for_application"] == []
    assert len(profile["offered_tags"]) == 3
    assert len(profile["sought_tags"]) == 3
    assert profile["company"]["name"] == "Yılmaz Yazılım A.Ş."


async def test_two_tags_are_not_enough(authenticated_client: AsyncClient) -> None:
    """M2 en az üçer etiket istiyor."""
    _sector_id, tag_ids = await seeded_ids(authenticated_client)

    response = await authenticated_client.patch("/profile", json={"offered_tag_ids": tag_ids[:2]})
    assert "offered_tags" in response.json()["missing_for_application"]


async def test_same_tag_can_be_offered_and_sought(
    authenticated_client: AsyncClient,
) -> None:
    """Etiketler tek havuzdan geliyor; aynı etiket iki yönde de seçilebilir."""
    _sector_id, tag_ids = await seeded_ids(authenticated_client)

    response = await authenticated_client.patch(
        "/profile",
        json={"offered_tag_ids": tag_ids[:3], "sought_tag_ids": tag_ids[:3]},
    )
    profile = response.json()
    assert len(profile["offered_tags"]) == 3
    assert len(profile["sought_tags"]) == 3


async def test_replacing_tags_removes_the_previous_selection(
    authenticated_client: AsyncClient,
) -> None:
    _sector_id, tag_ids = await seeded_ids(authenticated_client)

    await authenticated_client.patch("/profile", json={"offered_tag_ids": tag_ids[:4]})
    response = await authenticated_client.patch("/profile", json={"offered_tag_ids": tag_ids[4:6]})

    selected = {tag["id"] for tag in response.json()["offered_tags"]}
    assert selected == set(tag_ids[4:6])


async def test_unknown_tag_is_rejected(authenticated_client: AsyncClient) -> None:
    """Olmayan etiket kimliği 500 değil, istemci hatası vermeli."""
    response = await authenticated_client.patch("/profile", json={"offered_tag_ids": [999_999]})
    assert response.status_code == 422


async def test_duplicate_tag_ids_are_collapsed(
    authenticated_client: AsyncClient,
) -> None:
    _sector_id, tag_ids = await seeded_ids(authenticated_client)

    response = await authenticated_client.patch(
        "/profile", json={"offered_tag_ids": [tag_ids[0], tag_ids[0], tag_ids[1]]}
    )
    assert len(response.json()["offered_tags"]) == 2


async def test_each_user_sees_only_their_own_profile(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Profil ucu kimlik parametresi almıyor; kaynak oturumdan türüyor (Bölüm 7)."""
    first = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "cok-gizli-sifre"}
    )
    second = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "cok-gizli-sifre"}
    )

    first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    await client.patch("/profile", json={"full_name": "Birinci"}, headers=first_headers)
    await client.patch("/profile", json={"full_name": "İkinci"}, headers=second_headers)

    assert (await client.get("/profile", headers=first_headers)).json()["full_name"] == "Birinci"
    assert (await client.get("/profile", headers=second_headers)).json()["full_name"] == "İkinci"


async def test_whitespace_does_not_count_as_filled(
    authenticated_client: AsyncClient,
) -> None:
    """Boşluk tuşuyla tamamlanma yüzdesi yükseltilememeli."""
    response = await authenticated_client.patch("/profile", json={"full_name": "   "})
    assert "full_name" in response.json()["missing_for_application"]


# --- Taksonomi -------------------------------------------------------------


async def test_seed_catalogue_is_available(authenticated_client: AsyncClient) -> None:
    """Etiket havuzu boşsa sihirbazın iki adımı hiç çalışmaz."""
    sectors = (await authenticated_client.get("/sectors")).json()
    categories = (await authenticated_client.get("/tag-categories")).json()

    assert len(sectors) >= 10
    assert len(categories) >= 5
    assert all(category["tags"] for category in categories)
