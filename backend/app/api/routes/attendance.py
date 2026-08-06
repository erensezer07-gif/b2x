"""Check-in uçları (şartname M10).

İki taraf var:

* **Katılımcı** yalnızca kendi giriş kodunu okuyor. Başkasının kodunu
  istemek diye bir istek biçimi yok — kimlik jetondan geliyor.
* **Organizatör** listeyi görüyor, kod okutuyor, elle işaretliyor.
  `OwnedEvent` başkasının etkinliğine 404 döndürüyor.

Kapılar `app/services/attendance.py` içinde; buradaki işler yükleme ve hatayı
HTTP'ye çevirme.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, OwnedEvent, SessionDep, StorageDep
from app.models import AttendanceStatus, Event, Registration
from app.schemas.attendance import (
    AttendanceResponse,
    AttendeeResponse,
    MarkAttendanceRequest,
    MyQrResponse,
    ScanRequest,
    ScanResponse,
)
from app.services.attendance import (
    CheckInFailed,
    counts,
    find_by_code,
    mark,
    roster,
)
from app.services.participant_plan import accepted_registration
from app.services.storage import Storage

router = APIRouter(prefix="/events/{event_id}", tags=["check-in"])

SearchQuery = Annotated[str | None, Query(alias="q", max_length=100)]


def _attendee(registration: Registration, storage: Storage) -> AttendeeResponse:
    profile = registration.user.profile
    return AttendeeResponse(
        registration_id=registration.id,
        full_name=profile.full_name if profile else None,
        title=profile.title if profile else None,
        company=profile.company.name if profile and profile.company else None,
        photo_url=(
            storage.public_url(profile.photo_key) if profile and profile.photo_key else None
        ),
        present=registration.attendance is AttendanceStatus.PRESENT,
        checked_in_at=registration.checked_in_at,
    )


@router.get("/my-qr", summary="Kendi giriş kodum")
async def read_my_qr(event_id: int, user: CurrentUser, session: SessionDep) -> MyQrResponse:
    """*"Her kabul edilmiş katılımcı için benzersiz bir kod üretilir."* (M10)

    Kod metin olarak dönüyor; QR'ı istemci çiziyor. *"İnternet olmasa bile
    görüntülenebilmeli"* — sunucudan görsel çekmek bunu bozardı.
    """
    registration = await accepted_registration(session, event_id, user.id)
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu etkinliğin katılımcısı değilsin.",
        )
    return MyQrResponse(
        registration_id=registration.id,
        qr_code=registration.qr_code,
        checked_in_at=registration.checked_in_at,
    )


async def _snapshot(
    session: SessionDep, event: Event, storage: Storage, search: str | None = None
) -> AttendanceResponse:
    """Liste ve sayaç.

    Sayaç **süzgeçten etkilenmiyor**: arama yaparken "kaç kişi bekleniyor"
    bilgisi kaybolmamalı.
    """
    people = await roster(session, event.id, search=search)
    totals = await counts(session, event.id)
    return AttendanceResponse(
        attendees=[_attendee(item, storage) for item in people],
        accepted_count=totals.accepted,
        present_count=totals.present,
        expected_count=totals.expected,
    )


@router.get("/attendance", summary="Check-in listesi ve sayaç")
async def read_attendance(
    event: OwnedEvent,
    session: SessionDep,
    storage: StorageDep,
    search: SearchQuery = None,
) -> AttendanceResponse:
    """*"Elle arama da olmalı — telefonu bozulan, kodu bulamayan kişi listeden
    bulunup elle işaretlenebilir."* (M10)"""
    return await _snapshot(session, event, storage, search)


@router.post("/attendance/scan", summary="Giriş kodu okut")
async def scan_code(
    payload: ScanRequest,
    event: OwnedEvent,
    session: SessionDep,
    storage: StorageDep,
) -> ScanResponse:
    """*"Okunan kişi 'geldi' olarak işaretlenir, ekranda adı ve fotoğrafı
    belirir."* (M10)

    Aynı kodu iki kez okutmak **hata değil** — kapıda olur. Yanıt
    `already_present` ile bunu söylüyor ve giriş zamanı ilk okumada kalıyor.
    """
    try:
        registration = await find_by_code(session, event.id, payload.qr_code)
    except CheckInFailed as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error.message) from error

    already = registration.attendance is AttendanceStatus.PRESENT
    await mark(session, registration, present=True)
    totals = await counts(session, event.id)

    return ScanResponse(
        attendee=_attendee(registration, storage),
        accepted_count=totals.accepted,
        present_count=totals.present,
        expected_count=totals.expected,
        already_present=already,
    )


@router.post("/attendance/{registration_id}", summary="Elle işaretle")
async def mark_attendance(
    registration_id: int,
    payload: MarkAttendanceRequest,
    event: OwnedEvent,
    session: SessionDep,
    storage: StorageDep,
) -> AttendanceResponse:
    """Elle geldi/gelmedi işaretleme.

    Geri alınabiliyor: yanlış kişi okutulmuş olabilir. `checked_in_at` durumla
    birlikte değişiyor — şemadaki `checkin_consistent` kısıtı ikisinin
    ayrışmasını engelliyor.
    """
    people = await roster(session, event.id)
    registration = next((item for item in people if item.id == registration_id), None)
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu etkinlikte böyle bir katılımcı yok.",
        )

    await mark(session, registration, present=payload.present)
    return await _snapshot(session, event, storage)
