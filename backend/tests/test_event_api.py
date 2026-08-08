"""Etkinlik uçları (şartname M4, Bölüm 7, Bölüm 10).

Kabul kriterleri:
* *"Slot ve mola süreleri girildiğinde program anlık hesaplanıyor ve bitiş saati
  görünüyor."*
* *"Kontenjan kapasiteyi aşarsa uyarı çıkıyor."*
* *"Salon düzeni kurulmadan kayıtlar açılamıyor."*
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

START = datetime(2026, 9, 15, 10, 0, tzinfo=UTC)


def draft(**overrides) -> dict:
    return {
        "name": "Fintech Zirvesi",
        "starts_at": START.isoformat(),
        "slot_duration_minutes": 30,
        "break_duration_minutes": 10,
        "slot_count": 6,
        "capacity": 100,
        **overrides,
    }


async def create_draft(client: AsyncClient, **overrides) -> dict:
    response = await client.post("/events", json=draft(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def add_layout(client: AsyncClient, event_id: int, tables: int = 10) -> dict:
    response = await client.put(
        f"/events/{event_id}/layout/auto",
        json={"kind": "seated", "table_count": tables, "seat_count": 6},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- Taslak oluşturma ve güncelleme ----------------------------------------


async def test_new_event_starts_as_draft(authenticated_client: AsyncClient) -> None:
    event = await create_draft(authenticated_client)

    assert event["status"] == "draft"
    assert event["name"] == "Fintech Zirvesi"
    assert event["has_layout"] is False


async def test_partial_update_keeps_other_fields(
    authenticated_client: AsyncClient,
) -> None:
    """Sihirbazın bir adımı diğerinin verisini silmemeli (M4)."""
    event = await create_draft(authenticated_client)

    await authenticated_client.patch(
        f"/events/{event['id']}", json={"venue_name": "İzmir Fuar Alanı"}
    )
    response = await authenticated_client.patch(
        f"/events/{event['id']}", json={"description": "Yıllık fintech buluşması"}
    )

    updated = response.json()
    assert updated["venue_name"] == "İzmir Fuar Alanı"
    assert updated["description"] == "Yıllık fintech buluşması"
    assert updated["name"] == "Fintech Zirvesi"


async def test_event_list_shows_only_my_events(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Bölüm 7: başka organizatörlerin etkinlikleri görünmemeli."""
    first = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "cok-gizli-sifre"}
    )
    second = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "cok-gizli-sifre"}
    )
    first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    await client.post("/events", json=draft(name="Benim etkinliğim"), headers=first_headers)

    listed = await client.get("/events", headers=second_headers)
    assert listed.json() == []


# --- Program hesabı (Bölüm 10) ---------------------------------------------


