"""Check-in ve planın yenilenmesi (şartname M10, 9.8, Bölüm 10).

Kabul kriteri: *"QR okunduğunda katılımcı geldi olarak işaretleniyor.
Gelmeyenler çıkarılıp plan güncellendiğinde, yeri değişenlerin listesi
organizatöre gösteriliyor."*

Son bölüm 9.10'un minimum değişim testini **gerçek veriyle** yapıyor: motor
tarafı Aşama 2'de sentetik veriyle sınanmıştı, uçtan uca ilk kez burada.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, AttendanceStatus, Registration
from app.services.attendance import started_slots
from app.services.schedule import build_schedule
from tests.test_matching_api import run_plan
from tests.test_registration_api import complete_profile, open_event, sign_up, use


def in_hours(hours: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


async def crowd(
    client: AsyncClient,
    emails: Callable[[], str],
    *,
    people: int = 6,
    tables: int = 3,
    seats: int = 2,
    slots: int = 3,
    starts_at: str | None = None,
) -> tuple[str, dict, list[str]]:
    """Kabul edilmiş katılımcıları olan bir etkinlik; jetonlar geri dönüyor."""
    organiser = await sign_up(client, emails())
    use(client, organiser)
    event = await open_event(
        client,
        name="Check-in Denemesi",
        capacity=people,
        slot_count=slots,
        **({"starts_at": starts_at} if starts_at else {}),
    )
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


async def my_qr(client: AsyncClient, event: dict) -> dict:
    response = await client.get(f"/events/{event['id']}/my-qr")
    assert response.status_code == 200, response.text
    return response.json()


async def scan(client: AsyncClient, event: dict, code: str):
    return await client.post(f"/events/{event['id']}/attendance/scan", json={"qr_code": code})


async def attendance(client: AsyncClient, event: dict, **params) -> dict:
    response = await client.get(f"/events/{event['id']}/attendance", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --- Giriş kodu ------------------------------------------------------------------


async def test_the_participant_reads_their_own_code(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Her kabul edilmiş katılımcı için benzersiz bir kod üretilir."* (M10)"""
    _organiser, event, tokens = await crowd(client, unique_email, people=3)
    use(client, tokens[0])

    body = await my_qr(client, event)

    assert body["qr_code"]
    assert len(body["qr_code"]) >= 16
    assert body["checked_in_at"] is None


