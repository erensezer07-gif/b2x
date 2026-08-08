"""Etkinlik keşfi ve başvuru (şartname M3, Bölüm 10).

Kabul kriteri: *"Eksik profille etkinliğe başvurulamıyor ve eksiğin ne olduğu
yazıyor."* Aşama 3'te bu kural yalnızca hesaplanıyordu; burada gerçekten
engelliyor.

Testler iki kullanıcıyla çalışıyor: aynı istemci üzerinde jeton değiştiriliyor.
Rol etkinliğe göre belirlendiği için (Bölüm 7) ayrı bir "organizatör hesabı"
kavramı yok — organizatör de sadece bir kullanıcı.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from tests.test_profile_api import seeded_ids


def in_days(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def sign_up(client: AsyncClient, email: str) -> str:
    """Yeni kullanıcı açar ve erişim jetonunu döner."""
    response = await client.post(
        "/auth/register", json={"email": email, "password": "cok-gizli-sifre"}
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def use(client: AsyncClient, token: str) -> None:
    client.headers["Authorization"] = f"Bearer {token}"


async def complete_profile(client: AsyncClient, name: str) -> None:
    """Başvuru için yeterli profil: ad, şirket, sektör, üçer etiket (M2)."""
    sector_id, tag_ids = await seeded_ids(client)
    company = await client.post("/companies", json={"name": f"{name} Ltd."})
    response = await client.patch(
        "/profile",
        json={
            "full_name": name,
            "title": "Kurucu",
            "company_id": company.json()["id"],
            "sector_id": sector_id,
            "offered_tag_ids": tag_ids[:3],
            "sought_tag_ids": tag_ids[3:6],
        },
    )
    assert response.json()["can_apply"] is True, response.text


async def open_event(client: AsyncClient, **overrides) -> dict:
    """Kayıtları açılmış bir etkinlik: temel alanlar, salon düzeni, açılış."""
    body = {
        "name": "İhracat Forumu",
        "starts_at": in_days(30),
        "slot_count": 6,
        "capacity": 10,
        **overrides,
    }
    event = (await client.post("/events", json=body)).json()

    await client.patch(
        f"/events/{event['id']}",
        json={
            "venue_name": "İzmir Fuar Alanı",
            "address": "Fuar Cad. No:1",
            "description": "Detaylı açıklama metni",
        },
    )

    layout = await client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "seated", "table_count": 4, "seat_count": 6},
    )
    assert layout.status_code == 200, layout.text

    opened = await client.post(f"/events/{event['id']}/open-registration")
    assert opened.status_code == 200, opened.text
    return opened.json()


async def two_users(client: AsyncClient, emails: Callable[[], str]) -> tuple[str, str]:
    """Organizatör ve profili tamamlanmış bir katılımcı."""
    organiser = await sign_up(client, emails())
    applicant = await sign_up(client, emails())

    use(client, applicant)
    await complete_profile(client, "Ayşe Yılmaz")

    use(client, organiser)
    return organiser, applicant


# --- Keşif -------------------------------------------------------------------


async def test_discover_hides_drafts_and_past_events(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Yaklaşan etkinliklerin listesi."* Taslak ve geçmiş listede yok."""
    organiser, applicant = await two_users(client, unique_email)

    await client.post("/events", json={"name": "Taslak", "starts_at": in_days(20)})
    await open_event(client, name="Açık Etkinlik")
    past = (await client.post("/events", json={"name": "Geçmiş", "starts_at": in_days(-5)})).json()
    await client.put(
        f"/events/{past['id']}/layout/auto",
        json={"kind": "seated", "table_count": 2, "seat_count": 6},
    )
    await client.post(f"/events/{past['id']}/open-registration")

    use(client, applicant)
    names = [card["name"] for card in (await client.get("/events/discover")).json()]

    assert "Açık Etkinlik" in names
    assert "Taslak" not in names
    assert "Geçmiş" not in names


async def test_discover_card_carries_my_application_status(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Her kart: ad, tarih, yer, kalan kontenjan, başvuru durumu."*"""
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client, capacity=5)

    use(client, applicant)
    before = next(
        card for card in (await client.get("/events/discover")).json() if card["id"] == event["id"]
    )
    assert before["my_registration"] is None
    assert before["remaining_capacity"] == 5
    assert before["is_open"] is True

    await client.post(f"/events/{event['id']}/registration")

    after = next(
        card for card in (await client.get("/events/discover")).json() if card["id"] == event["id"]
    )
    assert after["my_registration"]["status"] == "accepted"
    assert after["remaining_capacity"] == 4


