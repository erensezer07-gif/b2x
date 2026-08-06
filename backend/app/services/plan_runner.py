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
from dataclasses import dataclass

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


async def _together(session: AsyncSession, plan_id: int) -> set[tuple[int, int]]:
    """Planın herhangi bir turunda aynı masaya oturan ikililer."""
    seats = await session.execute(
        select(Assignment.slot_number, Assignment.table_id, Assignment.registration_id).where(
            Assignment.plan_id == plan_id
        )
    )
    by_table: dict[tuple[int, int], list[int]] = {}
    for slot, table, registration in seats.all():
        by_table.setdefault((slot, table), []).append(registration)

    pairs: set[tuple[int, int]] = set()
    for people in by_table.values():
        ordered = sorted(people)
        for position, first in enumerate(ordered):
            for second in ordered[position + 1 :]:
                pairs.add((first, second))
    return pairs


async def _active_requests(session: AsyncSession, event_id: int) -> list[tuple[int, int]]:
    result = await session.execute(
        select(
            MeetingRequest.requester_registration_id,
            MeetingRequest.target_registration_id,
        ).where(
            MeetingRequest.event_id == event_id,
            MeetingRequest.status == MeetingRequestStatus.ACTIVE,
        )
    )
    return [(requester, target) for requester, target in result.all()]


async def request_counts(session: AsyncSession, event_id: int, plan_id: int) -> tuple[int, int]:
    """*"Karşılanan talep sayısı / toplam talep"* (M7).

    Bir talep, iki taraf planın herhangi bir turunda aynı masaya oturduysa
    karşılanmış sayılıyor. Karşılıklı talep **iki** talep sayılıyor: ikisi de
    isteğini almış oluyor.
    """
    requests = await _active_requests(session, event_id)
    if not requests:
        return 0, 0

    together = await _together(session, plan_id)
    satisfied = sum(
        1
        for requester, target in requests
        if (min(requester, target), max(requester, target)) in together
    )
    return satisfied, len(requests)


@dataclass(frozen=True, slots=True)
class UnmetRequest:
    """Karşılanmayan bir talep (M9, organizatör görünümü).

    `fixable_slot` iki tarafın da oturduğu ama farklı masalara düştüğü ilk
    tur — takasla düzeltilebilecek yer. İkisi hiçbir turda birlikte
    oturmuyorsa (biri hep boşta kaldıysa) `None`.
    """

    requester_registration_id: int
    target_registration_id: int
    requester_name: str
    target_name: str

    # İkisi de birbirini istemiş mi. M9 buna "neredeyse kesin eşleşme" diyor;
    # karşılanmadıysa gerçek bir kusur.
    mutual: bool

    fixable_slot: int | None


async def unmet_requests(session: AsyncSession, event_id: int, plan_id: int) -> list[UnmetRequest]:
    """*"Organizatör plan ekranında karşılanmayan talepleri görür."* (M9)

    Karşılanmış talepler dönmüyor: yapılacak bir şey kalmamış. Karşılıklı
    ikili **tek satır** olarak dönüyor — iki yönü ayrı göstermek aynı sorunu
    iki kez saymak olurdu.

    Sıralama karşılıklılar önce: düzeltilmesi gereken onlar.
    """
    requests = await _active_requests(session, event_id)
    if not requests:
        return []

    together = await _together(session, plan_id)
    directions = set(requests)

    # (küçük, büyük) → karşılıklı mı. Karşılanmışlar hiç girmiyor.
    pairs: dict[tuple[int, int], bool] = {}
    for requester, target in requests:
        key = (min(requester, target), max(requester, target))
        if key in together:
            continue
        mutual = (target, requester) in directions
        pairs[key] = pairs.get(key, False) or mutual

    if not pairs:
        return []

    names = await _names(session, event_id)
    seats = await session.execute(
        select(Assignment.slot_number, Assignment.table_id, Assignment.registration_id).where(
            Assignment.plan_id == plan_id
        )
    )
    where_seated: dict[int, dict[int, int]] = {}
    for slot, table, registration in seats.all():
        where_seated.setdefault(registration, {})[slot] = table

    rows = [
        UnmetRequest(
            requester_registration_id=first,
            target_registration_id=second,
            requester_name=names.get(first, f"#{first}"),
            target_name=names.get(second, f"#{second}"),
            mutual=mutual,
            fixable_slot=_fixable_slot(where_seated, first, second),
        )
        for (first, second), mutual in pairs.items()
    ]
    rows.sort(key=lambda row: (not row.mutual, row.requester_name, row.target_name))
    return rows


def _fixable_slot(where_seated: dict[int, dict[int, int]], first: int, second: int) -> int | None:
    """İkisinin de oturduğu ama farklı masalara düştüğü ilk tur."""
    mine = where_seated.get(first, {})
    theirs = where_seated.get(second, {})
    for slot in sorted(set(mine) & set(theirs)):
        if mine[slot] != theirs[slot]:
            return slot
    return None


async def _names(session: AsyncSession, event_id: int) -> dict[int, str]:
    result = await session.execute(
        select(Registration.id, Profile.full_name)
        .join(User, User.id == Registration.user_id)
        .join(Profile, Profile.user_id == User.id, isouter=True)
        .where(Registration.event_id == event_id)
    )
    return {
        registration_id: name or f"#{registration_id}" for registration_id, name in result.all()
    }
