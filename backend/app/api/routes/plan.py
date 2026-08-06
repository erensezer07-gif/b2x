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
from app.models import JobStatus, Plan
from app.schemas.plan import (
    MatchingCheckResponse,
    PlanSummaryResponse,
    RunMatchingRequest,
)
from app.services.matching import build_matching_check
from app.services.plan_runner import (
    assignment_count,
    create_queued_plan,
    seated_participant_count,
)

router = APIRouter(prefix="/events/{event_id}", tags=["esletirme"])

# İşçideki fonksiyonun adı. Kuyruk adla çalışıyor, referansla değil.
MATCHING_JOB = "run_matching_job"


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

    running = await session.execute(
        select(Plan).where(
            Plan.event_id == event.id,
            Plan.job_status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    if running.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu etkinlik için bir eşleştirme zaten çalışıyor.",
        )

    plan = await create_queued_plan(session, event, payload.seed)
    await session.commit()

    # Kuyruk ulaşılamazsa `None` dönüyor ve plan `queued` kalıyor; ayrıntı
    # `app/services/queue.py` içinde.
    plan.job_id = await queue.enqueue(MATCHING_JOB, plan.id)
    await session.commit()

    return await _to_response(session, plan)


@router.get("/plans", summary="Plan versiyonları")
async def list_plans(event: OwnedEvent, session: SessionDep) -> list[PlanSummaryResponse]:
    """Yeni versiyon önce: organizatör en son çalıştırmayı arıyor."""
    result = await session.execute(
        select(Plan).where(Plan.event_id == event.id).order_by(Plan.version.desc())
    )
    return [await _to_response(session, plan) for plan in result.scalars()]


@router.get("/plans/{plan_id}", summary="Plan ve hesabın durumu")
async def read_plan(plan_id: int, event: OwnedEvent, session: SessionDep) -> PlanSummaryResponse:
    result = await session.execute(
        select(Plan)
        .where(Plan.id == plan_id, Plan.event_id == event.id)
        .execution_options(populate_existing=True)
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        # Başka bir etkinliğin planı da buraya düşer (Bölüm 7).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan bulunamadı.")
    return await _to_response(session, plan)
