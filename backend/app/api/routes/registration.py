"""Etkinlik keşfi ve başvuru uçları (şartname M3).

İki taraf var ve ikisi farklı şey görüyor:

* **Katılımcı** yaklaşan etkinlikleri listeler, detayına bakar, başvurur.
  Gördüğü alanlar organizatörün gördüğünden az — `auto_approve_registrations`
  gibi bilgiler dışarı çıkmıyor (Bölüm 7).
* **Organizatör** kendi etkinliğinin başvurularını görür, onaylar veya
  reddeder. `OwnedEvent` bağımlılığı başkasının listesine 404 döndürüyor.

Kapıların hepsi `app.services.registration` içinde; buradaki işler yükleme,
sayma ve hatayı HTTP'ye çevirme.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, OwnedEvent, SessionDep, StorageDep
from app.models import (
    Event,
    EventStatus,
    Profile,
    Registration,
    RegistrationStatus,
    User,
)
from app.schemas.company import CompanyResponse
from app.schemas.event import SlotTimingResponse
from app.schemas.registration import (
    ApplicantResponse,
    DiscoverEventResponse,
    MyRegistrationResponse,
    PublicEventResponse,
    RegistrationResponse,
    RegistrationSummaryResponse,
)
from app.schemas.taxonomy import SectorResponse
from app.services.profile import evaluate_profile
from app.services.registration import (
    ApplicationBlocked,
    ProfileIncomplete,
    RegistrationCounts,
    check_can_apply,
    check_can_approve,
    initial_status,
    is_open_for_applications,
    new_qr_code,
)
from app.services.schedule import build_schedule
from app.services.storage import Storage

router = APIRouter(tags=["basvuru"])

# Başvuru listesinin süzgeci. `status` adıyla geliyor; Python tarafında
# `status` FastAPI'nin durum kodu modülüyle çakıştığı için ad ayrı.
StatusFilter = Annotated[RegistrationStatus | None, Query(alias="status")]


# --- Yükleme yardımcıları ----------------------------------------------------


def _counts_subquery() -> Select:
    """Etkinlik başına durum sayıları.

    Tek sorguda toplanıyor: keşif listesi yüzlerce etkinlik döndürebilir, her
    biri için ayrı sayım N+1 olurdu.
    """
    return (
        select(
            Registration.event_id.label("event_id"),
            func.count()
            .filter(Registration.status == RegistrationStatus.ACCEPTED)
            .label("accepted"),
            func.count().filter(Registration.status == RegistrationStatus.PENDING).label("pending"),
        )
        .group_by(Registration.event_id)
        .subquery()
    )


async def _counts_for(session: SessionDep, event_id: int) -> RegistrationCounts:
    result = await session.execute(
        select(Registration.status, func.count())
        .where(Registration.event_id == event_id)
        .group_by(Registration.status)
    )
    tally = dict(result.all())
    return RegistrationCounts(
        accepted=tally.get(RegistrationStatus.ACCEPTED, 0),
        pending=tally.get(RegistrationStatus.PENDING, 0),
    )


async def _my_registration(session: SessionDep, event_id: int, user_id: int) -> Registration | None:
    result = await session.execute(
        select(Registration)
        .where(Registration.event_id == event_id, Registration.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


def _mine(registration: Registration | None) -> MyRegistrationResponse | None:
    """Geri çekilmiş başvuru "başvurmadı" sayılıyor.

    Satır silinmiyor (aynı kişi tekrar başvurabilsin diye) ama kullanıcıya
    iptal edilmiş bir başvuruyu göstermenin anlamı yok.
    """
    if registration is None or registration.status is RegistrationStatus.CANCELLED:
        return None
    return MyRegistrationResponse(
        id=registration.id,
        status=registration.status,
        applied_at=registration.applied_at,
    )


def _cover(event: Event, storage: Storage) -> str | None:
    return storage.public_url(event.cover_image_key) if event.cover_image_key else None


# --- Katılımcı: keşif --------------------------------------------------------


@router.get("/events/discover", summary="Yaklaşan etkinlikler")
async def discover_events(
    user: CurrentUser, session: SessionDep, storage: StorageDep
) -> list[DiscoverEventResponse]:
    """*"Yaklaşan etkinliklerin listesi."* (M3)

    Taslaklar ve başlamış etkinlikler listede yok. Kontenjanı dolmuş veya son
    tarihi geçmiş etkinlik **kalıyor**: kart neden başvurulamadığını söylüyor,
    listeden sessizce kaybolması kullanıcıyı şaşırtırdı.

    Kullanıcının kendi düzenlediği etkinlikler de görünüyor — rol etkinliğe
    göre belirleniyor (Bölüm 7) ve keşif herkesin gördüğü liste. Başvuru
    düğmesini uç zaten kapatıyor.
    """
    now = datetime.now(UTC)
    counts = _counts_subquery()

    result = await session.execute(
        select(Event, counts.c.accepted, counts.c.pending)
        .outerjoin(counts, counts.c.event_id == Event.id)
        .where(Event.status != EventStatus.DRAFT, Event.starts_at > now)
        .order_by(Event.starts_at)
    )
    rows = result.all()
    if not rows:
        return []

    events = [row[0] for row in rows]
    mine = await session.execute(
        select(Registration).where(
            Registration.user_id == user.id,
            Registration.event_id.in_([event.id for event in events]),
        )
    )
    by_event = {item.event_id: item for item in mine.scalars()}

    cards = []
    for event, accepted, pending in rows:
        tally = RegistrationCounts(accepted=accepted or 0, pending=pending or 0)
        cards.append(
            DiscoverEventResponse(
                id=event.id,
                name=event.name,
                cover_url=_cover(event, storage),
                starts_at=event.starts_at,
                venue_name=event.venue_name,
                slot_count=event.slot_count,
                capacity=event.capacity,
                remaining_capacity=tally.remaining(event.capacity),
                registration_deadline=event.registration_deadline,
                is_open=is_open_for_applications(event, tally, now=now),
                my_registration=_mine(by_event.get(event.id)),
            )
        )
    return cards


async def _load_visible_event(session: SessionDep, event_id: int) -> Event:
    """Katılımcının görebileceği etkinlik.

    Taslak etkinlik yok sayılıyor: organizatör henüz yayınlamadı, varlığı bile
    sızmamalı (Bölüm 7). Organizatör kendi taslağını `GET /events/{id}`
    üzerinden görüyor.
    """
    event = await session.get(Event, event_id)
    if event is None or event.status is EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Etkinlik bulunamadı.",
        )
    return event


@router.get("/events/{event_id}/public", summary="Etkinlik detayı (katılımcı)")
async def read_public_event(
    event_id: int, user: CurrentUser, session: SessionDep, storage: StorageDep
) -> PublicEventResponse:
    """*"Detay ekranı: açıklama, program (slot saatleri hesaplanmış halde), yer
    bilgisi, kaç kişi katılıyor, başvur butonu."* (M3)"""
    event = await _load_visible_event(session, event_id)
    counts = await _counts_for(session, event_id)
    schedule = build_schedule(
        starts_at=event.starts_at,
        slot_duration_minutes=event.slot_duration_minutes,
        break_duration_minutes=event.break_duration_minutes,
        slot_count=event.slot_count,
    )

    return PublicEventResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        cover_url=_cover(event, storage),
        starts_at=event.starts_at,
        venue_name=event.venue_name,
        address=event.address,
        slot_duration_minutes=event.slot_duration_minutes,
        break_duration_minutes=event.break_duration_minutes,
        slot_count=event.slot_count,
        schedule=[
            SlotTimingResponse(number=slot.number, starts_at=slot.starts_at, ends_at=slot.ends_at)
            for slot in schedule.slots
        ],
        ends_at=schedule.ends_at,
        total_minutes=schedule.total_minutes,
        capacity=event.capacity,
        remaining_capacity=counts.remaining(event.capacity),
        accepted_count=counts.accepted,
        registration_deadline=event.registration_deadline,
        is_open=is_open_for_applications(event, counts),
        my_registration=_mine(await _my_registration(session, event_id, user.id)),
    )


