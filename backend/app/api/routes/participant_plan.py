"""Katılımcının kendi planı (şartname M8, Bölüm 7).

Üç uç, üçü de **kimliği jetondan** alıyor. `registration_id` parametresi
yok: başkasının planını istemek diye bir istek biçimi kurulmadı.

Görünürlük kararlarının hepsi `app/services/participant_plan.py` içinde;
buradaki işler yükleme, yetki kapısı ve şemaya çevirme.

Organizatörün gördüğü uçlar ayrı (`plan.py`). Katılımcı yanıtında skor,
masa kalitesi ve kırılım **hiç yok** — alan gizlemek yerine ayrı şema.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep, StorageDep
from app.models import Event, Profile, Registration, TagDirection
from app.schemas.company import CompanyResponse
from app.schemas.participant_plan import (
    MatchReasonResponse,
    MyPlanResponse,
    MySlotResponse,
    TablemateProfileResponse,
    TablemateResponse,
    VenueAreaResponse,
    VenueResponse,
    VenueTableResponse,
)
from app.schemas.taxonomy import SectorResponse, TagResponse
from app.services.participant_plan import (
    accepted_registration,
    build_my_plan,
    load_venue,
    visible_profile,
)
from app.services.storage import Storage

router = APIRouter(prefix="/events/{event_id}", tags=["katilimci-plani"])

_NOT_A_PARTICIPANT = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Bu etkinliğin katılımcısı değilsin.",
)


async def _require_participation(
    session: SessionDep, event_id: int, user: CurrentUser
) -> tuple[Event, Registration]:
    """Etkinliği yükler ve kullanıcının **kabul edilmiş** katılımcı olduğunu doğrular.

    Etkinlik yokken de, başvuru kabul edilmemişken de aynı 404 dönüyor: iki
    durumu ayırmak "bu etkinlik var ama sen giremezsin" bilgisini sızdırırdı
    (Bölüm 7, `get_owned_event`'teki gerekçenin aynısı).
    """
    event = await session.get(Event, event_id)
    if event is None:
        raise _NOT_A_PARTICIPANT

    registration = await accepted_registration(session, event_id, user.id)
    if registration is None:
        raise _NOT_A_PARTICIPANT
    return event, registration


@router.get("/my-plan", summary="Kendi oturma planım")
async def read_my_plan(
    event_id: int, user: CurrentUser, session: SessionDep, storage: StorageDep
) -> MyPlanResponse:
    """*"Katılımcının tüm slotları sırayla."* (M8)

    Plan yayınlanmadan hiçbir atama dönmüyor — `is_published` yanlış ve
    `slots` boş. *"Oturma planınız henüz hazırlanıyor"* cümlesini arayüz
    kuruyor.
    """
    event, registration = await _require_participation(session, event_id, user)
    plan = await build_my_plan(session, event, registration)

    return MyPlanResponse(
        is_published=plan.is_published,
        plan_version=plan.plan_version,
        slots=[
            MySlotResponse(
                slot_number=slot.slot_number,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                table_id=slot.table.id if slot.table else None,
                table_number=slot.table.number if slot.table else None,
                table_label=slot.table.label if slot.table else None,
                tablemates=[
                    TablemateResponse(
                        registration_id=mate.registration_id,
                        full_name=mate.profile.full_name if mate.profile else None,
                        title=mate.profile.title if mate.profile else None,
                        company=(
                            mate.profile.company.name
                            if mate.profile and mate.profile.company
                            else None
                        ),
                        photo_url=_photo(mate.profile, storage),
                        reasons=[
                            MatchReasonResponse(kind=reason.kind, values=list(reason.values))
                            for reason in mate.reasons
                        ],
                    )
                    for mate in slot.tablemates
                ],
            )
            for slot in plan.slots
        ],
    )


@router.get("/venue", summary="Salon krokisi")
async def read_venue(event_id: int, user: CurrentUser, session: SessionDep) -> VenueResponse:
    """*"Manuel düzen varsa: krokide masanın yeri işaretli."* (M8)

    Masa numaraları ve yerleri dönüyor, **kimin oturduğu dönmüyor.** O bilgi
    yalnızca `/my-plan` üzerinden ve yalnızca kendi masası için geliyor.
    """
    event, _registration = await _require_participation(session, event_id, user)
    layout, tables, areas = await load_venue(session, event.id)
    if layout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu etkinliğin salon düzeni kurulmamış.",
        )

    return VenueResponse(
        mode=layout.mode,
        grid_width=layout.grid_width,
        grid_height=layout.grid_height,
        tables=[
            VenueTableResponse(
                id=table.id,
                number=table.number,
                label=table.label,
                grid_x=table.grid_x,
                grid_y=table.grid_y,
            )
            for table in tables
        ],
        areas=[
            VenueAreaResponse(
                id=area.id,
                label=area.label,
                grid_x=area.grid_x,
                grid_y=area.grid_y,
                width=area.width,
                height=area.height,
            )
            for area in areas
        ],
    )


@router.get("/tablemates/{registration_id}", summary="Masa arkadaşının profili")
async def read_tablemate(
    event_id: int,
    registration_id: int,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> TablemateProfileResponse:
    """*"Sadece aynı masada oturduğu kişilerin profilini görebilir."* (M8)

    Masa arkadaşı olmayan biri istenirse **404** — 403 "böyle biri var ama
    göremezsin" bilgisini sızdırırdı. Kabul edilmiş ama başka masada oturan
    biri de buraya düşüyor.
    """
    event, registration = await _require_participation(session, event_id, user)
    profile = await visible_profile(session, event, registration, registration_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu kişi masa arkadaşın değil.",
        )

    def tags_for(direction: TagDirection) -> list[TagResponse]:
        return [
            TagResponse.model_validate(link.tag)
            for link in sorted(profile.tags, key=lambda item: item.tag_id)
            if link.direction is direction and link.tag
        ]

    return TablemateProfileResponse(
        registration_id=registration_id,
        full_name=profile.full_name,
        title=profile.title,
        city=profile.city,
        bio=profile.bio,
        photo_url=_photo(profile, storage),
        website=profile.website,
        linkedin_url=profile.linkedin_url,
        company=(CompanyResponse.model_validate(profile.company) if profile.company else None),
        sector=(SectorResponse.model_validate(profile.sector) if profile.sector else None),
        offered_tags=tags_for(TagDirection.OFFERED),
        sought_tags=tags_for(TagDirection.SOUGHT),
    )


def _photo(profile: Profile | None, storage: Storage) -> str | None:
    """Fotoğrafın tam adresi.

    Veritabanında anahtar duruyor; adres depolama arka ucuna göre üretiliyor
    (Bölüm 3).
    """
    if profile is None or not profile.photo_key:
        return None
    return storage.public_url(profile.photo_key)