async def test_public_detail_hides_organiser_fields(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Katılımcı organizatörün ayarlarını görmemeli (Bölüm 7)."""
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)

    use(client, applicant)
    detail = (await client.get(f"/events/{event['id']}/public")).json()

    assert "auto_approve_registrations" not in detail
    assert "request_quota" not in detail
    assert "capacity_summary" not in detail
    # *"Program (slot saatleri hesaplanmış halde)"* katılımcıya gösteriliyor.
    assert len(detail["schedule"]) == 6
    assert detail["accepted_count"] == 0


async def test_draft_event_is_not_visible_to_others(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    draft = (await client.post("/events", json={"name": "Taslak", "starts_at": in_days(20)})).json()

    use(client, applicant)
    assert (await client.get(f"/events/{draft['id']}/public")).status_code == 404
    assert (await client.post(f"/events/{draft['id']}/registration")).status_code == 404


# --- Başvuru kapıları ---------------------------------------------------------


async def test_incomplete_profile_cannot_apply_and_learns_why(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Bölüm 10: *"Eksik profille etkinliğe başvurulamıyor ve eksiğin ne olduğu
    yazıyor."*"""
    organiser = await sign_up(client, unique_email())
    stranger = await sign_up(client, unique_email())

    use(client, organiser)
    event = await open_event(client)

    use(client, stranger)
    response = await client.post(f"/events/{event['id']}/registration")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert set(detail["missing_for_application"]) == {
        "full_name",
        "company",
        "sector",
        "offered_tags",
        "sought_tags",
    }


async def test_auto_approval_accepts_immediately(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)

    use(client, applicant)
    response = await client.post(f"/events/{event['id']}/registration")

    assert response.status_code == 201
    assert response.json()["my_registration"]["status"] == "accepted"


async def test_manual_approval_leaves_the_application_pending(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)
    await client.patch(f"/events/{event['id']}", json={"auto_approve_registrations": False})

    use(client, applicant)
    response = await client.post(f"/events/{event['id']}/registration")

    assert response.json()["my_registration"]["status"] == "pending"
    # Bekleyen başvuru kontenjanı doldurmuyor.
    assert response.json()["remaining_capacity"] == event["capacity"]


async def test_second_application_is_refused(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)

    use(client, applicant)
    await client.post(f"/events/{event['id']}/registration")
    again = await client.post(f"/events/{event['id']}/registration")

    assert again.status_code == 409
    assert "zaten" in again.json()["detail"]


async def test_withdrawing_frees_the_seat_and_allows_reapplying(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Geri çekme satırı silmiyor, durumu iptale çeviriyor."""
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client, capacity=3)

    use(client, applicant)
    await client.post(f"/events/{event['id']}/registration")

    withdrawn = await client.delete(f"/events/{event['id']}/registration")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["my_registration"] is None
    assert withdrawn.json()["remaining_capacity"] == 3

    again = await client.post(f"/events/{event['id']}/registration")
    assert again.status_code == 201
    assert again.json()["my_registration"]["status"] == "accepted"


async def test_withdrawing_without_applying_is_not_found(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)

    use(client, applicant)
    assert (await client.delete(f"/events/{event['id']}/registration")).status_code == 404


async def test_full_capacity_closes_applications(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Kontenjan dolduysa ... başvuru kapanır."*"""
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = await open_event(client, capacity=1)

    first = await sign_up(client, unique_email())
    use(client, first)
    await complete_profile(client, "İlk Katılımcı")
    assert (await client.post(f"/events/{event['id']}/registration")).status_code == 201

    second = await sign_up(client, unique_email())
    use(client, second)
    await complete_profile(client, "İkinci Katılımcı")
    response = await client.post(f"/events/{event['id']}/registration")

    assert response.status_code == 409
    assert "Kontenjan" in response.json()["detail"]

    card = next(
        item for item in (await client.get("/events/discover")).json() if item["id"] == event["id"]
    )
    assert card["is_open"] is False
    assert card["remaining_capacity"] == 0


async def test_passed_deadline_closes_applications(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"...veya son başvuru tarihi geçtiyse başvuru kapanır."*"""
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)
    await client.patch(f"/events/{event['id']}", json={"registration_deadline": in_days(-1)})

    use(client, applicant)
    response = await client.post(f"/events/{event['id']}/registration")

    assert response.status_code == 409
    assert "Son başvuru tarihi" in response.json()["detail"]


async def test_closed_registration_refuses_applications(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = (await client.post("/events", json={"name": "Kapalı", "starts_at": in_days(20)})).json()
    await client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "seated", "table_count": 2, "seat_count": 6},
    )
    # Kayıtlar hiç açılmadı: etkinlik taslak. Taslak dışarıya görünmez.
    use(client, applicant)
    assert (await client.post(f"/events/{event['id']}/registration")).status_code == 404


async def test_organiser_cannot_apply_to_their_own_event(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Aynı kişi aynı etkinlikte iki rolde olamaz (Bölüm 7)."""
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    await complete_profile(client, "Organizatör Kişi")
    event = await open_event(client)

    response = await client.post(f"/events/{event['id']}/registration")
    assert response.status_code == 409
    assert "Kendi düzenlediğin" in response.json()["detail"]


async def test_qr_code_is_generated_and_unique(
    client: AsyncClient, unique_email: Callable[[], str], session
) -> None:
    """Şartname Bölüm 6: *"QR kodu (her katılımcı için benzersiz)."*"""
    from sqlalchemy import select

    from app.models import Registration

    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = await open_event(client)

    for name in ("Bir Kişi", "İki Kişi"):
        token = await sign_up(client, unique_email())
        use(client, token)
        await complete_profile(client, name)
        assert (await client.post(f"/events/{event['id']}/registration")).status_code == 201

    stored = await session.execute(
        select(Registration.qr_code).where(Registration.event_id == event["id"])
    )
    codes = stored.scalars().all()
    assert len(codes) == 2
    assert all(code for code in codes)
    assert len(set(codes)) == 2


# --- Organizatör: başvuru yönetimi -------------------------------------------


async def test_organiser_sees_applicants_with_their_profiles(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Organizatör kimi kabul ettiğini görmeden karar veremez (Bölüm 7)."""
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)
    await client.patch(f"/events/{event['id']}", json={"auto_approve_registrations": False})

    use(client, applicant)
    await client.post(f"/events/{event['id']}/registration")

    use(client, organiser)
    summary = (await client.get(f"/events/{event['id']}/registrations")).json()

    assert summary["pending_count"] == 1
    assert summary["accepted_count"] == 0
    row = summary["registrations"][0]
    assert row["status"] == "pending"
    assert row["applicant"]["full_name"] == "Ayşe Yılmaz"
    assert row["applicant"]["company"]["name"] == "Ayşe Yılmaz Ltd."
    assert row["applicant"]["sector"] is not None


async def test_approve_and_reject_move_the_application(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)
    await client.patch(f"/events/{event['id']}", json={"auto_approve_registrations": False})

    use(client, applicant)
    await client.post(f"/events/{event['id']}/registration")

    use(client, organiser)
    listing = (await client.get(f"/events/{event['id']}/registrations")).json()
    registration_id = listing["registrations"][0]["id"]

    approved = await client.post(f"/events/{event['id']}/registrations/{registration_id}/approve")
    assert approved.json()["accepted_count"] == 1
    assert approved.json()["pending_count"] == 0

    rejected = await client.post(f"/events/{event['id']}/registrations/{registration_id}/reject")
    assert rejected.json()["rejected_count"] == 1
    assert rejected.json()["accepted_count"] == 0

    use(client, applicant)
    detail = (await client.get(f"/events/{event['id']}/public")).json()
    assert detail["my_registration"]["status"] == "rejected"


async def test_approval_cannot_exceed_capacity(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Elle onayda bekleyenler kontenjanı doldurmuyor; kapı onayda gerekli."""
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = await open_event(client, capacity=1)
    await client.patch(f"/events/{event['id']}", json={"auto_approve_registrations": False})

    for name in ("Bir Kişi", "İki Kişi"):
        token = await sign_up(client, unique_email())
        use(client, token)
        await complete_profile(client, name)
        assert (await client.post(f"/events/{event['id']}/registration")).status_code == 201

    use(client, organiser)
    listing = (await client.get(f"/events/{event['id']}/registrations")).json()
    assert listing["pending_count"] == 2

    first, second = (row["id"] for row in listing["registrations"])
    assert (
        await client.post(f"/events/{event['id']}/registrations/{first}/approve")
    ).status_code == 200

    blocked = await client.post(f"/events/{event['id']}/registrations/{second}/approve")
    assert blocked.status_code == 409
    assert "Kontenjan doldu" in blocked.json()["detail"]


async def test_status_filter_narrows_the_list(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)

    use(client, applicant)
    await client.post(f"/events/{event['id']}/registration")

    use(client, organiser)
    accepted = await client.get(f"/events/{event['id']}/registrations?status=accepted")
    pending = await client.get(f"/events/{event['id']}/registrations?status=pending")

    assert len(accepted.json()["registrations"]) == 1
    assert pending.json()["registrations"] == []


async def test_withdrawn_applications_are_hidden_from_the_organiser(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)

    use(client, applicant)
    await client.post(f"/events/{event['id']}/registration")
    await client.delete(f"/events/{event['id']}/registration")

    use(client, organiser)
    summary = (await client.get(f"/events/{event['id']}/registrations")).json()
    assert summary["registrations"] == []
    assert summary["accepted_count"] == 0


# --- Görünürlük ---------------------------------------------------------------


async def test_registrations_of_another_event_are_not_found(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Bölüm 7: başkasının etkinliğine 404, 403 değil."""
    organiser, applicant = await two_users(client, unique_email)
    event = await open_event(client)

    use(client, applicant)
    await client.post(f"/events/{event['id']}/registration")
    assert (await client.get(f"/events/{event['id']}/registrations")).status_code == 404


async def test_discovery_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events/discover")).status_code == 401
    assert (await client.get("/events/1/public")).status_code == 401
    assert (await client.post("/events/1/registration")).status_code == 401
    assert (await client.get("/events/1/registrations")).status_code == 401