async def test_codes_are_unique_per_participant(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, tokens = await crowd(client, unique_email, people=4)

    codes = set()
    for token in tokens:
        use(client, token)
        codes.add((await my_qr(client, event))["qr_code"])

    assert len(codes) == len(tokens)


async def test_a_stranger_has_no_code(client: AsyncClient, unique_email: Callable[[], str]) -> None:
    _organiser, event, _tokens = await crowd(client, unique_email, people=3)
    use(client, await sign_up(client, unique_email()))

    assert (await client.get(f"/events/{event['id']}/my-qr")).status_code == 404


# --- Okuma -------------------------------------------------------------------------


async def test_scanning_marks_the_person_present(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Bölüm 10: *"QR okunduğunda katılımcı geldi olarak işaretleniyor."*"""
    organiser, event, tokens = await crowd(client, unique_email, people=4)
    use(client, tokens[0])
    code = (await my_qr(client, event))["qr_code"]

    use(client, organiser)
    response = await scan(client, event, code)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["attendee"]["present"] is True
    assert body["attendee"]["full_name"] == "Katılımcı 0"
    assert body["attendee"]["checked_in_at"] is not None
    assert body["already_present"] is False
    assert body["present_count"] == 1
    assert body["expected_count"] == 3


async def test_scanning_twice_is_not_an_error(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Kapıda aynı kod iki kez okunabilir; zaman ilk okumada kalıyor."""
    organiser, event, tokens = await crowd(client, unique_email, people=3)
    use(client, tokens[0])
    code = (await my_qr(client, event))["qr_code"]

    use(client, organiser)
    first = (await scan(client, event, code)).json()
    second = (await scan(client, event, code)).json()

    assert second["already_present"] is True
    assert second["present_count"] == 1
    assert second["attendee"]["checked_in_at"] == first["attendee"]["checked_in_at"]


async def test_an_unknown_code_is_refused(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser, event, _tokens = await crowd(client, unique_email, people=3)
    use(client, organiser)

    response = await scan(client, event, "uydurma-kod")

    assert response.status_code == 404
    assert "giriş kodu yok" in response.json()["detail"]


async def test_another_events_code_is_refused(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Kod benzersiz ama okuma etkinlikle sınırlı.

    Hangi etkinliğe ait olduğunu söylemek başka bir organizatörün katılımcı
    listesi hakkında bilgi sızdırırdı.
    """
    _first_organiser, first_event, first_tokens = await crowd(client, unique_email, people=3)
    use(client, first_tokens[0])
    stolen = (await my_qr(client, first_event))["qr_code"]

    second_organiser, second_event, _second = await crowd(client, unique_email, people=3)
    use(client, second_organiser)

    response = await scan(client, second_event, stolen)

    assert response.status_code == 404
    assert "giriş kodu yok" in response.json()["detail"]


# --- Liste, sayaç, elle işaretleme -------------------------------------------------


async def test_the_counter_tracks_arrivals(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Sayaç sürekli görünür: kaç kişi geldi, kaç kişi bekleniyor."*"""
    organiser, event, tokens = await crowd(client, unique_email, people=4)

    before = await attendance(client, event)
    assert (before["accepted_count"], before["present_count"], before["expected_count"]) == (
        4,
        0,
        4,
    )

    for token in tokens[:2]:
        use(client, token)
        code = (await my_qr(client, event))["qr_code"]
        use(client, organiser)
        await scan(client, event, code)

    after = await attendance(client, event)
    assert (after["present_count"], after["expected_count"]) == (2, 2)


async def test_manual_marking_and_undo(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Elle arama da olmalı — telefonu bozulan, kodu bulamayan kişi
    listeden bulunup elle işaretlenebilir."* (M10)

    Geri alınabiliyor: yanlış kişi işaretlenmiş olabilir.
    """
    organiser, event, _tokens = await crowd(client, unique_email, people=3)
    use(client, organiser)
    listing = await attendance(client, event)
    person = listing["attendees"][0]

    marked = await client.post(
        f"/events/{event['id']}/attendance/{person['registration_id']}",
        json={"present": True},
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["present_count"] == 1

    undone = await client.post(
        f"/events/{event['id']}/attendance/{person['registration_id']}",
        json={"present": False},
    )
    assert undone.json()["present_count"] == 0
    row = next(
        item
        for item in undone.json()["attendees"]
        if item["registration_id"] == person["registration_id"]
    )
    assert row["present"] is False
    assert row["checked_in_at"] is None


async def test_search_folds_turkish_letters(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """ "İzmir" yazan da "izmir" yazan da aynı kişiyi bulmalı.

    `str.lower()` yetmiyor: "İ" küçültülünce noktalı i + birleşen nokta
    oluyor ve "i" ile eşleşmiyor.
    """
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = await open_event(client, capacity=4)
    await client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "seated", "table_count": 2, "seat_count": 3},
    )
    for name in ("İpek Şahin", "Oğuz Çelik"):
        use(client, await sign_up(client, unique_email()))
        await complete_profile(client, name)
        await client.post(f"/events/{event['id']}/registration")

    use(client, organiser)

    for needle in ("ipek", "İPEK", "İpek", "sahin", "Şahin"):
        found = await attendance(client, event, q=needle)
        names = [item["full_name"] for item in found["attendees"]]
        assert names == ["İpek Şahin"], f"{needle} → {names}"


async def test_the_counter_ignores_the_search_filter(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Arama yaparken "kaç kişi bekleniyor" bilgisi kaybolmamalı."""
    organiser, event, _tokens = await crowd(client, unique_email, people=4)
    use(client, organiser)

    filtered = await attendance(client, event, q="Katılımcı 1")

    assert len(filtered["attendees"]) == 1
    assert filtered["accepted_count"] == 4
    assert filtered["expected_count"] == 4


async def test_check_in_is_organiser_only(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    _organiser, event, tokens = await crowd(client, unique_email, people=3)
    use(client, tokens[0])

    assert (await client.get(f"/events/{event['id']}/attendance")).status_code == 404
    assert (await scan(client, event, "x")).status_code == 404
    assert (
        await client.post(f"/events/{event['id']}/attendance/1", json={"present": True})
    ).status_code == 404


async def test_check_in_requires_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events/1/attendance")).status_code == 401
    assert (await client.get("/events/1/my-qr")).status_code == 401
    assert (
        await client.post("/events/1/attendance/scan", json={"qr_code": "x"})
    ).status_code == 401


# --- Başlamış turlar (9.8) ----------------------------------------------------------


async def test_started_slots_are_derived_from_the_schedule(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Başlamış veya bitmiş slotlara dokunulmaz."* (9.8)

    Etkinlik iki saat önce başlamış: ilk turlar geçmişte kalmış.
    """
    from app.models import Event

    _organiser, event, _tokens = await crowd(
        client, unique_email, people=4, slots=6, starts_at=in_hours(-2)
    )
    stored = await session.get(Event, event["id"])

    started = started_slots(stored)
    schedule = build_schedule(
        starts_at=stored.starts_at,
        slot_count=stored.slot_count,
        slot_duration_minutes=stored.slot_duration_minutes,
        break_duration_minutes=stored.break_duration_minutes,
    )
    expected = {timing.number for timing in schedule.slots if timing.starts_at <= datetime.now(UTC)}

    assert started == expected
    assert started, "İki saat önce başlamış etkinlikte en az bir tur geçmiş olmalı."


async def test_a_future_event_has_no_started_slots(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    from app.models import Event

    _organiser, event, _tokens = await crowd(client, unique_email, people=4)
    stored = await session.get(Event, event["id"])

    assert started_slots(stored) == set()


# --- Minimum değişim modu (9.8, M10) ------------------------------------------------


async def mark_present(client: AsyncClient, event: dict, tokens: list[str], who: list[int]) -> None:
    """Verilen katılımcıları geldi olarak işaretler."""
    organiser_headers = dict(client.headers)
    for index in who:
        use(client, tokens[index])
        code = (await my_qr(client, event))["qr_code"]
        client.headers.update(organiser_headers)
        assert (await scan(client, event, code)).status_code == 200


async def test_refresh_needs_at_least_one_arrival(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Kimse okutulmadan "gelmeyenleri çıkar" denirse plan tamamen boşalır."""
    organiser, event, _tokens = await crowd(client, unique_email, people=6)
    use(client, organiser)
    await run_plan(client, session, event["id"])

    response = await client.post(f"/events/{event['id']}/plans", json={"minimal_change": True})

    assert response.status_code == 409
    assert "en az bir katılımcının geldiğini" in response.json()["detail"]


async def test_absent_people_are_not_seated(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Motor gelmeyenler çıkarılmış halde tekrar çalışır."* (M10)"""
    organiser, event, tokens = await crowd(client, unique_email, people=6, tables=3, seats=2)
    use(client, organiser)
    first = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{first['id']}/publish")

    # Dört kişi geldi, ikisi gelmedi.
    await mark_present(client, event, tokens, [0, 1, 2, 3])

    use(client, organiser)
    started = await client.post(f"/events/{event['id']}/plans", json={"minimal_change": True})
    assert started.status_code == 202, started.text
    from app.services.plan_runner import execute_plan

    await execute_plan(session, started.json()["id"])

    absent_ids = set(
        (
            await session.execute(
                select(Registration.id).where(
                    Registration.event_id == event["id"],
                    Registration.attendance == AttendanceStatus.ABSENT,
                )
            )
        ).scalars()
    )
    seated = set(
        (
            await session.execute(
                select(Assignment.registration_id).where(Assignment.plan_id == started.json()["id"])
            )
        ).scalars()
    )

    assert absent_ids, "İki kişi gelmemiş olmalıydı."
    assert not (absent_ids & seated), "Gelmeyen biri masaya oturmuş."


async def test_started_slots_are_untouched(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Sadece gelecek slotlar yeniden hesaplanır."* (9.8)"""
    from app.models import Event
    from app.services.plan_runner import execute_plan

    organiser, event, tokens = await crowd(
        client, unique_email, people=6, tables=3, seats=2, slots=6, starts_at=in_hours(-2)
    )
    use(client, organiser)
    first = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{first['id']}/publish")

    await mark_present(client, event, tokens, [0, 1, 2, 3])

    use(client, organiser)
    started = await client.post(f"/events/{event['id']}/plans", json={"minimal_change": True})
    second_id = started.json()["id"]
    await execute_plan(session, second_id)

    stored = await session.get(Event, event["id"])
    frozen = started_slots(stored)
    assert frozen, "Bu senaryoda en az bir tur donmuş olmalı."

    async def rows(plan_id: int) -> set[tuple[int, int, int]]:
        result = await session.execute(
            select(Assignment.slot_number, Assignment.table_id, Assignment.registration_id).where(
                Assignment.plan_id == plan_id, Assignment.slot_number.in_(frozen)
            )
        )
        return set(result.all())

    assert await rows(first["id"]) == await rows(second_id)


async def test_pinned_assignments_survive_the_refresh(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Sabitlenen atama, motor tekrar çalıştırılsa bile değişmez."* (M7)

    Aşama 8'de yazılmıştı ama motora ilk kez burada geçiyor.
    """
    from app.services.plan_runner import execute_plan

    organiser, event, tokens = await crowd(client, unique_email, people=6, tables=3, seats=2)
    use(client, organiser)
    first = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{first['id']}/publish")

    slot = (await client.get(f"/events/{event['id']}/plans/{first['id']}/slots/2")).json()
    table = next(item for item in slot["tables"] if item["occupants"])
    pinned = table["occupants"][0]
    await client.patch(
        f"/events/{event['id']}/plans/{first['id']}/assignments/{pinned['assignment_id']}",
        json={"is_pinned": True},
    )

    await mark_present(client, event, tokens, [0, 1, 2, 3, 4, 5])

    use(client, organiser)
    started = await client.post(f"/events/{event['id']}/plans", json={"minimal_change": True})
    second_id = started.json()["id"]
    await execute_plan(session, second_id)

    seat = (
        await session.execute(
            select(Assignment.table_id).where(
                Assignment.plan_id == second_id,
                Assignment.slot_number == 2,
                Assignment.registration_id == pinned["registration_id"],
            )
        )
    ).scalar_one_or_none()

    assert seat == table["table_id"], "Sabitlenmiş atama yeni planda kaymış."


async def test_changes_are_reported(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Bölüm 10: *"Yeri değişenlerin listesi organizatöre gösteriliyor."*"""
    from app.services.plan_runner import execute_plan

    organiser, event, tokens = await crowd(client, unique_email, people=6, tables=3, seats=2)
    use(client, organiser)
    first = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{first['id']}/publish")

    await mark_present(client, event, tokens, [0, 1, 2, 3])

    use(client, organiser)
    started = await client.post(f"/events/{event['id']}/plans", json={"minimal_change": True})
    second_id = started.json()["id"]
    await execute_plan(session, second_id)

    changes = (await client.get(f"/events/{event['id']}/plans/{second_id}/changes")).json()

    assert changes["previous_plan_id"] == first["id"]
    assert changes["moved_people"] > 0, "Gelmeyen iki kişi masadan kalkmış olmalı."
    for row in changes["changes"]:
        assert row["name"]
        assert row["slot_number"] >= 1
        # En az biri değişmiş olmalı; ikisi aynıysa satır listeye girmemeliydi.
        assert row["before"] != row["after"]


async def test_the_first_plan_has_no_changes(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Karşılaştırılacak bir öncesi yok."""
    organiser, event, _tokens = await crowd(client, unique_email, people=6)
    use(client, organiser)
    plan = await run_plan(client, session, event["id"])

    changes = (await client.get(f"/events/{event['id']}/plans/{plan['id']}/changes")).json()

    assert changes["previous_plan_id"] is None
    assert changes["changes"] == []
    assert changes["moved_people"] == 0


async def test_minimal_change_moves_few_people(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """9.10'un minimum değişim testi — **gerçek veriyle**.

    *"Motor sıfırdan çalışırsa herkesin planı değişir. Dün akşam masasını
    öğrenmiş olan kişi sabah bambaşka bir yere düşer. Kapıda kaos çıkar."*

    Motor tarafı Aşama 2'de sentetik veriyle sınanmıştı; uçtan uca ilk kez
    burada. Ölçüt: gelmeyenler dışındaki kişilerin **çoğunluğu** yerinde
    kalmalı.
    """
    from app.services.plan_runner import execute_plan

    people = 12
    organiser, event, tokens = await crowd(
        client, unique_email, people=people, tables=6, seats=2, slots=4
    )
    use(client, organiser)
    first = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{first['id']}/publish")

    # İki kişi gelmiyor.
    await mark_present(client, event, tokens, list(range(people - 2)))

    use(client, organiser)
    started = await client.post(f"/events/{event['id']}/plans", json={"minimal_change": True})
    second_id = started.json()["id"]
    await execute_plan(session, second_id)

    changes = (await client.get(f"/events/{event['id']}/plans/{second_id}/changes")).json()

    absent_ids = set(
        (
            await session.execute(
                select(Registration.id).where(
                    Registration.event_id == event["id"],
                    Registration.attendance == AttendanceStatus.ABSENT,
                )
            )
        ).scalars()
    )
    moved = {
        row["registration_id"]
        for row in changes["changes"]
        if row["registration_id"] not in absent_ids
    }
    present_count = people - len(absent_ids)

    # Sıfırdan çalıştırma neredeyse herkesi oynatırdı. Yarıdan azı yeterli
    # bir sınır: kesin sayı tohuma ve senaryoya bağlı.
    assert len(moved) < present_count / 2, (
        f"{present_count} gelen kişiden {len(moved)}'inin yeri değişti; "
        "minimum değişim modu çalışmıyor olabilir."
    )
