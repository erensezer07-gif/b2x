"""Profil tamamlanma ve başvuru yeterliliği (şartname M2).

İki ayrı kavram, karıştırılmamalı:

**Tamamlanma yüzdesi** kullanıcıyı bilgilendirir: *"Eksik profil eşleştirmede
kötü sonuç verir, kullanıcının bunu bilmesi lazım."* Hiçbir şeyi engellemez.

**Başvuru yeterliliği** kapı bekçisidir: *"Etkinliğe başvurabilmek için profil en
az şu alanları içermeli: ad soyad, şirket, sektör, en az üç 'sunuyorum' etiketi,
en az üç 'arıyorum' etiketi. Eksikse başvuru butonu çalışmaz ve neyin eksik
olduğu yazılır."*

Eksik alanlar İngilizce anahtar olarak dönüyor; Türkçe cümleyi arayüz kuruyor.
Motorun gerekçe kırılımında olduğu gibi — sunucu metin üretmez.
"""

from dataclasses import dataclass

from app.models import Profile, TagDirection

# Şartnamenin saydığı asgari etiket sayısı (M2).
MINIMUM_TAGS_PER_DIRECTION = 3

# Tamamlanma yüzdesine giren kalemler. Web sitesi ve LinkedIn bilerek yok:
# şartname onları "isteğe bağlı" diye işaretliyor (Bölüm 6), sayıya katılsalardı
# eksiksiz bir profil bile %100 görünmezdi.
FULL_NAME = "full_name"
TITLE = "title"
COMPANY = "company"
SECTOR = "sector"
CITY = "city"
BIO = "bio"
PHOTO = "photo"
OFFERED_TAGS = "offered_tags"
SOUGHT_TAGS = "sought_tags"

COMPLETION_ITEMS = (
    FULL_NAME,
    TITLE,
    COMPANY,
    SECTOR,
    CITY,
    BIO,
    PHOTO,
    OFFERED_TAGS,
    SOUGHT_TAGS,
)

# Başvuru için zorunlu olanlar — tamamlanma kalemlerinin alt kümesi.
APPLICATION_REQUIREMENTS = (FULL_NAME, COMPANY, SECTOR, OFFERED_TAGS, SOUGHT_TAGS)


@dataclass(frozen=True, slots=True)
class ProfileStatus:
    completion_percent: int
    missing_for_application: tuple[str, ...]

    @property
    def can_apply(self) -> bool:
        return not self.missing_for_application


def count_tags(profile: Profile, direction: TagDirection) -> int:
    return sum(1 for link in profile.tags if link.direction == direction)


def _satisfied_items(profile: Profile) -> set[str]:
    """Doldurulmuş sayılan kalemler.

    Yalnızca boşluktan oluşan bir metin dolu sayılmaz: kullanıcı boşluk tuşuna
    basarak tamamlanma yüzdesini yükseltememeli.
    """
    satisfied = set()

    if (profile.full_name or "").strip():
        satisfied.add(FULL_NAME)
    if (profile.title or "").strip():
        satisfied.add(TITLE)
    if profile.company_id is not None:
        satisfied.add(COMPANY)
    if profile.sector_id is not None:
        satisfied.add(SECTOR)
    if (profile.city or "").strip():
        satisfied.add(CITY)
    if (profile.bio or "").strip():
        satisfied.add(BIO)
    if (profile.photo_key or "").strip():
        satisfied.add(PHOTO)
    if count_tags(profile, TagDirection.OFFERED) >= MINIMUM_TAGS_PER_DIRECTION:
        satisfied.add(OFFERED_TAGS)
    if count_tags(profile, TagDirection.SOUGHT) >= MINIMUM_TAGS_PER_DIRECTION:
        satisfied.add(SOUGHT_TAGS)

    return satisfied


def evaluate_profile(profile: Profile) -> ProfileStatus:
    """Tamamlanma yüzdesini ve başvuru için eksikleri hesaplar."""
    satisfied = _satisfied_items(profile)

    percent = round(100 * len(satisfied) / len(COMPLETION_ITEMS))
    missing = tuple(item for item in APPLICATION_REQUIREMENTS if item not in satisfied)

    return ProfileStatus(completion_percent=percent, missing_for_application=missing)
