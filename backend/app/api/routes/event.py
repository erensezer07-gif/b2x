"""Etkinlik uçları (şartname M4).

Organizatörün sihirbazı bu uçları çağırıyor. Her adım kendi verisini kaydediyor;
etkinlik taslak olarak durur ve sonra devam edilebilir.

**Yetki:** her uç `OwnedEvent` bağımlılığından geçiyor — kullanıcı yalnızca
kendi oluşturduğu etkinliğe erişebilir (Bölüm 7). Ayrı bir rol tablosu yok; rol
etkinliğe göre belirleniyor.
"""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, OwnedEvent, SessionDep, StorageDep
from app.models import Event, EventStatus, Layout
from app.schemas.event import (
    EventCreateRequest,
    EventResponse,
    EventSummaryResponse,
    EventUpdateRequest,
)
from app.services.event import build_event_response, is_event_info_complete
from app.services.storage import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES, StorageError

router = APIRouter(prefix="/events", tags=["etkinlik"])


async def _load_layout(session: SessionDep, event_id: int) -> Layout | None:
    """Etkinliğin düzenini masalarıyla birlikte getirir."""
    result = await session.execute(
        select(Layout)
        .where(Layout.event_id == event_id)
        .options(selectinload(Layout.tables))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _respond(session: SessionDep, event: Event, storage: StorageDep) -> EventResponse:
    return build_event_response(event, await _load_layout(session, event.id), storage)


@router.get("", summary="Oluşturduğum etkinlikler")
async def list_events(user: CurrentUser, session: SessionDep) -> list[EventSummaryResponse]:
    """Kullanıcının organizatör olduğu etkinlikler.

    Başkalarının etkinlikleri burada görünmez; etkinlik keşfi Aşama 6'nın konusu
    ve ayrı bir uç olacak.
    """
    result = await session.execute(
        select(Event).where(Event.organizer_id == user.id).order_by(Event.starts_at.desc())
    )
    return [EventSummaryResponse.model_validate(event) for event in result.scalars()]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Taslak etkinlik oluştur")
async def create_event(
    payload: EventCreateRequest,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> EventResponse:
    """Sihirbazın ilk adımı.

    Etkinlik taslak olarak açılıyor; kalan alanlar sonraki adımlarda `PATCH` ile
    dolduruluyor (M4).
    """
    event = Event(
        organizer_id=user.id,
        name=payload.name,
        starts_at=payload.starts_at,
        slot_duration_minutes=payload.slot_duration_minutes,
        break_duration_minutes=payload.break_duration_minutes,
        slot_count=payload.slot_count,
        capacity=payload.capacity,
        status=EventStatus.DRAFT,
        # Sihirbazın kontenjan adımında değiştirilecek; buradaki değerler
        # yalnızca taslağın geçerli olması için.
        auto_approve_registrations=True,
        request_quota=3,
    )
    session.add(event)
    await session.commit()

    return await _respond(session, event, storage)


@router.get("/{event_id}", summary="Etkinlik detayı")
async def read_event(event: OwnedEvent, session: SessionDep, storage: StorageDep) -> EventResponse:
    return await _respond(session, event, storage)


@router.patch("/{event_id}", summary="Etkinliği güncelle")
async def update_event(
    payload: EventUpdateRequest,
    event: OwnedEvent,
    session: SessionDep,
    storage: StorageDep,
) -> EventResponse:
    """Sihirbazın her adımı bu ucu çağırıyor.

    Yalnızca gönderilen alanlar değişiyor — bir adımı kaydetmek diğerinin
    verisini silmiyor.
    """
    if event.status is not EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıtları açılmış veya tamamlanmış bir etkinlikte değişiklik yapılamaz.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    await session.commit()
    return await _respond(session, event, storage)


@router.post("/{event_id}/cover", summary="Kapak görseli yükle")
async def upload_cover(
    event: OwnedEvent,
    session: SessionDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File(description="JPEG, PNG veya WebP")],
) -> EventResponse:
    if event.status is not EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıtları açılmış veya tamamlanmış bir etkinlikte değişiklik yapılamaz.",
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Yalnızca JPEG, PNG veya WebP yükleyebilirsin.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Dosya boş.")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Görsel en fazla {MAX_IMAGE_BYTES // (1024 * 1024)} MB olabilir.",
        )

    previous_key = event.cover_image_key
    try:
        event.cover_image_key = await storage.save(
            content, folder="event-covers", content_type=content_type
        )
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Görsel kaydedilemedi, az sonra tekrar dene.",
        ) from error

    await session.commit()

    # Eski dosya yenisi kaydedildikten sonra siliniyor: ters sırada yükleme
    # yarıda kalırsa organizatör ikisinden de olurdu.
    if previous_key:
        await _delete_quietly(storage, previous_key)

    return await _respond(session, event, storage)


@router.delete("/{event_id}/cover", summary="Kapak görselini kaldır")
async def delete_cover(
    event: OwnedEvent, session: SessionDep, storage: StorageDep
) -> EventResponse:
    if event.status is not EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıtları açılmış veya tamamlanmış bir etkinlikte değişiklik yapılamaz.",
        )

    key = event.cover_image_key
    event.cover_image_key = None
    await session.commit()

    if key:
        await _delete_quietly(storage, key)

    return await _respond(session, event, storage)


@router.post("/{event_id}/open-registration", summary="Kayıtları aç")
async def open_registration(
    event: OwnedEvent, session: SessionDep, storage: StorageDep
) -> EventResponse:
    """Kayıtları açar.

    Bölüm 10 kabul kriteri: *"Salon düzeni kurulmadan kayıtlar açılamıyor."*
    Bu bir kapı, uyarı değil — düzen yoksa istek reddediliyor.

    Kapasite uyarısı ise engel değil (M4): kontenjan salondan büyük olsa bile
    kayıtlar açılabilir, çünkü gelmeyecekler hesaba katılmış olabilir.
    """
    if not is_event_info_complete(event):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıtları açmadan önce etkinlik bilgilerini (ad, yer, adres, açıklama) eksiksiz doldurmalısın.",
        )

    layout = await _load_layout(session, event.id)
    if layout is None or not layout.tables:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıtları açmadan önce salon düzenini kurmalısın.",
        )

    if event.status is EventStatus.DRAFT:
        event.status = EventStatus.REGISTRATION_OPEN
        await session.commit()

    return await _respond(session, event, storage)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Etkinliği sil")
async def delete_event(
    event: OwnedEvent, session: SessionDep, storage: StorageDep
) -> None:
    """Organizatörün kendi etkinliğini silmesi.

    Varsa kapak görseli depodan temizlenir; veritabanı ilişkileri (düzen, masalar vb.)
    otomatik silinir.
    """
    key = event.cover_image_key
    await session.delete(event)
    await session.commit()

    if key:
        await _delete_quietly(storage, key)


async def _delete_quietly(storage: StorageDep, key: str) -> None:
    """Artık kullanılmayan dosyayı siler; başarısız olursa isteği düşürmez."""
    try:
        await storage.delete(key)
    except StorageError:
        pass
