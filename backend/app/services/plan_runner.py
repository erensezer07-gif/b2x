"""Eşleştirmenin çalıştırılması (şartname 5.4).

Motor HTTP isteği içinde çalıştırılamaz — 200 kişilik bir etkinlikte saniyeler
sürüyor, istek zaman aşımına uğrardı. Bu yüzden akış ikiye bölünüyor:

1. **Uç** plan satırını `queued` durumunda oluşturur ve işi kuyruğa atar.
   Anında döner.
2. **İşçi** bu modüldeki `execute_plan` fonksiyonunu çağırır: durumu
   `running` yapar, motoru çalıştırır, satırları yazar, `done` yapar.

Hata olursa durum `failed` ve mesaj `job_error` alanında. Organizatör "neden
çalışmadı" sorusunun cevabını ekranda görmeli; sessizce kuyrukta kalan bir iş
en kötü sonuç olurdu.

Bu modül HTTP bilmez: hem uç hem işçi çağırabilsin diye yalnızca oturum ve
kimlik alıyor.
"""

import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    Assignment,
    Event,
    JobStatus,
    MeetingRequest,
    MeetingRequestStatus,
    Plan,
    PlanStatus,
    Profile,
    Registration,
    RegistrationStatus,
    User,
)
from app.services.matching import build_engine_input, build_rows
from engine.runner import run_matching

logger = logging.getLogger(__name__)


async def create_queued_plan(session: AsyncSession, event: Event, seed: int | None) -> Plan:
    """Yeni bir plan versiyonu açar; hesabı henüz yapılmadı.

    Versiyon numarası mevcut en yükseğin bir fazlası. Plan **taslak** olarak
    doğuyor: 5.2 gereği yayınlanma ayrı bir karar, motorun bitmesi otomatik
    yayın anlamına gelmiyor.
    """
    highest = await session.execute(select(func.max(Plan.version)).where(Plan.event_id == event.id))
    previous = await session.execute(
        select(Plan).where(Plan.event_id == event.id).order_by(Plan.version.desc()).limit(1)
    )
    latest = previous.scalar_one_or_none()

    plan = Plan(
        event_id=event.id,
        version=(highest.scalar_one() or 0) + 1,
        status=PlanStatus.DRAFT,
        job_status=JobStatus.QUEUED,
        seed=seed if seed is not None else get_settings().matching_default_seed,
        previous_plan_id=latest.id if latest is not None else None,
    )
    session.add(plan)
    await session.flush()
    return plan


async def execute_plan(session: AsyncSession, plan_id: int) -> None:
    """Motoru çalıştırır ve sonucu plana yazar.

    İşçi tarafından çağrılıyor. Hata durumunda **yutmuyor**: durumu `failed`
    yapıp mesajı saklıyor, sonra yeniden fırlatıyor — kuyruk da görsün.
    """
    plan = await session.get(Plan, plan_id)
    if plan is None:
        logger.warning("Plan %s bulunamadı; iş atlanıyor.", plan_id)
        return

    event = await session.get(Event, plan.event_id)
    if event is None:
        await _fail(session, plan_id, "Etkinlik bulunamadı.")
        return

    plan.job_status = JobStatus.RUNNING
    await session.commit()

    try:
        context = await build_engine_input(session, event, seed=plan.seed)

        # Motor senkron ve CPU'ya bağlı. Doğrudan çağrılsaydı olay döngüsünü
        # saniyelerce kilitler ve aynı işçideki diğer işler beklerdi.
        output = await asyncio.to_thread(run_matching, context.engine_input)

        assignments, reasons = build_rows(plan, context, output)
        session.add_all(assignments)
        session.add_all(reasons)

        summary = output.summary
        plan.total_meetings = summary.total_meetings
        plan.min_meetings_per_person = summary.min_meetings_per_person
        plan.average_table_score = summary.average_table_score
        plan.runtime_ms = summary.runtime_ms
        plan.job_status = JobStatus.DONE
        plan.job_error = None
        await session.commit()

    except Exception as error:  # noqa: BLE001 — hata neyse plana yazılmalı
        await session.rollback()
        await _fail(session, plan_id, str(error) or error.__class__.__name__)
        raise


