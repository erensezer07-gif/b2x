"""Görüşme talepleri (şartname M9, Bölüm 10).

Kabul kriteri: *"Talep hakkı sınırı çalışıyor. Kapanış zamanından sonra talep
gönderilemiyor. Talep edilen kişi kimin talep ettiğini göremiyor."*

Üçüncüsü bu dosyanın omurgası. Gelen talep diye bir uç yazılmadı; testler
**yazılmadığını** ve hiçbir yanıtın onu sızdırmadığını kanıtlıyor.

Son bölüm motoru bağlıyor: `meeting_requests` tablosu bugüne kadar hep boştu,
9.3'ün talep bonusu ilk kez gerçek veriyle çalışıyor.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, MeetingRequest, MeetingRequestStatus, Plan, PlanStatus
from tests.test_matching_api import run_plan, seed_event
from tests.test_registration_api import complete_profile, open_event, sign_up, use


def in_hours(hours: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


async def crowd(
    client: AsyncClient,
    emails: Callable[[], str],
    *,
    people: int = 4,
    quota: int = 3,
    tables: int = 3,
    seats: int = 2,
    slots: int = 3,
) -> tuple[str, dict, list[str]]:
    """Kabul edilmiş katılımcıları olan bir etkinlik.

    Jetonlar geri dönüyor: talep testleri kişilerin **adına** konuşmak
    zorunda; `seed_event` jetonları saklamıyor.
    """
    organiser = await sign_up(client, emails())
    use(client, organiser)
    event = await open_event(client, name="Talep Denemesi", capacity=people, slot_count=slots)
    # Talep hakkı yalnızca güncellemede var: sihirbazın ilk adımı taslak
    # açıyor, hak sonraki adımda belirleniyor (M4).
    await client.patch(f"/events/{event['id']}", json={"request_quota": quota})
    await client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "seated", "table_count": tables, "seat_count": seats},
    )

    tokens = []
    for number in range(people):
        token = await sign_up(client, emails())
        use(client, token)
        await complete_profile(client, f"Katılımcı {number}")
        joined = await client.post(f"/events/{event['id']}/registration")
        assert joined.status_code == 201, joined.text
        tokens.append(token)

    use(client, organiser)
    return organiser, event, tokens


async def participants(client: AsyncClient, event: dict, **params) -> dict:
    response = await client.get(f"/events/{event['id']}/participants", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def request_meeting(client: AsyncClient, event: dict, target: int):
    return await client.post(
        f"/events/{event['id']}/requests", json={"target_registration_id": target}
    )


def row(listing: dict, name: str) -> dict:
    return next(item for item in listing["participants"] if item["full_name"] == name)


# --- Katılımcı listesi (M9) ----------------------------------------------------


async def test_list_shows_the_four_fields_and_not_the_profile(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Listede ad, unvan, şirket, sektör görünür."*

    Tam profil burada yok: o yalnızca aynı masaya düşenler için (Bölüm 7).
    """
    _organiser, event, tokens = await crowd(client, unique_email)
    use(client, tokens[0])

    listing = await participants(client, event)
    person = listing["participants"][0]

    assert person["full_name"]
    assert person["title"]
    assert person["company"]
    assert person["sector"]
    for hidden in ("bio", "website", "linkedin_url", "offered_tags", "sought_tags", "city"):
        assert hidden not in person


