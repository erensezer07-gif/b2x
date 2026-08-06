"""Motorun veritabanına bağlanması (şartname M6, 5.4, 9.2).

Motorun kendisi Aşama 2'de test edildi; buradaki testler **dönüşümü** sınıyor.
9.2'nin uyarısı: indeks kayması eşleştirmeyi bozar ama hata vermez, aylar
sonra fark edilir. Bu yüzden testler kimlik→indeks→kimlik yolculuğunu uçtan
uca kontrol ediyor.

İş kuyruğu testlerde çalışmıyor; `execute_plan` doğrudan çağrılıyor. Kuyruğun
kendisi altyapı, ürün mantığı değil.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Event, JobStatus, Layout, MatchReason, Plan, Table
from app.services.matching import (
    CAPACITY_BELOW_PARTICIPANTS,
    INCOMPLETE_PROFILES,
    NO_PARTICIPANTS,
    REQUESTS_STILL_OPEN,
    build_engine_input,
)
from app.services.plan_runner import execute_plan
from tests.test_registration_api import (
    complete_profile,
    in_days,
    open_event,
    sign_up,
    use,
)


async def seed_event(
    client: AsyncClient,
    emails: Callable[[], str],
    *,
    participants: int = 6,
    tables: int = 3,
    seats: int = 4,
    slots: int = 3,
    complete: bool = True,
) -> tuple[str, dict]:
    """Kabul edilmiş katılımcıları olan bir etkinlik kurar.

    Otomatik onay açık; kabul edilmiş başvuru üretmenin en kısa yolu.
    """
    organiser = await sign_up(client, emails())
    use(client, organiser)
    event = await open_event(
        client,
        name="Eşleştirme Denemesi",
        capacity=max(participants, 1),
        slot_count=slots,
    )
    await client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "seated", "table_count": tables, "seat_count": seats},
    )

    for number in range(participants):
        token = await sign_up(client, emails())
        use(client, token)
        if complete:
            await complete_profile(client, f"Katılımcı {number}")
        else:
            await client.patch("/profile", json={"full_name": f"Katılımcı {number}"})
        response = await client.post(f"/events/{event['id']}/registration")
        assert response.status_code in (201, 422), response.text

    use(client, organiser)
    return organiser, event


async def run_plan(client: AsyncClient, session: AsyncSession, event_id: int) -> dict:
    """Planı açar ve motoru senkron çalıştırır."""
    started = await client.post(f"/events/{event_id}/plans", json={})
    assert started.status_code == 202, started.text
    plan_id = started.json()["id"]

    await execute_plan(session, plan_id)

    finished = await client.get(f"/events/{event_id}/plans/{plan_id}")
    assert finished.status_code == 200, finished.text
    return finished.json()


# --- Dönüşüm -----------------------------------------------------------------


async def test_conversion_indexes_are_contiguous_and_ordered(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """9.2: indeksler 0'dan başlayıp sıralı olmalı; motor bunu doğruluyor."""
    _organiser, event = await seed_event(client, unique_email, participants=5, tables=2)

    stored = await session.get(Event, event["id"])
    context = await build_engine_input(session, stored)

    assert len(context.engine_input.participants) == 5
    assert [p.index for p in context.engine_input.participants] == [0, 1, 2, 3, 4]
    assert [t.index for t in context.engine_input.tables] == [0, 1]
    # Kimlik haritası indekslerle aynı uzunlukta olmalı, yoksa geri dönüş kayar.
    assert len(context.registration_ids) == 5
    assert len(context.table_ids) == 2