async def test_schedule_is_calculated_in_the_response(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_draft(authenticated_client)

    schedule = event["schedule"]
    assert len(schedule) == 6
    assert schedule[0]["number"] == 1
    assert schedule[0]["starts_at"].startswith("2026-09-15T10:00")
    assert schedule[1]["starts_at"].startswith("2026-09-15T10:40")
    # 6×30 + 5×10 = 230 dakika
    assert event["total_minutes"] == 230
    assert event["ends_at"].startswith("2026-09-15T13:50")


async def test_schedule_follows_the_updated_durations(
    authenticated_client: AsyncClient,
) -> None:
    """Organizatör süreleri değiştirince program da değişmeli."""
    event = await create_draft(authenticated_client)

    response = await authenticated_client.patch(
        f"/events/{event['id']}",
        json={"slot_duration_minutes": 20, "break_duration_minutes": 5, "slot_count": 4},
    )
    updated = response.json()

    assert len(updated["schedule"]) == 4
    # 4×20 + 3×5 = 95
    assert updated["total_minutes"] == 95


# --- Kapasite uyarısı (M4) --------------------------------------------------


async def test_capacity_warning_when_quota_exceeds_seating(
    authenticated_client: AsyncClient,
) -> None:
    """*"Kontenjan kapasiteden büyükse organizatör uyarılır."*"""
    event = await create_draft(authenticated_client, capacity=100)
    # 10 masa × 6 sandalye = 60 < 100
    await add_layout(authenticated_client, event["id"], tables=10)

    response = await authenticated_client.get(f"/events/{event['id']}")
    summary = response.json()["capacity_summary"]

    assert summary["seating_capacity"] == 60
    assert summary["capacity"] == 100
    assert summary["exceeds_seating"] is True


async def test_no_warning_when_seating_is_enough(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_draft(authenticated_client, capacity=50)
    await add_layout(authenticated_client, event["id"], tables=10)

    response = await authenticated_client.get(f"/events/{event['id']}")
    assert response.json()["capacity_summary"]["exceeds_seating"] is False


async def test_capacity_warning_does_not_block_opening(
    authenticated_client: AsyncClient,
) -> None:
    """*"Bu bir engel değil uyarıdır, çünkü gelmeyecekler hesaba katılabilir."*"""
    event = await create_draft(authenticated_client, capacity=500)
    await authenticated_client.patch(
        f"/events/{event['id']}",
        json={"venue_name": "Fuar", "address": "Adres", "description": "Açıklama"},
    )
    await add_layout(authenticated_client, event["id"], tables=5)

    response = await authenticated_client.post(f"/events/{event['id']}/open-registration")
    assert response.status_code == 200
    assert response.json()["status"] == "registration_open"


# --- Kayıtları açma kapısı (Bölüm 10) ---------------------------------------


async def test_registration_cannot_open_without_a_layout(
    authenticated_client: AsyncClient,
) -> None:
    """*"Salon düzeni kurulmadan kayıtlar açılamıyor."*"""
    event = await create_draft(authenticated_client)

    response = await authenticated_client.post(f"/events/{event['id']}/open-registration")
    assert response.status_code == 409
    assert event["can_open_registration"] is False


async def test_registration_cannot_open_without_complete_info(
    authenticated_client: AsyncClient,
) -> None:
    """Temel bilgiler (yer, adres, açıklama) eksikse kayıtlar açılamaz."""
    event = await create_draft(authenticated_client)
    await add_layout(authenticated_client, event["id"])

    # Yer, adres ve açıklama eksik
    response = await authenticated_client.post(f"/events/{event['id']}/open-registration")
    assert response.status_code == 409
    assert "etkinlik bilgilerini" in response.json()["detail"]


async def test_registration_opens_once_a_layout_and_info_exist(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_draft(authenticated_client)
    await authenticated_client.patch(
        f"/events/{event['id']}",
        json={"venue_name": "İzmir Fuar Alanı", "address": "Adres 123", "description": "Detaylar"},
    )
    await add_layout(authenticated_client, event["id"])

    detail = (await authenticated_client.get(f"/events/{event['id']}")).json()
    assert detail["can_open_registration"] is True

    response = await authenticated_client.post(f"/events/{event['id']}/open-registration")
    assert response.json()["status"] == "registration_open"


# --- Yetki (Bölüm 7) --------------------------------------------------------


async def test_other_organisers_event_is_not_found(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """404 dönüyor, 403 değil: etkinliğin varlığı bile sızmamalı."""
    owner = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "cok-gizli-sifre"}
    )
    stranger = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "cok-gizli-sifre"}
    )
    owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}
    stranger_headers = {"Authorization": f"Bearer {stranger.json()['access_token']}"}

    created = await client.post("/events", json=draft(), headers=owner_headers)
    event_id = created.json()["id"]

    for request in (
        client.get(f"/events/{event_id}", headers=stranger_headers),
        client.patch(
            f"/events/{event_id}", json={"name": "Ele geçirildi"}, headers=stranger_headers
        ),
        client.post(f"/events/{event_id}/open-registration", headers=stranger_headers),
        client.get(f"/events/{event_id}/layout", headers=stranger_headers),
    ):
        assert (await request).status_code == 404


async def test_event_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events")).status_code == 401
    assert (await client.post("/events", json=draft())).status_code == 401


async def test_missing_event_is_not_found(authenticated_client: AsyncClient) -> None:
    assert (await authenticated_client.get("/events/999999")).status_code == 404


# --- Doğrulama --------------------------------------------------------------


async def test_invalid_durations_are_rejected(
    authenticated_client: AsyncClient,
) -> None:
    """Sıfır slot süresi geçerli bir program üretemez."""
    response = await authenticated_client.post("/events", json=draft(slot_duration_minutes=0))
    assert response.status_code == 422


async def test_deadline_can_be_set(authenticated_client: AsyncClient) -> None:
    event = await create_draft(authenticated_client)
    deadline = (START - timedelta(days=3)).isoformat()

    response = await authenticated_client.patch(
        f"/events/{event['id']}",
        json={"registration_deadline": deadline, "auto_approve_registrations": False},
    )
    updated = response.json()

    assert updated["registration_deadline"].startswith("2026-09-12")
    assert updated["auto_approve_registrations"] is False


async def test_organiser_can_delete_event(
    authenticated_client: AsyncClient,
) -> None:
    """Organizatör kendi etkinliğini silebilmeli."""
    event = await create_draft(authenticated_client)

    response = await authenticated_client.delete(f"/events/{event['id']}")
    assert response.status_code == 204

    get_resp = await authenticated_client.get(f"/events/{event['id']}")
    assert get_resp.status_code == 404