async def test_the_list_never_contains_yourself(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, tokens = await crowd(client, unique_email, people=4)
    use(client, tokens[0])

    listing = await participants(client, event)

    assert len(listing["participants"]) == 3
    assert "Katılımcı 0" not in [item["full_name"] for item in listing["participants"]]


async def test_search_and_sector_filter(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Arama ve sektöre göre filtreleme var."*"""
    _organiser, event, tokens = await crowd(client, unique_email, people=4)
    use(client, tokens[0])

    found = await participants(client, event, q="Katılımcı 2")
    assert [item["full_name"] for item in found["participants"]] == ["Katılımcı 2"]

    # Şirket adından da bulunuyor; normalleştirme şirket servisiyle aynı.
    by_company = await participants(client, event, q="katilimci 3 ltd")
    assert [item["full_name"] for item in by_company["participants"]] == ["Katılımcı 3"]

    everyone = await participants(client, event)
    sector_id = None
    sectors = (await client.get("/sectors")).json()
    sector_id = sectors[0]["id"]
    filtered = await participants(client, event, sector_id=sector_id)
    assert len(filtered["participants"]) == len(everyone["participants"])

    empty = await participants(client, event, sector_id=sectors[-1]["id"])
    assert empty["participants"] == []


async def test_only_accepted_participants_are_listed(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Bekleyen başvuru sahibi henüz katılımcı değil (Bölüm 4 sözlüğü)."""
    organiser, event, tokens = await crowd(client, unique_email, people=3)
    use(client, organiser)
    await client.patch(f"/events/{event['id']}", json={"auto_approve_registrations": False})
    await client.patch(f"/events/{event['id']}", json={"capacity": 10})

    waiting = await sign_up(client, unique_email())
    use(client, waiting)
    await complete_profile(client, "Bekleyen Kişi")
    await client.post(f"/events/{event['id']}/registration")

    use(client, tokens[0])
    listing = await participants(client, event)

    assert "Bekleyen Kişi" not in [item["full_name"] for item in listing["participants"]]


# --- Talep gönderme -------------------------------------------------------------


async def test_sending_a_request(client: AsyncClient, unique_email: Callable[[], str]) -> None:
    _organiser, event, tokens = await crowd(client, unique_email, quota=3)
    use(client, tokens[0])
    listing = await participants(client, event)
    target = listing["participants"][0]

    response = await request_meeting(client, event, target["registration_id"])

    assert response.status_code == 201, response.text
    after = response.json()
    assert after["requests_used"] == 1
    assert after["requests_remaining"] == 2
    assert row(after, target["full_name"])["my_request_id"] is not None


async def test_the_same_person_cannot_be_requested_twice(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, tokens = await crowd(client, unique_email)
    use(client, tokens[0])
    target = (await participants(client, event))["participants"][0]["registration_id"]

    assert (await request_meeting(client, event, target)).status_code == 201
    again = await request_meeting(client, event, target)

    assert again.status_code == 409
    assert "zaten talep gönderdin" in again.json()["detail"]


async def test_the_quota_is_enforced(client: AsyncClient, unique_email: Callable[[], str]) -> None:
    """*"Kıtlık, insanı gerçekten istediğini seçmeye zorlar."* (M9)"""
    _organiser, event, tokens = await crowd(client, unique_email, people=5, quota=2)
    use(client, tokens[0])
    others = [
        item["registration_id"] for item in (await participants(client, event))["participants"]
    ]

    assert (await request_meeting(client, event, others[0])).status_code == 201
    assert (await request_meeting(client, event, others[1])).status_code == 201
    blocked = await request_meeting(client, event, others[2])

    assert blocked.status_code == 409
    assert "Talep hakkın doldu" in blocked.json()["detail"]
    assert (await participants(client, event))["requests_remaining"] == 0


async def test_you_cannot_request_yourself(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Liste zaten kendini göstermiyor; uç doğrudan çağrılsa da reddediyor."""
    _organiser, event, tokens = await crowd(client, unique_email)
    use(client, tokens[0])
    mine = (await client.get(f"/events/{event['id']}/public")).json()["my_registration"]

    response = await request_meeting(client, event, mine["id"])

    assert response.status_code == 409
    assert "Kendine talep" in response.json()["detail"]


async def test_a_non_participant_cannot_be_requested(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, tokens = await crowd(client, unique_email)
    use(client, tokens[0])

    response = await request_meeting(client, event, 999_999)

    assert response.status_code == 409
    assert "katılımcısı değil" in response.json()["detail"]


# --- Geri çekme ------------------------------------------------------------------


async def test_withdrawing_gives_the_quota_back(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Kıtlığın anlamı "aynı anda kaç kişiyi istiyorsun" (M9 kararı)."""
    _organiser, event, tokens = await crowd(client, unique_email, quota=1)
    use(client, tokens[0])
    others = [
        item["registration_id"] for item in (await participants(client, event))["participants"]
    ]

    sent = await request_meeting(client, event, others[0])
    request_id = row(sent.json(), "Katılımcı 1")["my_request_id"]
    assert (await request_meeting(client, event, others[1])).status_code == 409

    withdrawn = await client.delete(f"/events/{event['id']}/requests/{request_id}")

    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["requests_remaining"] == 1
    assert (await request_meeting(client, event, others[1])).status_code == 201


async def test_the_same_person_can_be_requested_again_after_withdrawing(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """İkili benzersizliği duruma bakmıyor; satır silinmiyor, canlandırılıyor."""
    _organiser, event, tokens = await crowd(client, unique_email)
    use(client, tokens[0])
    target = (await participants(client, event))["participants"][0]

    sent = await request_meeting(client, event, target["registration_id"])
    request_id = row(sent.json(), target["full_name"])["my_request_id"]
    await client.delete(f"/events/{event['id']}/requests/{request_id}")

    again = await request_meeting(client, event, target["registration_id"])
    assert again.status_code == 201, again.text

    rows = (
        (
            await session.execute(
                select(MeetingRequest).where(MeetingRequest.event_id == event["id"])
            )
        )
        .scalars()
        .all()
    )
    # Tek satır, yeniden canlandırılmış.
    assert len(rows) == 1
    assert rows[0].status == MeetingRequestStatus.ACTIVE


async def test_you_cannot_withdraw_someone_elses_request(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, tokens = await crowd(client, unique_email, people=4)
    use(client, tokens[0])
    target = (await participants(client, event))["participants"][0]
    sent = await request_meeting(client, event, target["registration_id"])
    request_id = row(sent.json(), target["full_name"])["my_request_id"]

    use(client, tokens[1])
    response = await client.delete(f"/events/{event['id']}/requests/{request_id}")

    assert response.status_code == 409
    assert "Böyle bir talebin yok" in response.json()["detail"]


# --- Kapanış zamanı ----------------------------------------------------------------


async def test_requests_close_at_the_deadline(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Talepler bir zamanda kapanır... Kapanmazsa plan hiç kilitlenemez."*"""
    organiser, event, tokens = await crowd(client, unique_email)
    use(client, tokens[0])
    target = (await participants(client, event))["participants"][0]
    sent = await request_meeting(client, event, target["registration_id"])
    request_id = row(sent.json(), target["full_name"])["my_request_id"]

    use(client, organiser)
    await client.patch(f"/events/{event['id']}", json={"requests_close_at": in_hours(-1)})

    use(client, tokens[0])
    listing = await participants(client, event)
    assert listing["requests_open"] is False

    other = listing["participants"][1]["registration_id"]
    blocked = await request_meeting(client, event, other)
    assert blocked.status_code == 409
    assert "kapandı" in blocked.json()["detail"]

    # Geri çekme de kapalı: açık bırakmak planı yeniden oynatırdı.
    withdrawn = await client.delete(f"/events/{event['id']}/requests/{request_id}")
    assert withdrawn.status_code == 409
    assert "geri çekilemez" in withdrawn.json()["detail"]


async def test_requests_stay_open_without_a_deadline(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, tokens = await crowd(client, unique_email)
    use(client, tokens[0])

    assert (await participants(client, event))["requests_open"] is True


# --- Görünürlük: talep edilen kimin istediğini göremiyor -----------------------------


async def test_the_target_never_learns_who_requested_them(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Bölüm 10: *"Talep edilen kişi kimin talep ettiğini göremiyor."*

    Gelen talep diye bir uç yazılmadı; bu test yanıtların da sızdırmadığını
    kanıtlıyor.
    """
    _organiser, event, tokens = await crowd(client, unique_email, people=3)

    use(client, tokens[0])
    others = (await participants(client, event))["participants"]
    target_id = others[0]["registration_id"]
    assert (await request_meeting(client, event, target_id)).status_code == 201

    # Hedef kendi listesine bakıyor: hiçbir satırda "bana talep geldi" yok.
    use(client, tokens[1])
    listing = await participants(client, event)

    assert listing["requests_used"] == 0
    assert all(item["my_request_id"] is None for item in listing["participants"])
    assert "incoming" not in str(listing)


async def test_endpoints_are_closed_to_outsiders(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, _tokens = await crowd(client, unique_email)
    use(client, await sign_up(client, unique_email()))

    assert (await client.get(f"/events/{event['id']}/participants")).status_code == 404
    assert (await request_meeting(client, event, 1)).status_code == 404
    assert (await client.delete(f"/events/{event['id']}/requests/1")).status_code == 404


async def test_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events/1/participants")).status_code == 401
    assert (
        await client.post("/events/1/requests", json={"target_registration_id": 2})
    ).status_code == 401
    assert (await client.delete("/events/1/requests/1")).status_code == 401


# --- Motor bağlantısı (9.3) ------------------------------------------------------


async def test_a_mutual_request_reaches_the_engine(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"A, B'yi istiyor ve B de A'yı istiyorsa bu neredeyse kesin
    eşleşmedir."* (M9)

    `meeting_requests` tablosu bugüne kadar hep boştu; 9.3'ün talep bonusu
    ilk kez gerçek veriyle çalışıyor.
    """
    organiser, event, tokens = await crowd(
        client, unique_email, people=6, tables=3, seats=2, slots=3
    )

    use(client, tokens[0])
    listing = await participants(client, event)
    partner = row(listing, "Katılımcı 5")
    assert (await request_meeting(client, event, partner["registration_id"])).status_code == 201

    use(client, tokens[5])
    back = row(await participants(client, event), "Katılımcı 0")
    assert (await request_meeting(client, event, back["registration_id"])).status_code == 201

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])

    assert plan["total_requests"] == 2
    assert plan["satisfied_requests"] == 2, plan["unmet_requests"]
    assert plan["unmet_requests"] == []

    # İkisi gerçekten aynı masaya düşmüş mü — doğrudan atamalardan.
    seats = (
        await session.execute(
            select(Assignment.slot_number, Assignment.table_id, Assignment.registration_id).where(
                Assignment.plan_id == plan["id"]
            )
        )
    ).all()
    together = {
        (slot, table): {registration for s, t, registration in seats if (s, t) == (slot, table)}
        for slot, table, _r in seats
    }
    pair = {partner["registration_id"], back["registration_id"]}
    assert any(pair <= people for people in together.values())


async def test_the_matching_check_counts_requests(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Kontrol listesindeki talep sayısı ilk kez sıfırdan farklı (M6)."""
    organiser, event, tokens = await crowd(client, unique_email, people=4)

    use(client, tokens[0])
    target = (await participants(client, event))["participants"][0]
    await request_meeting(client, event, target["registration_id"])

    use(client, organiser)
    check = (await client.get(f"/events/{event['id']}/matching-check")).json()
    assert check["request_count"] == 1


# --- Karşılanmayan talepler (organizatör, M9) -----------------------------------------


async def test_an_unmet_mutual_request_is_reported_with_a_fixable_slot(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Organizatör plan ekranında karşılanmayan talepleri görür."*

    Karşılıklı talep kuruluyor, sonra ikisi elle ayrılıyor: plan özeti
    kaçırılan ikiliyi ve hangi turda düzeltilebileceğini söylüyor.
    """
    organiser, event, tokens = await crowd(
        client, unique_email, people=6, tables=3, seats=2, slots=3
    )

    use(client, tokens[0])
    partner = row(await participants(client, event), "Katılımcı 5")
    await request_meeting(client, event, partner["registration_id"])
    use(client, tokens[5])
    back = row(await participants(client, event), "Katılımcı 0")
    await request_meeting(client, event, back["registration_id"])

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])
    assert plan["satisfied_requests"] == 2

    # Organizatör ikisini elle ayırıyor: her turda birini başkasıyla takas et.
    pair = {partner["registration_id"], back["registration_id"]}
    for slot_number in (1, 2, 3):
        slot = (
            await client.get(f"/events/{event['id']}/plans/{plan['id']}/slots/{slot_number}")
        ).json()
        shared = next(
            (
                table
                for table in slot["tables"]
                if pair <= {person["registration_id"] for person in table["occupants"]}
            ),
            None,
        )
        if shared is None:
            continue
        outsider = next(
            person
            for table in slot["tables"]
            for person in table["occupants"]
            if person["registration_id"] not in pair
        )
        await client.post(
            f"/events/{event['id']}/plans/{plan['id']}/swap",
            json={
                "slot_number": slot_number,
                "assignment_id": shared["occupants"][0]["assignment_id"],
                "target_assignment_id": outsider["assignment_id"],
            },
        )

    refreshed = (await client.get(f"/events/{event['id']}/plans/{plan['id']}")).json()

    assert refreshed["satisfied_requests"] == 0
    unmet = refreshed["unmet_requests"]
    assert len(unmet) == 1, unmet
    assert unmet[0]["mutual"] is True
    assert {unmet[0]["requester_name"], unmet[0]["target_name"]} == {
        "Katılımcı 0",
        "Katılımcı 5",
    }
    # Takasla düzeltilebilecek bir tur gösteriliyor.
    assert unmet[0]["fixable_slot"] in (1, 2, 3)


async def test_a_one_way_request_is_marked_as_such(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Tek taraflı talep de listede ama `mutual` yanlış.

    M9: zorlanması önerilmiyor; arayüz ikisini ayrı gösteriyor.
    """
    organiser, event, tokens = await crowd(
        client, unique_email, people=6, tables=3, seats=2, slots=1
    )

    use(client, tokens[0])
    listing = await participants(client, event)
    # Tek turda altı kişiden yalnızca ikisi buluşabiliyor; talep büyük
    # olasılıkla karşılanmayacak.
    for person in listing["participants"][:3]:
        await request_meeting(client, event, person["registration_id"])

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])

    for item in plan["unmet_requests"]:
        assert item["mutual"] is False


async def test_a_satisfied_request_is_not_reported(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Karşılanmış talebin operasyonel karşılığı yok; listede yer almıyor."""
    organiser, event, tokens = await crowd(
        client, unique_email, people=4, tables=2, seats=2, slots=3
    )

    use(client, tokens[0])
    partner = row(await participants(client, event), "Katılımcı 3")
    await request_meeting(client, event, partner["registration_id"])

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])

    if plan["satisfied_requests"] == 1:
        assert plan["unmet_requests"] == []
    else:
        assert len(plan["unmet_requests"]) == 1


async def test_a_plan_without_requests_reports_nothing(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)
    plan = await run_plan(client, session, event["id"])

    assert plan["total_requests"] == 0
    assert plan["unmet_requests"] == []


async def test_the_participant_never_sees_unmet_requests(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Karşılanmayan talepler organizatöre özel.

    Katılımcının plan yanıtı `plan.py` şemasını hiç kullanmıyor; bu test onu
    kilitliyor.
    """
    organiser, event, tokens = await crowd(
        client, unique_email, people=4, tables=2, seats=2, slots=2
    )
    use(client, tokens[0])
    target = (await participants(client, event))["participants"][0]
    await request_meeting(client, event, target["registration_id"])

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")

    use(client, tokens[0])
    mine = (await client.get(f"/events/{event['id']}/my-plan")).json()

    assert "unmet_requests" not in str(mine)
    assert (await client.get(f"/events/{event['id']}/plans/{plan['id']}")).status_code == 404


async def test_published_plans_keep_the_summary(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Yayınlanmış planın özeti de karşılanmayan talepleri taşıyor."""
    organiser, event, tokens = await crowd(
        client, unique_email, people=4, tables=2, seats=2, slots=2
    )
    use(client, organiser)
    plan = await run_plan(client, session, event["id"])
    published = await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")

    assert published.status_code == 200
    assert published.json()["unmet_requests"] == []

    stored = (
        await session.execute(
            select(Plan).where(Plan.event_id == event["id"], Plan.status == PlanStatus.PUBLISHED)
        )
    ).scalar_one()
    assert stored.id == plan["id"]
