"""Profil uçları (şartname M2).

Kullanıcı yalnızca **kendi** profiline erişir. Başka katılımcıların profillerini
görme kuralları Aşama 9'un konusu ve orada da sunucuda uygulanacak (Bölüm 7);
burada kaynak zaten oturumdaki kullanıcıdan türetiliyor, dolayısıyla başkasının
profilini isteyecek bir parametre bile yok.
"""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, StorageDep
from app.models import Profile, ProfileTag, Tag, TagDirection
from app.schemas.company import CompanyResponse
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.schemas.taxonomy import SectorResponse, TagResponse
from app.services.profile import evaluate_profile
from app.services.storage import (
    ALLOWED_IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    Storage,
    StorageError,
)

router = APIRouter(prefix="/profile", tags=["profil"])


async def _load_profile(session: SessionDep, user_id: int) -> Profile:
    result = await session.execute(
        select(Profile)
        .where(Profile.user_id == user_id)
        .options(
            selectinload(Profile.company),
            selectinload(Profile.sector),
            selectinload(Profile.tags).selectinload(ProfileTag.tag),
        )
        # Güncelleme sonrası bu sorgu tekrar çalışıyor. `populate_existing`
        # olmadan SQLAlchemy kimlik haritasındaki nesneyi olduğu gibi döndürür ve
        # zaten yüklenmiş ilişkileri tazelemez: `company_id` değişmiş olsa bile
        # `company` eski hâliyle (çoğu zaman None) kalırdı.
        .execution_options(populate_existing=True)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        # Kayıt sırasında açılıyor; yoksa veri tutarsız demektir.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil bulunamadı.",
        )
    return profile


def _to_response(profile: Profile, storage: Storage) -> ProfileResponse:
    status_ = evaluate_profile(profile)

    def tags_for(direction: TagDirection) -> list[TagResponse]:
        return [
            TagResponse.model_validate(link.tag)
            for link in sorted(profile.tags, key=lambda item: item.tag_id)
            if link.direction == direction
        ]

    return ProfileResponse(
        full_name=profile.full_name,
        title=profile.title,
        city=profile.city,
        bio=profile.bio,
        # İstemciye anahtar değil kullanılabilir adres veriliyor; adresin nasıl
        # kurulduğu depolama arka ucunun işi (Bölüm 3).
        photo_url=(storage.public_url(profile.photo_key) if profile.photo_key else None),
        website=profile.website,
        linkedin_url=profile.linkedin_url,
        company=(CompanyResponse.model_validate(profile.company) if profile.company else None),
        sector=(SectorResponse.model_validate(profile.sector) if profile.sector else None),
        offered_tags=tags_for(TagDirection.OFFERED),
        sought_tags=tags_for(TagDirection.SOUGHT),
        completion_percent=status_.completion_percent,
        missing_for_application=list(status_.missing_for_application),
        can_apply=status_.can_apply,
    )


@router.get("", summary="Kendi profilim")
async def read_profile(
    user: CurrentUser, session: SessionDep, storage: StorageDep
) -> ProfileResponse:
    return _to_response(await _load_profile(session, user.id), storage)


@router.patch("", summary="Profili güncelle")
async def update_profile(
    payload: ProfileUpdate,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> ProfileResponse:
    """Sihirbazın her adımı bu ucu çağırır.

    Yalnızca gönderilen alanlar değişir — `exclude_unset` sayesinde bir adımı
    kaydetmek diğer adımların verisini silmez (M2).
    """
    profile = await _load_profile(session, user.id)
    changes = payload.model_dump(exclude_unset=True)

    offered = changes.pop("offered_tag_ids", None)
    sought = changes.pop("sought_tag_ids", None)

    for field, value in changes.items():
        setattr(profile, field, value)

    if offered is not None:
        await _replace_tags(session, profile, TagDirection.OFFERED, offered)
    if sought is not None:
        await _replace_tags(session, profile, TagDirection.SOUGHT, sought)

    await session.commit()
    return _to_response(await _load_profile(session, user.id), storage)


@router.post("/photo", summary="Profil fotoğrafı yükle")
async def upload_photo(
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
    file: Annotated[UploadFile, File(description="JPEG, PNG veya WebP")],
) -> ProfileResponse:
    """Fotoğrafı depolama arayüzü üzerinden kaydeder (Bölüm 3).

    Uç diskin nerede olduğunu bilmiyor; `Storage` sözleşmesini çağırıyor.
    """
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Yalnızca JPEG, PNG veya WebP yükleyebilirsin.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Dosya boş.",
        )
    # Boyut, bildirilen başlığa değil okunan içeriğe göre kontrol ediliyor:
    # Content-Length istemcinin iddiası, gerçek boyut bu.
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Fotoğraf en fazla {MAX_IMAGE_BYTES // (1024 * 1024)} MB olabilir.",
        )

    profile = await _load_profile(session, user.id)
    previous_key = profile.photo_key

    try:
        profile.photo_key = await storage.save(
            content, folder="profile-photos", content_type=content_type
        )
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fotoğraf kaydedilemedi, az sonra tekrar dene.",
        ) from error

    await session.commit()

    # Eski dosya ancak yenisi kaydedildikten ve veritabanı güncellendikten sonra
    # siliniyor. Ters sırada olsaydı, yükleme yarıda kalınca kullanıcı hem eski
    # hem yeni fotoğrafından olurdu.
    if previous_key:
        await _delete_quietly(storage, previous_key)

    return _to_response(await _load_profile(session, user.id), storage)


@router.delete("/photo", summary="Profil fotoğrafını kaldır")
async def delete_photo(
    user: CurrentUser, session: SessionDep, storage: StorageDep
) -> ProfileResponse:
    profile = await _load_profile(session, user.id)
    key = profile.photo_key

    profile.photo_key = None
    await session.commit()

    if key:
        await _delete_quietly(storage, key)

    return _to_response(await _load_profile(session, user.id), storage)


async def _delete_quietly(storage: Storage, key: str) -> None:
    """Artık kullanılmayan dosyayı siler; başarısız olursa isteği düşürmez.

    Kullanıcının işlemi tamamlandı; diskte kalan artık bir dosya yüzünden hata
    göstermek yanlış olurdu.
    """
    try:
        await storage.delete(key)
    except StorageError:
        pass


async def _replace_tags(
    session: SessionDep, profile: Profile, direction: TagDirection, tag_ids: list[int]
) -> None:
    """Bir yöndeki etiketlerin tamamını verilen listeyle değiştirir.

    Etiketlerin gerçekten var olduğu kontrol edilir: olmayan bir kimlik yabancı
    anahtar hatasıyla 500'e dönüşürdü, oysa bu istemcinin hatası.
    """
    unique_ids = sorted(set(tag_ids))

    if unique_ids:
        found = await session.execute(select(Tag.id).where(Tag.id.in_(unique_ids)))
        missing = set(unique_ids) - set(found.scalars())
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Bilinmeyen etiket: {sorted(missing)}",
            )

    profile.tags = [link for link in profile.tags if link.direction != direction] + [
        ProfileTag(profile_id=profile.id, tag_id=tag_id, direction=direction)
        for tag_id in unique_ids
    ]
