"""Eşleşme gerekçesi üretimi (şartname M8, 9.3).

Katılımcı masasındaki her kişi için *"neden bu kişiyle oturuyorum"* sorusunun
cevabını görüyor. M8: *"Karşıdaki kişiyle neden eşleştiğini anlatan bir veya
iki kısa cümle."*

## Sayı gösterilmiyor

M8 bu konuda kesin: *"'Uyum: %62' gibi bir ifade kullanılmaz. Sayı gören insan
not almış gibi hisseder ve 'neden 62?' tartışması çıkar."* Bu modül skoru
yalnızca **sıralamak** için kullanıyor; ürettiği yapıda hiçbir sayı yok ve
katılımcı yanıtına da girmiyor.

## Cümle burada kurulmuyor

Sunucu yapılandırılmış bir gerekçe döndürüyor (`kind` + ilgili adlar), Türkçe
cümleyi arayüz kuruyor. Aşama 6-7-8'deki kalıbın aynısı: bütün Türkçe metin
tek katmanda toplu duruyor.

## Etiket adları neden burada hesaplanıyor

`match_reasons.breakdown` yalnızca *hangi bileşenden kaç puan geldiğini*
saklıyor (9.3). Hangi etiketin eşleştiğini ve **hangi yönde** eşleştiğini
söylemiyor — arz-talep tek bir sayıya indirgenmiş durumda. Cümlenin ihtiyacı
olan ayrıntı ("kendisi X sunuyor, siz X arıyorsunuz") ancak iki profilin
kesiştirilmesiyle çıkıyor. Okuma anında hesaplanıyor: saklamak, profil
değiştiğinde eskiyen bir kopya bırakırdı.
"""

from dataclasses import dataclass, field

from app.models import Profile, TagDirection
from engine.scoring import CATEGORY, CITY, SECTOR, SUPPLY_DEMAND

# Gerekçe türleri. Türkçe cümleyi arayüz kuruyor.
THEY_OFFER = "they_offer"
YOU_OFFER = "you_offer"
SHARED_CATEGORY = "shared_category"
SAME_SECTOR = "same_sector"
SAME_CITY = "same_city"
MUTUAL_REQUEST = "mutual_request"

# M8: *"bir veya iki kısa cümle."*
MAX_REASONS = 2


@dataclass(frozen=True, slots=True)
class MatchReasonItem:
    """Tek bir gerekçe kalemi.

    `values` cümlenin içine giren adlar: etiketler, sektör, şehir. Arayüz
    bunları kendi cümlesine yerleştiriyor.
    """

    kind: str
    values: tuple[str, ...] = field(default=())


def _tag_names(profile: Profile | None, direction: TagDirection) -> dict[int, str]:
    if profile is None:
        return {}
    return {
        link.tag_id: link.tag.name
        for link in profile.tags
        if link.direction is direction and link.tag
    }


def _categories(profile: Profile | None, direction: TagDirection) -> dict[int, str]:
    if profile is None:
        return {}
    return {
        link.tag.category_id: link.tag.category.name
        for link in profile.tags
        if link.direction is direction and link.tag and link.tag.category
    }


def build_reasons(
    viewer: Profile | None,
    other: Profile | None,
    breakdown: dict[str, float],
    *,
    mutual_request: bool = False,
) -> list[MatchReasonItem]:
    """En güçlü iki gerekçeyi üretir.

    `breakdown` motorun kırılımı (9.3). Sıralama ondan geliyor; **ceza kalemi
    hiç değerlendirmeye girmiyor** — negatif bir katkı "neden eşleştiniz"
    sorusunun cevabı olamaz.

    Bir bileşen puan almış ama karşılığı profillerde bulunamıyorsa atlanıyor:
    plan üretildikten sonra profil değişmiş olabilir ve boş bir cümle
    göstermektense o gerekçeyi hiç göstermemek doğru.
    """
    candidates: list[tuple[float, MatchReasonItem]] = []

    # Karşılıklı talep her zaman en üstte: M9'a göre bu "neredeyse kesin
    # eşleşme" ve katılımcının kendi verdiği karar. Skoru ne olursa olsun ilk
    # sırada anlatılmalı.
    if mutual_request:
        candidates.append((float("inf"), MatchReasonItem(MUTUAL_REQUEST)))

    supply_demand = breakdown.get(SUPPLY_DEMAND, 0.0)
    if supply_demand > 0:
        # İki yön ayrı cümle: "kendisi sunuyor" ile "siz sunuyorsunuz" aynı
        # şey değil ve ikisi birden geçerli olabilir.
        theirs = set(_tag_names(other, TagDirection.OFFERED)) & set(
            _tag_names(viewer, TagDirection.SOUGHT)
        )
        yours = set(_tag_names(viewer, TagDirection.OFFERED)) & set(
            _tag_names(other, TagDirection.SOUGHT)
        )
        offered_by_other = _tag_names(other, TagDirection.OFFERED)
        offered_by_viewer = _tag_names(viewer, TagDirection.OFFERED)

        if theirs:
            candidates.append(
                (
                    supply_demand,
                    MatchReasonItem(
                        THEY_OFFER,
                        tuple(sorted(offered_by_other[tag_id] for tag_id in theirs)),
                    ),
                )
            )
        if yours:
            candidates.append(
                (
                    # İkinci yön birinciden yarım adım geride: katılımcı önce
                    # kendi aradığını duymalı.
                    supply_demand - 1e-9,
                    MatchReasonItem(
                        YOU_OFFER,
                        tuple(sorted(offered_by_viewer[tag_id] for tag_id in yours)),
                    ),
                )
            )

    category = breakdown.get(CATEGORY, 0.0)
    if category > 0:
        shared = set(_categories(other, TagDirection.OFFERED)) & set(
            _categories(viewer, TagDirection.SOUGHT)
        )
        shared |= set(_categories(viewer, TagDirection.OFFERED)) & set(
            _categories(other, TagDirection.SOUGHT)
        )
        names = _categories(other, TagDirection.OFFERED) | _categories(viewer, TagDirection.OFFERED)
        if shared:
            candidates.append(
                (
                    category,
                    MatchReasonItem(
                        SHARED_CATEGORY,
                        tuple(sorted(names[category_id] for category_id in shared)),
                    ),
                )
            )

    if breakdown.get(SECTOR, 0.0) > 0 and other is not None and other.sector is not None:
        candidates.append((breakdown[SECTOR], MatchReasonItem(SAME_SECTOR, (other.sector.name,))))

    if breakdown.get(CITY, 0.0) > 0 and other is not None and other.city:
        candidates.append((breakdown[CITY], MatchReasonItem(SAME_CITY, (other.city,))))

    # Tek taraflı talep (`REQUEST` puanı var ama karşılıklı değil) hiç
    # gösterilmiyor. M9: *"Talep gönderildiği kişiye bildirilmez... sosyal
    # baskı yaratmamak."* Kendi talebini geri okumak da bir şey katmıyor.

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item for _score, item in candidates[:MAX_REASONS]]