# --- Katılımcı: başvuru ------------------------------------------------------


@router.post(
    "/events/{event_id}/registration",
    status_code=status.HTTP_201_CREATED,
    summary="Etkinliğe başvur",
)
async def apply_to_event(
    event_id: int, user: CurrentUser, session: SessionDep, storage: StorageDep
) -> PublicEventResponse:
    """Başvuruyu oluşturur (M3).

    Geri çekilmiş bir başvuru varsa satır yeniden kullanılıyor: silmek,
    `uq_registrations_event_user` ile birlikte sessiz bir yeniden başvuru yolu
    açardı.
    """
    event = await _load_visible_event(session, event_id)
    # `Profile`'ın birincil anahtarı `user_id` değil; kullanıcıya bağlı satır
    # tekil indeksten geliyor. Etiketler yükleniyor: başvuru yeterliliği
    # "en az üçer etiket" kuralını sayıyor.
    profile = (
        await session.execute(
            select(Profile).where(Profile.user_id == user.id).options(selectinload(Profile.tags))
        )
    ).scalar_one_or_none()
    existing = await _my_registration(session, event_id, user.id)
    counts = await _counts_for(session, event_id)

    try:
        check_can_apply(
            event,
            counts,
            user_id=user.id,
            profile_missing=(evaluate_profile(profile).missing_for_application if profile else ()),
            existing=existing,
        )
    except ProfileIncomplete as error:
        # 422 ve eksik listesi: kullanıcı neyi düzelteceğini görmeli. Türkçe
        # cümleyi arayüz kuruyor (Aşama 3'teki kalıp).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Profilin başvuru için yeterli değil.",
                "missing_for_application": list(error.missing),
            },
        ) from error
    except ApplicationBlocked as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.message) from error

    if existing is not None:
        existing.status = initial_status(event)
        existing.applied_at = datetime.now(UTC)
    else:
        session.add(
            Registration(
                event_id=event_id,
                user_id=user.id,
                status=initial_status(event),
                qr_code=new_qr_code(),
            )
        )

    try:
        await session.commit()
    except IntegrityError as error:
        # Aynı kullanıcı iki isteği aynı anda gönderdiyse buraya düşer;
        # `uq_registrations_event_user` arkada bekçilik ediyor.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu etkinliğe zaten başvurdun.",
        ) from error

    return await read_public_event(event_id, user, session, storage)


