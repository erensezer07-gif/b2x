"""Görüşme talebi uçları (şartname M9).

Katılımcı tarafı. Kimlik jetondan geliyor — Aşama 9'daki kalıp: başkası adına
talep göndermek diye bir istek biçimi kurulmadı.

**Gelen talep ucu yok.** M9: *"Talep gönderildiği kişiye bildirilmez."* Uç hiç
yazılmadığı için sızacak yer de yok.

Organizatörün gördüğü karşılanmayan talepler bu dosyada değil — o plana bağlı
bir bilgi, `plan.py` içindeki plan özetiyle birlikte dönüyor.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, StorageDep
from app.models import Event, Profile, Registration, RegistrationStatus, User
from app.schemas.meeting_request import (
    ParticipantListResponse,
    ParticipantRowResponse,
    SendRequestBody,
)
from app.services.company import normalize_company_name
from app.services.meeting_request import (
    RequestBlocked,
    quota_of,
    requests_open,
    send_request,
    sent_requests,
    withdraw_request,
)
from app.services.participant_plan import accepted_registration

router = APIRouter(prefix="/events/{event_id}", tags=["gorusme-talepleri"])

_NOT_A_PARTICIPANT = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Bu etkinliğin katılımcısı değilsin.",
)

SearchQuery = Annotated[str | None, Query(alias="q", max_length=100)]
SectorFilter = Annotated[int | None, Query(alias="sector_id")]


async def _require_participation(
    session: SessionDep, event_id: int, user: CurrentUser
) -> tuple[Event, Registration]:
    """Etkinliği yükler ve kabul edilmiş katılımcı olduğunu doğrular.

    Etkinlik yokken de, başvuru kabul edilmemişken de aynı 404 — iki durumu
    ayırmak "bu etkinlik var ama sen giremezsin" bilgisini sızdırırdı
    (Bölüm 7).
    """
    event = await session.get(Event, event_id)
    if event is None:
        raise _NOT_A_PARTICIPANT

    registration = await accepted_registration(session, event_id, user.id)
    if registration is None:
        raise _NOT_A_PARTICIPANT
    return event, registration


@router.get("/participants", summary="Etkinliğin katılımcıları")
async def list_participants(
    event_id: int,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    search: SearchQuery = None,
    sector_id: SectorFilter = None,
) -> ParticipantListResponse:
    """*"Katılımcı, kabul edilmiş diğer katılımcıların listesini görür.
    Arama ve sektöre göre filtreleme var."* (M9)

    Liste **tam profil açmıyor**: ad, unvan, şirket, sektör. Tam profil
    yalnızca aynı masaya düşenler için (Bölüm 7).
    """
    event, me = await _require_participation(session, event_id, user)

    result = await session.execute(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.ACCEPTED,
            # Kişinin kendisi listede yok: kendine talep gönderemiyor.
            Registration.id != me.id,
        )
        .options(
            selectinload(Registration.user)
            .selectinload(User.profile)
            .options(selectinload(Profile.company), selectinload(Profile.sector))
        )
        .order_by(Registration.id)
    )

    mine = await sent_requests(session, me.id)
    needle = normalize_company_name(search) if search else ""

    rows = []
    for registration in result.scalars():
        profile = registration.user.profile
        company = profile.company.name if profile and profile.company else None
        sector = profile.sector if profile and profile.sector else None

        if sector_id is not None and (sector is None or sector.id != sector_id):
            continue
        # Arama ad ve şirkette; şirket normalleştirmesinin aynısı kullanılıyor
        # ki "A.Ş." ile "AŞ" aynı sonucu versin.
        if needle:
            haystack = normalize_company_name(
                f"{profile.full_name if profile else ''} {company or ''}"
            )
            if needle not in haystack:
                continue

        request = mine.get(registration.id)
        rows.append(
            ParticipantRowResponse(
                registration_id=registration.id,
                full_name=profile.full_name if profile else None,
                title=profile.title if profile else None,
                company=company,
                sector=sector.name if sector else None,
                photo_url=(
                    storage.public_url(profile.photo_key) if profile and profile.photo_key else None
                ),
                my_request_id=request.id if request else None,
            )
        )

    quota = await quota_of(session, event, me.id)
    return ParticipantListResponse(
        participants=rows,
        request_quota=quota.quota,
        requests_used=quota.used,
        requests_remaining=quota.remaining,
        requests_open=requests_open(event),
    )


@router.post(
    "/requests",
    status_code=status.HTTP_201_CREATED,
    summary="Görüşme talebi gönder",
)
async def create_request(
    event_id: int,
    payload: SendRequestBody,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> ParticipantListResponse:
    """*"Bir kişiye 'görüşmek istiyorum' talebi gönderilebilir."* (M9)

    Güncel liste dönüyor: kalan hak ve satırın yeni hâli tek istekte
    geliyor, ekran ikinci bir çağrı yapmıyor (Aşama 8'deki takas kalıbı).
    """
    event, me = await _require_participation(session, event_id, user)
    try:
        await send_request(session, event, me, payload.target_registration_id)
    except RequestBlocked as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.message) from error

    return await list_participants(event_id, user, session, storage)


@router.delete("/requests/{request_id}", summary="Talebi geri çek")
async def delete_request(
    event_id: int,
    request_id: int,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> ParticipantListResponse:
    """Talebi geri çeker ve hakkı iade eder (M9).

    Başkasının talebi geri çekilemez: sorgu istek sahibine bağlı ve kimlik
    jetondan geliyor.
    """
    event, me = await _require_participation(session, event_id, user)
    try:
        await withdraw_request(session, event, me, request_id)
    except RequestBlocked as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.message) from error

    return await list_participants(event_id, user, session, storage)
