"""Şemanın gerçekten koruduğunun kanıtı.

Buradaki her test bir kuralı bilerek ihlal eder ve veritabanının reddettiğini
gösterir. Kısıtı migration'a yazmak yetmez — yanlış yazılmış bir kısıt, ilgili
ekran yazılana kadar fark edilmez.

Çoğu şartname Bölüm 10'daki kabul kriterlerinin doğrudan karşılığıdır.

Testler `alembic upgrade head` ile kurulmuş ayrı bir veritabanına karşı çalışır;
veritabanı yoksa `conftest.py` hepsini atlar.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assignment,
    Company,
    LayoutMode,
    MatchReason,
    MeetingRequest,
    PlanStatus,
    Table,
    TableKind,
    User,
)
from tests.factories import (
    create_company,
    create_event,
    create_layout,
    create_plan,
    create_registration,
    create_table,
    create_user,
)

# --- Plan versiyonlama (şartname 5.2, Bölüm 10 "Plan durumu") ---------------


async def test_only_one_published_plan_per_event(session: AsyncSession) -> None:
    """Şartnamenin en kritik veri kuralı."""
    event = await create_event(session)
    await create_plan(session, event, version=1, status=PlanStatus.PUBLISHED)

    with pytest.raises(IntegrityError):
        await create_plan(session, event, version=2, status=PlanStatus.PUBLISHED)


async def test_archived_plan_does_not_block_publishing(session: AsyncSession) -> None:
    """Arşivdeki plan koşullu indekse takılmamalı — yoksa yeni versiyon yayınlanamazdı."""
    event = await create_event(session)
    await create_plan(session, event, version=1, status=PlanStatus.ARCHIVED)
    await create_plan(session, event, version=2, status=PlanStatus.PUBLISHED)


async def test_plan_version_is_unique_per_event(session: AsyncSession) -> None:
    event = await create_event(session)
    await create_plan(session, event, version=1)

    with pytest.raises(IntegrityError):
        await create_plan(session, event, version=1)


async def test_published_plan_requires_publish_time(session: AsyncSession) -> None:
    event = await create_event(session)
    plan = await create_plan(session, event, status=PlanStatus.DRAFT)

    plan.status = PlanStatus.PUBLISHED
    plan.published_at = None
    with pytest.raises(IntegrityError):
        await session.flush()


# --- Atamalar (şartname 9.5 "Tek yer") --------------------------------------


async def test_participant_cannot_sit_at_two_tables_in_one_slot(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    layout = await create_layout(session, event)
    first_table = await create_table(session, layout, number=1)
    second_table = await create_table(session, layout, number=2)
    registration = await create_registration(session, event)
    plan = await create_plan(session, event)

    session.add(
        Assignment(
            plan_id=plan.id,
            slot_number=1,
            table_id=first_table.id,
            registration_id=registration.id,
        )
    )
    await session.flush()

    session.add(
        Assignment(
            plan_id=plan.id,
            slot_number=1,
            table_id=second_table.id,
            registration_id=registration.id,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_same_participant_may_sit_in_different_slots(session: AsyncSession) -> None:
    """Kısıt slot bazlı olmalı; kişi elbette her slotta bir masada oturur."""
    event = await create_event(session)
    layout = await create_layout(session, event)
    table = await create_table(session, layout, number=1)
    registration = await create_registration(session, event)
    plan = await create_plan(session, event)

    for slot in (1, 2):
        session.add(
            Assignment(
                plan_id=plan.id,
                slot_number=slot,
                table_id=table.id,
                registration_id=registration.id,
            )
        )
    await session.flush()


# --- Salon düzeni (şartname M5, Bölüm 10 "Manuel düzen") --------------------


async def test_table_number_is_unique_within_layout(session: AsyncSession) -> None:
    """Katılımcı masasını numarayla buluyor; çakışma kabul edilemez."""
    event = await create_event(session)
    layout = await create_layout(session, event)
    await create_table(session, layout, number=7)

    with pytest.raises(IntegrityError):
        await create_table(session, layout, number=7)


async def test_two_tables_cannot_share_a_grid_cell(session: AsyncSession) -> None:
    event = await create_event(session)
    layout = await create_layout(session, event, mode=LayoutMode.MANUAL)
    await create_table(session, layout, number=1, grid_x=3, grid_y=4)

    with pytest.raises(IntegrityError):
        await create_table(session, layout, number=2, grid_x=3, grid_y=4)


async def test_seated_table_cannot_carry_standing_capacity(session: AsyncSession) -> None:
    """Masa tipi ile kapasite alanları tutarlı olmak zorunda."""
    event = await create_event(session)
    layout = await create_layout(session, event)

    session.add(
        Table(
            layout_id=layout.id,
            number=1,
            kind=TableKind.SEATED,
            seat_count=6,
            min_people=2,
            max_people=8,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_standing_table_requires_people_range(session: AsyncSession) -> None:
    event = await create_event(session)
    layout = await create_layout(session, event)

    session.add(Table(layout_id=layout.id, number=1, kind=TableKind.STANDING))
    with pytest.raises(IntegrityError):
        await session.flush()


# --- Başvuru ve talep (şartname Bölüm 6, M9) --------------------------------


async def test_user_cannot_register_twice_for_same_event(session: AsyncSession) -> None:
    event = await create_event(session)
    user = await create_user(session)
    await create_registration(session, event, user)

    with pytest.raises(IntegrityError):
        await create_registration(session, event, user)


async def test_qr_code_is_unique(session: AsyncSession) -> None:
    event = await create_event(session)
    first = await create_registration(session, event)
    second = await create_registration(session, event)

    second.qr_code = first.qr_code
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_second_request_to_same_person_is_rejected(session: AsyncSession) -> None:
    event = await create_event(session)
    requester = await create_registration(session, event)
    target = await create_registration(session, event)

    for _ in range(2):
        session.add(
            MeetingRequest(
                event_id=event.id,
                requester_registration_id=requester.id,
                target_registration_id=target.id,
            )
        )

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_request_to_self_is_rejected(session: AsyncSession) -> None:
    event = await create_event(session)
    registration = await create_registration(session, event)

    session.add(
        MeetingRequest(
            event_id=event.id,
            requester_registration_id=registration.id,
            target_registration_id=registration.id,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_request_across_events_is_rejected(session: AsyncSession) -> None:
    """Bileşik yabancı anahtar tarafların aynı etkinlikte olmasını zorlar."""
    first_event = await create_event(session)
    second_event = await create_event(session)
    requester = await create_registration(session, first_event)
    outsider = await create_registration(session, second_event)

    session.add(
        MeetingRequest(
            event_id=first_event.id,
            requester_registration_id=requester.id,
            target_registration_id=outsider.id,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


# --- Şirket tekilleştirme (şartname Bölüm 10 "Profil") ----------------------


async def test_company_normalized_name_is_unique(session: AsyncSession) -> None:
    """Aynı şirket iki kez oluşturulamamalı — masa ayrımı kuralı buna dayanıyor."""
    await create_company(session, "abc yazilim")

    session.add(Company(name="ABC Yazılım A.Ş.", normalized_name="abc yazilim"))
    with pytest.raises(IntegrityError):
        await session.flush()


# --- Eşleşme gerekçesi ------------------------------------------------------


async def test_match_reason_pair_must_be_canonical(session: AsyncSession) -> None:
    """İkili sırasız; ters sırada yazılabilseydi aynı çift iki kez girerdi."""
    event = await create_event(session)
    plan = await create_plan(session, event)
    first = await create_registration(session, event)
    second = await create_registration(session, event)
    low, high = sorted((first.id, second.id))

    session.add(
        MatchReason(
            plan_id=plan.id,
            slot_number=1,
            registration_a_id=high,
            registration_b_id=low,
            total_score=0.8,
            breakdown={},
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_duplicate_match_reason_is_rejected(session: AsyncSession) -> None:
    event = await create_event(session)
    plan = await create_plan(session, event)
    first = await create_registration(session, event)
    second = await create_registration(session, event)
    low, high = sorted((first.id, second.id))

    for _ in range(2):
        session.add(
            MatchReason(
                plan_id=plan.id,
                slot_number=1,
                registration_a_id=low,
                registration_b_id=high,
                total_score=0.8,
                breakdown={"sektor": {"puan": 0.8, "aciklama": "İkiniz de fintech'tesiniz"}},
            )
        )

    with pytest.raises(IntegrityError):
        await session.flush()


# --- Kimlik ve durum alanları -----------------------------------------------


async def test_email_must_be_stored_lowercase(session: AsyncSession) -> None:
    session.add(User(email="Buyuk@Ornek.Test", password_hash="ozet"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_status_column_rejects_unknown_value(session: AsyncSession) -> None:
    """Durum sütunları denetimsiz metin olmamalı.

    ORM listedeki değerleri zorluyor, bu yüzden ham SQL ile deneniyor — kısıtın
    veritabanında olduğunu görmek gerekiyor.
    """
    event = await create_event(session)

    with pytest.raises(IntegrityError):
        await session.execute(
            text("UPDATE events SET status = 'olmayan_durum' WHERE id = :id"),
            {"id": event.id},
        )


async def test_registration_marked_present_requires_checkin_time(
    session: AsyncSession,
) -> None:
    event = await create_event(session)
    registration = await create_registration(session, event)

    with pytest.raises(IntegrityError):
        await session.execute(
            text("UPDATE registrations SET attendance = 'present' WHERE id = :id"),
            {"id": registration.id},
        )


async def test_registration_defaults_are_sane(session: AsyncSession) -> None:
    """Yeni başvuru beklemede ve gelmedi olarak başlar."""
    event = await create_event(session)
    registration = await create_registration(session, event)
    await session.refresh(registration)

    assert registration.status == "pending"
    assert registration.attendance == "absent"
    assert registration.checked_in_at is None