@router.delete("/events/{event_id}/registration", summary="Başvurumu geri çek")
async def withdraw_from_event(
    event_id: int, user: CurrentUser, session: SessionDep, storage: StorageDep
) -> PublicEventResponse:
    """Başvuruyu iptal eder, satırı silmez.

    Kabul edilmiş başvuru da geri çekilebiliyor: katılamayacağını anlayan
    kişinin yeri boşalmalı, yoksa kontenjan gereksiz yere dolu kalır.
    """
    await _load_visible_event(session, event_id)
    registration = await _my_registration(session, event_id, user.id)

    if registration is None or registration.status is RegistrationStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu etkinliğe başvurun yok.",
        )

    registration.status = RegistrationStatus.CANCELLED
    await session.commit()
    return await read_public_event(event_id, user, session, storage)


# --- Organizatör: başvuru yönetimi -------------------------------------------


@router.get("/events/{event_id}/registrations", summary="Başvurular")
async def list_registrations(
    event: OwnedEvent,
    session: SessionDep,
    storage: StorageDep,
    registration_status: StatusFilter = None,
) -> RegistrationSummaryResponse:
    """Organizatörün başvuru listesi.

    `OwnedEvent` başkasının etkinliğine 404 döndürüyor (Bölüm 7). Süzgeç
    verilmezse iptal edilenler hariç hepsi geliyor — geri çekilmiş başvuru
    organizatörü ilgilendirmiyor.
    """
    query = (
        select(Registration)
        .where(Registration.event_id == event.id)
        .options(
            # Başvuranın profili onay kararının dayanağı; şirket ve sektör de
            # satırda görünüyor, tek sorguda getiriliyor.
            selectinload(Registration.user)
            .selectinload(User.profile)
            .options(selectinload(Profile.company), selectinload(Profile.sector))
        )
        .order_by(Registration.applied_at)
    )
    query = query.where(
        Registration.status == registration_status
        if registration_status is not None
        else Registration.status != RegistrationStatus.CANCELLED
    )

    rows = (await session.execute(query)).scalars().all()
    counts = await _counts_for(session, event.id)
    rejected = await session.execute(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.event_id == event.id,
            Registration.status == RegistrationStatus.REJECTED,
        )
    )

    return RegistrationSummaryResponse(
        registrations=[_registration_row(item, storage) for item in rows],
        pending_count=counts.pending,
        accepted_count=counts.accepted,
        rejected_count=rejected.scalar_one(),
        capacity=event.capacity,
        remaining_capacity=counts.remaining(event.capacity),
    )


