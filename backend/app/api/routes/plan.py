"""Eşleştirme ve plan uçları (şartname M6, 5.4).

Organizatör "eşleştir" der, iş kuyruğa girer, uç anında döner. Motorun kendisi
`app/services/plan_runner.py` içinde; buradaki işler yetki kontrolü, kuyruğa
atma ve durumu raporlama.

Planı **yalnızca organizatör** görüyor. Katılımcının kendi atamalarını görmesi
Aşama 9'un konusu ve ayrı uçlar olacak — plan yayınlanmadan hiçbir atama
görünmemeli (Bölüm 7).
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import JobQueueDep, OwnedEvent, SessionDep
from app.models import Assignment, JobStatus, Plan
from app.schemas.attendance import PlanChangesResponse, SeatChangeResponse
from app.schemas.meeting_request import UnmetRequestResponse
from app.schemas.plan import (
    MatchingCheckResponse,
    PinRequest,
    PlanSummaryResponse,
    RunMatchingRequest,
    SeatedPersonResponse,
    SlotViewResponse,
    SwapRequest,
    SwapResponse,
    SwapWarningResponse,
    TableViewResponse,
)
from app.services.attendance import has_check_in
from app.services.matching import build_matching_check
from app.services.plan_editing import (
    SwapRejected,
    TableView,
    apply_swap,
    build_slot_view,
    publish,
    set_pinned,
)
import asyncio
import logging

from app.db import get_session_factory
from app.services.plan_runner import (
    absentees_of,
    assignment_count,
    create_queued_plan,
    execute_plan,
    request_counts,
    seat_changes,
    seated_participant_count,
    unmatched_names,
    unmet_requests,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events/{event_id}", tags=["esletirme"])

# İşçideki fonksiyonun adı. Kuyruk adla çalışıyor, referansla değil.
MATCHING_JOB = "run_matching_job"


async def _run_plan_in_background(plan_id: int) -> None:
    """Arka plan işçisi/Redis yoksa eşleştirmeyi sunucu sürecinde çalıştırır."""
    async with get_session_factory()() as session:
        try:
            await execute_plan(session, plan_id)
        except Exception:
            logger.exception("Sunucu içi eşleştirme plan %s için başarısız oldu.", plan_id)


@router.get("/matching-check", summary="Çalıştırma öncesi kontrol listesi")
async def read_matching_check(event: OwnedEvent, session: SessionDep) -> MatchingCheckResponse:
    """M6'nın kontrol listesi.

    *"Sorun varsa organizatör uyarılır ama çalıştırma engellenmez."* Uyarılar
    İngilizce anahtar olarak dönüyor; Türkçe cümleyi arayüz kuruyor.
    """
    check = await build_matching_check(session, event)
    return MatchingCheckResponse(
        accepted_count=check.accepted_count,
        table_count=check.table_count,
        seating_capacity=check.seating_capacity,
        request_count=check.request_count,
        incomplete_profile_count=check.incomplete_profile_count,
        slot_count=check.slot_count,
        requests_open=check.requests_open,
        warnings=list(check.warnings),
        can_run=check.can_run,
    )


async def _to_response(session: SessionDep, plan: Plan) -> PlanSummaryResponse:
    satisfied, total = await request_counts(session, plan.event_id, plan.id)
    absentees = await absentees_of(session, plan)
    return PlanSummaryResponse(
        id=plan.id,
        version=plan.version,
        status=plan.status,
        job_status=plan.job_status,
        job_error=plan.job_error,
        created_at=plan.created_at,
        published_at=plan.published_at,
        seed=plan.seed,
        total_meetings=plan.total_meetings,
        min_meetings_per_person=plan.min_meetings_per_person,
        average_table_score=plan.average_table_score,
        runtime_ms=plan.runtime_ms,
        assignment_count=await assignment_count(session, plan.id),
        participant_count=await seated_participant_count(session, plan.id),
        unmatched=await unmatched_names(session, plan.event_id, plan.id, absentees=absentees),
        absent_count=len(absentees),
        satisfied_requests=satisfied,
        total_requests=total,
        unmet_requests=[
            UnmetRequestResponse(
                requester_registration_id=row.requester_registration_id,
                target_registration_id=row.target_registration_id,
                requester_name=row.requester_name,
                target_name=row.target_name,
                mutual=row.mutual,
                fixable_slot=row.fixable_slot,
            )
            for row in await unmet_requests(session, plan.event_id, plan.id)
        ],
    )


def _slot_response(slot_number: int, tables: list[TableView]) -> SlotViewResponse:
    return SlotViewResponse(
        slot_number=slot_number,
        tables=[
            TableViewResponse(
                table_id=table.table_id,
                number=table.number,
                label=table.label,
                capacity=table.capacity,
                occupants=[
                    SeatedPersonResponse(
                        assignment_id=person.assignment_id,
                        registration_id=person.registration_id,
                        full_name=person.full_name,
                        company=person.company,
                        is_pinned=person.is_pinned,
                    )
                    for person in table.occupants
                ],
                quality=table.quality,
                score=table.score,
            )
            for table in tables
        ],
    )


@router.post(
    "/plans",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Eşleştirmeyi çalıştır",
)
async def run_matching(
    payload: RunMatchingRequest,
    event: OwnedEvent,
    session: SessionDep,
    queue: JobQueueDep,
) -> PlanSummaryResponse:
    """Yeni bir plan versiyonu açar ve hesabı kuyruğa atar (5.4).

    **202** dönüyor, 201 değil: kaynak oluştu ama işi bitmedi. Plan
    `queued` durumunda; sonucu `GET /plans/{id}` ile izleniyor.

    Aynı anda ikinci bir çalıştırma engelleniyor: iki iş aynı etkinlik için
    paralel çalışırsa hangisinin kazandığı belirsiz olur ve 5.3'ün determinizm
    sözü anlamını yitirir.
    """
    check = await build_matching_check(session, event)
    if not check.can_run:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Eşleştirme için en az iki kabul edilmiş katılımcı ve bir masa gerekiyor.",
        )

    running_plans = await session.execute(
        select(Plan).where(
            Plan.event_id == event.id,
            Plan.job_status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    for stuck in running_plans.scalars():
        await execute_plan(session, stuck.id)

    if payload.minimal_change and not await has_check_in(session, event.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Önce en az bir katılımcının geldiğini işaretle; yoksa plan tamamen boşalır.",
        )

    plan = await create_queued_plan(
        session, event, payload.seed, minimal_change=payload.minimal_change
    )
    await session.commit()

    # Sunucu içinde doğrudan motoru çalıştırıyoruz (anında sonuç verir ve kuyrukta takılmayı önler).
    await execute_plan(session, plan.id)

    fresh_plan = await session.get(Plan, plan.id)
    return await _to_response(session, fresh_plan or plan)


@router.get("/plans", summary="Plan versiyonları")
async def list_plans(event: OwnedEvent, session: SessionDep) -> list[PlanSummaryResponse]:
    """Yeni versiyon önce: organizatör en son çalıştırmayı arıyor."""
    result = await session.execute(
        select(Plan).where(Plan.event_id == event.id).order_by(Plan.version.desc())
    )
    plans = list(result.scalars())
    for p in plans:
        if p.job_status in (JobStatus.QUEUED, JobStatus.RUNNING):
            await execute_plan(session, p.id)

    result = await session.execute(
        select(Plan).where(Plan.event_id == event.id).order_by(Plan.version.desc())
    )
    return [await _to_response(session, p) for p in result.scalars()]


@router.get("/plans/{plan_id}", summary="Plan ve hesabın durumu")
async def read_plan(plan_id: int, event: OwnedEvent, session: SessionDep) -> PlanSummaryResponse:
    plan = await _require_plan(session, event, plan_id)
    if plan.job_status in (JobStatus.QUEUED, JobStatus.RUNNING):
        await execute_plan(session, plan.id)
        plan = await _require_plan(session, event, plan_id)
    return await _to_response(session, plan)


@router.delete(
    "/plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Planı veya eşleştirme çalışmasını sil/iptal et",
)
async def delete_plan(
    plan_id: int, event: OwnedEvent, session: SessionDep
) -> None:
    """Planı veya iptal edilmek istenen çalışmayı siler."""
    plan = await _require_plan(session, event, plan_id)
    if plan.status == PlanStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Yayınlanmış bir plan silinemez.",
        )
    await session.delete(plan)
    await session.commit()


async def _require_plan(session: SessionDep, event: OwnedEvent, plan_id: int) -> Plan:
    result = await session.execute(
        select(Plan)
        .where(Plan.id == plan_id, Plan.event_id == event.id)
        .execution_options(populate_existing=True)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        # Başka bir etkinliğin planı da buraya düşer (Bölüm 7).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan bulunamadı.")
    return plan


# --- Önizleme ve elle düzeltme (M7) ------------------------------------------


@router.get("/plans/{plan_id}/slots/{slot_number}", summary="Bir turun masaları")
async def read_slot(
    plan_id: int, slot_number: int, event: OwnedEvent, session: SessionDep
) -> SlotViewResponse:
    """*"Seçili slot için tüm masalar ve kimlerin oturduğu listelenir."* (M7)"""
    plan = await _require_plan(session, event, plan_id)
    if not 1 <= slot_number <= event.slot_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bu etkinlikte {event.slot_count} tur var.",
        )
    tables = await build_slot_view(session, event, plan, slot_number)
    return _slot_response(slot_number, tables)


@router.post("/plans/{plan_id}/swap", summary="İki kişiyi takas et")
async def swap_people(
    plan_id: int, payload: SwapRequest, event: OwnedEvent, session: SessionDep
) -> SwapResponse:
    """Takas ya da boş yere taşıma (M7).

    Kural ihlalleri **uyarı** olarak dönüyor, takası engellemiyor:
    *"Organizatör uyarıya rağmen devam edebilir — ama ne yaptığını bilerek
    yapar."* Yalnızca sabitlenmiş atama reddediliyor.
    """
    plan = await _require_plan(session, event, plan_id)
    try:
        tables, warnings = await apply_swap(
            session,
            event,
            plan,
            slot_number=payload.slot_number,
            assignment_id=payload.assignment_id,
            target_assignment_id=payload.target_assignment_id,
            target_table_id=payload.target_table_id,
        )
    except SwapRejected as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.message) from error

    return SwapResponse(
        slot=_slot_response(payload.slot_number, tables),
        warnings=[
            SwapWarningResponse(
                key=warning.key,
                table_number=warning.table_number,
                people=list(warning.people),
                slot_number=warning.slot_number,
            )
            for warning in warnings
        ],
    )


@router.patch(
    "/plans/{plan_id}/assignments/{assignment_id}",
    summary="Atamayı sabitle veya çöz",
)
async def pin_assignment(
    plan_id: int,
    assignment_id: int,
    payload: PinRequest,
    event: OwnedEvent,
    session: SessionDep,
) -> SlotViewResponse:
    """*"Sabitlenen atama, motor tekrar çalıştırılsa bile değişmez."* (M7)"""
    plan = await _require_plan(session, event, plan_id)
    try:
        await set_pinned(session, plan, assignment_id, payload.is_pinned)
    except SwapRejected as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.message) from error

    assignment = await session.get(Assignment, assignment_id)
    slot_number = assignment.slot_number if assignment else 1
    tables = await build_slot_view(session, event, plan, slot_number)
    return _slot_response(slot_number, tables)


@router.post("/plans/{plan_id}/publish", summary="Planı yayınla")
async def publish_plan(plan_id: int, event: OwnedEvent, session: SessionDep) -> PlanSummaryResponse:
    """*"Plan durumu 'yayında' olur, katılımcılar kendi yerlerini görmeye
    başlar. Varsa önceki yayındaki plan 'arşiv' durumuna geçer."* (M7)"""
    plan = await _require_plan(session, event, plan_id)
    try:
        await publish(session, event, plan)
    except SwapRejected as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.message) from error
    return await _to_response(session, plan)


@router.get("/plans/{plan_id}/changes", summary="Kimin yeri değişti")
async def read_plan_changes(
    plan_id: int, event: OwnedEvent, session: SessionDep
) -> PlanChangesResponse:
    """*"Yeni versiyon organizatöre gösterilir, kimin yeri değişti
    listelenir."* (M10)

    9.8'in sözü burada ölçülüyor: *"gerekmedikçe kimseyi kıpırdatma."*
    Öncesi olmayan bir plan (ilk versiyon) boş liste döndürüyor —
    karşılaştırılacak bir şey yok.
    """
    plan = await _require_plan(session, event, plan_id)
    if plan.previous_plan_id is None:
        return PlanChangesResponse(previous_plan_id=None, changes=[], moved_people=0)

    rows = await seat_changes(
        session,
        event.id,
        plan.id,
        plan.previous_plan_id,
        absentees=await absentees_of(session, plan),
    )
    return PlanChangesResponse(
        previous_plan_id=plan.previous_plan_id,
        changes=[
            SeatChangeResponse(
                registration_id=row.registration_id,
                name=row.name,
                slot_number=row.slot_number,
                before=row.before,
                after=row.after,
            )
            for row in rows
        ],
        moved_people=len({row.registration_id for row in rows}),
    )
