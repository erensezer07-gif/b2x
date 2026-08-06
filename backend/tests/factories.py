"""Kısıt testleri için geçerli örnek kayıtlar.

Amaç testleri okunur tutmak: her test yalnızca sınadığı kuralı yazar, geri kalan
alanları burası doldurur. Üretilen kayıtlar her zaman geçerlidir — testin
bozacağı tek şey sınadığı kuraldır.
"""

from datetime import UTC, datetime, timedelta
from itertools import count

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    Event,
    EventStatus,
    JobStatus,
    Layout,
    LayoutMode,
    Plan,
    PlanStatus,
    Registration,
    Table,
    TableKind,
    User,
)

# Benzersiz olması gereken alanlar (e-posta, QR kodu) için sayaç.
_counter = count(1)


async def create_user(session: AsyncSession, email: str | None = None) -> User:
    number = next(_counter)
    user = User(
        email=email or f"kullanici{number}@ornek.test",
        password_hash="test-icin-anlamsiz-ozet",
    )
    session.add(user)
    await session.flush()
    return user


async def create_company(session: AsyncSession, normalized_name: str) -> Company:
    company = Company(name=normalized_name.title(), normalized_name=normalized_name)
    session.add(company)
    await session.flush()
    return company


async def create_event(session: AsyncSession, organizer: User | None = None) -> Event:
    event = Event(
        organizer_id=(organizer or await create_user(session)).id,
        name=f"Test Etkinligi {next(_counter)}",
        starts_at=datetime.now(UTC) + timedelta(days=30),
        slot_duration_minutes=30,
        break_duration_minutes=10,
        slot_count=8,
        capacity=200,
        status=EventStatus.DRAFT,
        auto_approve_registrations=True,
        request_quota=3,
    )
    session.add(event)
    await session.flush()
    return event


async def create_layout(
    session: AsyncSession, event: Event, mode: LayoutMode = LayoutMode.AUTO
) -> Layout:
    manual = mode is LayoutMode.MANUAL
    layout = Layout(
        event_id=event.id,
        mode=mode,
        grid_width=20 if manual else None,
        grid_height=20 if manual else None,
    )
    session.add(layout)
    await session.flush()
    return layout


async def create_table(
    session: AsyncSession,
    layout: Layout,
    number: int,
    grid_x: int | None = None,
    grid_y: int | None = None,
) -> Table:
    table = Table(
        layout_id=layout.id,
        number=number,
        kind=TableKind.SEATED,
        seat_count=6,
        grid_x=grid_x,
        grid_y=grid_y,
    )
    session.add(table)
    await session.flush()
    return table


async def create_registration(
    session: AsyncSession, event: Event, user: User | None = None
) -> Registration:
    registration = Registration(
        event_id=event.id,
        user_id=(user or await create_user(session)).id,
        qr_code=f"qr-{next(_counter):08d}",
    )
    session.add(registration)
    await session.flush()
    return registration


async def create_plan(
    session: AsyncSession,
    event: Event,
    version: int = 1,
    status: PlanStatus = PlanStatus.DRAFT,
) -> Plan:
    # Yayınlanmış veya arşivlenmiş bir planın hesabı bitmiş olmak zorunda:
    # `published_needs_finished_job` kısıtı bunu şart koşuyor (Aşama 7).
    # Taslak plan kuyrukta bekliyor olabilir.
    finished = status is not PlanStatus.DRAFT
    plan = Plan(
        event_id=event.id,
        version=version,
        status=status,
        job_status=JobStatus.DONE if finished else JobStatus.QUEUED,
        published_at=datetime.now(UTC) if status is PlanStatus.PUBLISHED else None,
        seed=42,
    )
    session.add(plan)
    await session.flush()
    return plan