async def _fail(session: AsyncSession, plan_id: int, message: str) -> None:
    """Planı hatalı işaretler.

    **Nesne değil kimlik alıyor.** `rollback` bütün nesnelerin süresini
    doldurur; elde tutulan bir `Plan`'ın alanına dokunmak eşzamansız bir
    yeniden yükleme tetikler ve SQLAlchemy bunu `MissingGreenlet` ile
    reddeder. Kimlik düz bir sayı, süresi dolmaz.
    """
    fresh = await session.get(Plan, plan_id)
    if fresh is None:
        return
    fresh.job_status = JobStatus.FAILED
    # Mesaj ekranda görünecek; teknik ama boş bırakmaktan iyi.
    fresh.job_error = message[:1000]
    await session.commit()


async def assignment_count(session: AsyncSession, plan_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(Assignment).where(Assignment.plan_id == plan_id)
    )
    return result.scalar_one()


async def seated_participant_count(session: AsyncSession, plan_id: int) -> int:
    """Planda en az bir kez masaya oturan kişi sayısı."""
    result = await session.execute(
        select(func.count(func.distinct(Assignment.registration_id))).where(
            Assignment.plan_id == plan_id
        )
    )
    return result.scalar_one()


async def unmatched_names(session: AsyncSession, event_id: int, plan_id: int) -> list[str]:
    """*"Hiç eşleşmemiş kişi var mı, varsa kimler"* (M7).

    Kabul edilmiş ama planın hiçbir turunda masaya oturmamış kişiler. Özet
    panelin en can alıcı ikinci bilgisi: organizatör bu isimleri görüp elle
    yerleştirebilir.
    """
    seated = select(Assignment.registration_id).where(Assignment.plan_id == plan_id)
    result = await session.execute(
        select(Profile.full_name, Registration.id)
        .join(User, User.id == Registration.user_id)
        .join(Profile, Profile.user_id == User.id, isouter=True)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.ACCEPTED,
            Registration.id.not_in(seated),
        )
        .order_by(Registration.id)
    )
    return [name or f"#{registration_id}" for name, registration_id in result.all()]


async def request_counts(session: AsyncSession, event_id: int, plan_id: int) -> tuple[int, int]:
    """*"Karşılanan talep sayısı / toplam talep"* (M7).

    Bir talep, iki taraf planın herhangi bir turunda aynı masaya oturduysa
    karşılanmış sayılıyor. Talep sistemi Aşama 10'da açılıyor; şimdilik ikisi
    de sıfır dönüyor.
    """
    total = await session.execute(
        select(func.count())
        .select_from(MeetingRequest)
        .where(
            MeetingRequest.event_id == event_id,
            MeetingRequest.status == MeetingRequestStatus.ACTIVE,
        )
    )
    total_count = total.scalar_one()
    if total_count == 0:
        return 0, 0

    seats = await session.execute(
        select(Assignment.slot_number, Assignment.table_id, Assignment.registration_id).where(
            Assignment.plan_id == plan_id
        )
    )
    together: set[tuple[int, int]] = set()
    by_table: dict[tuple[int, int], list[int]] = {}
    for slot, table, registration in seats.all():
        by_table.setdefault((slot, table), []).append(registration)
    for people in by_table.values():
        ordered = sorted(people)
        for position, first in enumerate(ordered):
            for second in ordered[position + 1 :]:
                together.add((first, second))

    requests = await session.execute(
        select(
            MeetingRequest.requester_registration_id,
            MeetingRequest.target_registration_id,
        ).where(
            MeetingRequest.event_id == event_id,
            MeetingRequest.status == MeetingRequestStatus.ACTIVE,
        )
    )
    satisfied = sum(
        1
        for requester, target in requests.all()
        if (min(requester, target), max(requester, target)) in together
    )
    return satisfied, total_count