async def test_conversion_carries_tags_and_their_categories(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Kategoriler etiketlerden türetiliyor (9.3 kısmi puan).

    Motor türetemez — etiket→kategori haritası veritabanında.
    """
    _organiser, event = await seed_event(client, unique_email, participants=2, tables=1)

    stored = await session.get(Event, event["id"])
    context = await build_engine_input(session, stored)

    for participant in context.engine_input.participants:
        assert len(participant.offered_tags) == 3
        assert len(participant.sought_tags) == 3
        # Başlangıç setinde ilk kategorinin sekiz etiketi var; üçü de aynı
        # kategoriden seçiliyor.
        assert participant.offered_categories
        assert participant.sought_categories


async def test_conversion_uses_company_identity_not_text(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Aynı şirket kuralı kimlikle çalışıyor (Bölüm 6).

    Şirketi olmayan iki kişi "aynı şirketten" sayılmamalı; her biri kendine
    özel bir değer alıyor.
    """
    _organiser, event = await seed_event(
        client, unique_email, participants=3, tables=2, complete=False
    )

    stored = await session.get(Event, event["id"])
    context = await build_engine_input(session, stored)
    companies = [p.company for p in context.engine_input.participants]

    assert len(set(companies)) == len(companies)


# --- Çalıştırma ---------------------------------------------------------------


async def test_running_writes_a_draft_plan_with_a_summary(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Motor bitince plan taslak kalıyor (5.2): yayın ayrı bir karar."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)

    plan = await run_plan(client, session, event["id"])

    assert plan["job_status"] == JobStatus.DONE.value
    assert plan["status"] == "draft"
    assert plan["version"] == 1
    assert plan["assignment_count"] > 0
    assert plan["total_meetings"] is not None
    assert plan["runtime_ms"] is not None
    assert plan["job_error"] is None


async def test_slot_numbers_start_at_one(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Motor 0 tabanlı, şema `slot_number > 0` istiyor, katılımcı "Tur 1" görüyor."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3, slots=3)

    await run_plan(client, session, event["id"])

    slots = (
        (
            await session.execute(
                select(Assignment.slot_number)
                .join(Plan, Plan.id == Assignment.plan_id)
                .where(Plan.event_id == event["id"])
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    assert min(slots) == 1
    assert max(slots) <= 3


async def test_assignments_point_at_real_tables_and_registrations(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """İndeks→kimlik dönüşü doğru mu — 9.2'nin uyardığı kayma buradan çıkar."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)

    await run_plan(client, session, event["id"])

    stored_tables = await session.execute(
        select(Table.id)
        .join(Layout, Layout.id == Table.layout_id)
        .where(Layout.event_id == event["id"])
    )
    table_ids = set(stored_tables.scalars().all())
    assignments = (
        (
            await session.execute(
                select(Assignment)
                .join(Plan, Plan.id == Assignment.plan_id)
                .where(Plan.event_id == event["id"])
            )
        )
        .scalars()
        .all()
    )

    assert assignments
    for assignment in assignments:
        assert assignment.table_id in table_ids


async def test_nobody_sits_twice_in_the_same_slot(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Kesin kural "Tek yer" (9.5), uçtan uca."""
    _organiser, event = await seed_event(client, unique_email, participants=8, tables=3, slots=4)

    await run_plan(client, session, event["id"])

    rows = (
        await session.execute(
            select(Assignment.slot_number, Assignment.registration_id)
            .join(Plan, Plan.id == Assignment.plan_id)
            .where(Plan.event_id == event["id"])
        )
    ).all()
    assert len(rows) == len(set(rows))


async def test_table_capacity_is_never_exceeded(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Kesin kural "Kapasite" (9.5), uçtan uca."""
    _organiser, event = await seed_event(
        client, unique_email, participants=8, tables=3, seats=4, slots=3
    )

    await run_plan(client, session, event["id"])

    rows = (
        await session.execute(
            select(Assignment.slot_number, Assignment.table_id)
            .join(Plan, Plan.id == Assignment.plan_id)
            .where(Plan.event_id == event["id"])
        )
    ).all()
    counts: dict[tuple[int, int], int] = {}
    for slot, table in rows:
        counts[(slot, table)] = counts.get((slot, table), 0) + 1
    assert counts
    assert max(counts.values()) <= 4


async def test_match_reasons_are_written_in_canonical_order(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Şema ikiliyi sıralı istiyor; aksi hâlde aynı çift iki kez yazılabilirdi."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=2)

    await run_plan(client, session, event["id"])

    reasons = (
        (
            await session.execute(
                select(MatchReason)
                .join(Plan, Plan.id == MatchReason.plan_id)
                .where(Plan.event_id == event["id"])
            )
        )
        .scalars()
        .all()
    )
    assert reasons
    for reason in reasons:
        assert reason.registration_a_id < reason.registration_b_id
        # Kırılım motorun bileşen anahtarlarını taşıyor; Aşama 9 bunları
        # Türkçe cümleye çevirecek.
        assert "supply_demand" in reason.breakdown
        assert "category" in reason.breakdown


async def test_second_run_creates_a_new_version(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """5.2: plan yaşayan bir nesne; yeniden çalıştırma yeni versiyon."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)

    first = await run_plan(client, session, event["id"])
    second = await run_plan(client, session, event["id"])

    assert first["version"] == 1
    assert second["version"] == 2

    listing = (await client.get(f"/events/{event['id']}/plans")).json()
    # Yeni versiyon önce.
    assert [item["version"] for item in listing] == [2, 1]


async def test_a_second_run_is_refused_while_one_is_pending(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """İki iş paralel çalışırsa hangisinin kazandığı belirsiz olur (5.3)."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)

    assert (await client.post(f"/events/{event['id']}/plans", json={})).status_code == 202
    blocked = await client.post(f"/events/{event['id']}/plans", json={})

    assert blocked.status_code == 409
    assert "zaten çalışıyor" in blocked.json()["detail"]


async def test_running_without_participants_is_refused(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = await open_event(client)

    response = await client.post(f"/events/{event['id']}/plans", json={})
    assert response.status_code == 409


async def test_failure_is_recorded_on_the_plan(
    client: AsyncClient,
    unique_email: Callable[[], str],
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5.4: hata durumu takip edilebilir olmalı.

    Motor patlatılıyor: sessizce kuyrukta kalan bir iş en kötü sonuç olurdu,
    organizatör "neden çalışmadı" sorusunun cevabını ekranda görmeli.

    Yama `plan_runner` içindeki ada yapılıyor: modül `from engine.runner
    import run_matching` ile fonksiyonu kendi ad alanına kopyalıyor, kaynağı
    değiştirmek onu etkilemezdi.
    """
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)

    started = await client.post(f"/events/{event['id']}/plans", json={})
    plan_id = started.json()["id"]

    def explode(_engine_input):
        raise RuntimeError("motor çöktü")

    monkeypatch.setattr("app.services.plan_runner.run_matching", explode)

    with pytest.raises(RuntimeError):
        await execute_plan(session, plan_id)

    plan = (await client.get(f"/events/{event['id']}/plans/{plan_id}")).json()
    assert plan["job_status"] == JobStatus.FAILED.value
    assert "motor çöktü" in plan["job_error"]
    # Yarım bir plan yayınlanamamalı; şema da CHECK ile engelliyor.
    assert plan["status"] == "draft"


# --- Kontrol listesi (M6) -----------------------------------------------------


async def test_check_reports_the_scale(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Kaç katılımcı kabul edilmiş, kaç masa, toplam kapasite ne."*"""
    _organiser, event = await seed_event(client, unique_email, participants=4, tables=3, seats=6)

    check = (await client.get(f"/events/{event['id']}/matching-check")).json()

    assert check["accepted_count"] == 4
    assert check["table_count"] == 3
    assert check["seating_capacity"] == 18
    assert check["can_run"] is True


async def test_check_warns_but_does_not_block(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Sorun varsa organizatör uyarılır ama çalıştırma engellenmez."*"""
    _organiser, event = await seed_event(client, unique_email, participants=8, tables=1, seats=2)

    check = (await client.get(f"/events/{event['id']}/matching-check")).json()

    assert CAPACITY_BELOW_PARTICIPANTS in check["warnings"]
    # Uyarı var ama kapı açık.
    assert check["can_run"] is True
    assert (await client.post(f"/events/{event['id']}/plans", json={})).status_code == 202


async def test_check_warns_when_requests_are_still_open(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Talep sistemi henüz kapanmadan eşleştirme çalıştırılırsa organizatör
    ayrıca uyarılır."*"""
    _organiser, event = await seed_event(client, unique_email, participants=4, tables=2)

    open_check = (await client.get(f"/events/{event['id']}/matching-check")).json()
    assert REQUESTS_STILL_OPEN in open_check["warnings"]

    await client.patch(f"/events/{event['id']}", json={"requests_close_at": in_days(-1)})
    closed_check = (await client.get(f"/events/{event['id']}/matching-check")).json()
    assert REQUESTS_STILL_OPEN not in closed_check["warnings"]


async def test_check_counts_incomplete_profiles(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Eksik profilli katılımcı var mı."*

    Başvuru kapısı eksik profili zaten engelliyor; ama organizatör kontenjanı
    elle onaylarken veya profil sonradan boşalırsa bu sayı sıfırdan farklı
    olabilir.
    """
    _organiser, event = await seed_event(client, unique_email, participants=3, tables=2)
    check = (await client.get(f"/events/{event['id']}/matching-check")).json()

    assert check["incomplete_profile_count"] == 0
    assert INCOMPLETE_PROFILES not in check["warnings"]


async def test_check_on_an_empty_event(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = await open_event(client)

    check = (await client.get(f"/events/{event['id']}/matching-check")).json()
    assert NO_PARTICIPANTS in check["warnings"]
    assert check["can_run"] is False


# --- Görünürlük ----------------------------------------------------------------


async def test_plans_of_another_event_are_not_reachable(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Bölüm 7: başkasının planına erişilemez, 404 döner."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)
    plan = await run_plan(client, session, event["id"])

    stranger = await sign_up(client, unique_email())
    use(client, stranger)

    assert (await client.get(f"/events/{event['id']}/plans")).status_code == 404
    assert (await client.get(f"/events/{event['id']}/plans/{plan['id']}")).status_code == 404
    assert (await client.get(f"/events/{event['id']}/matching-check")).status_code == 404
    assert (await client.post(f"/events/{event['id']}/plans", json={})).status_code == 404


async def test_plan_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events/1/plans")).status_code == 401
    assert (await client.post("/events/1/plans", json={})).status_code == 401
    assert (await client.get("/events/1/matching-check")).status_code == 401