def _registration_row(registration: Registration, storage: Storage) -> RegistrationResponse:
    profile = registration.user.profile
    return RegistrationResponse(
        id=registration.id,
        status=registration.status,
        applied_at=registration.applied_at,
        applicant=ApplicantResponse(
            full_name=profile.full_name if profile else None,
            title=profile.title if profile else None,
            photo_url=(
                storage.public_url(profile.photo_key) if profile and profile.photo_key else None
            ),
            company=(
                CompanyResponse.model_validate(profile.company)
                if profile and profile.company
                else None
            ),
            sector=(
                SectorResponse.model_validate(profile.sector)
                if profile and profile.sector
                else None
            ),
        ),
    )


async def _load_registration(session: SessionDep, event_id: int, registration_id: int):
    result = await session.execute(
        select(Registration)
        .where(Registration.id == registration_id, Registration.event_id == event_id)
        .execution_options(populate_existing=True)
    )
    registration = result.scalar_one_or_none()
    if registration is None:
        # Başka bir etkinliğin başvurusu da buraya düşer.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Başvuru bulunamadı.")
    return registration


@router.post(
    "/events/{event_id}/registrations/{registration_id}/approve",
    summary="Başvuruyu onayla",
)
async def approve_registration(
    registration_id: int, event: OwnedEvent, session: SessionDep, storage: StorageDep
) -> RegistrationSummaryResponse:
    registration = await _load_registration(session, event.id, registration_id)

    if registration.status is not RegistrationStatus.ACCEPTED:
        try:
            check_can_approve(event, await _counts_for(session, event.id))
        except ApplicationBlocked as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=error.message
            ) from error
        registration.status = RegistrationStatus.ACCEPTED
        await session.commit()

    # Süzgeç açıkça `None`: doğrudan çağrıda FastAPI'nin `Query` varsayılanı
    # değer olarak geçerdi.
    return await list_registrations(event, session, storage, registration_status=None)


@router.post(
    "/events/{event_id}/registrations/{registration_id}/reject",
    summary="Başvuruyu reddet",
)
async def reject_registration(
    registration_id: int, event: OwnedEvent, session: SessionDep, storage: StorageDep
) -> RegistrationSummaryResponse:
    """Red her zaman serbest: kontenjan kontrolü yalnızca onayda anlamlı."""
    registration = await _load_registration(session, event.id, registration_id)
    registration.status = RegistrationStatus.REJECTED
    await session.commit()
    # Süzgeç açıkça `None`: doğrudan çağrıda FastAPI'nin `Query` varsayılanı
    # değer olarak geçerdi.
    return await list_registrations(event, session, storage, registration_status=None)
