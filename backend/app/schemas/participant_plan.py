"""Katılımcının gördüğü plan modelleri (şartname M8).

**Hiçbirinde sayı yok.** M8: *"'Uyum: %62' gibi bir ifade kullanılmaz. Sayı
gören insan not almış gibi hisseder."* Skor, masa kalitesi, kırılım — hiçbiri
bu şemalara girmiyor. Organizatörün gördüğü `TableViewResponse` ayrı bir şema;
alan gizlemek yerine ayrı şema, ileride oraya eklenen bir alan sessizce dışarı
çıkmasın diye (Aşama 6'daki `PublicEventResponse` kararının aynısı).
"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.company import CompanyResponse
from app.schemas.taxonomy import SectorResponse, TagResponse


class MatchReasonResponse(BaseModel):
    """*"Karşıdaki kişiyle neden eşleştiğini anlatan bir veya iki kısa cümle."*

    Anahtar İngilizce, Türkçe cümleyi arayüz kuruyor. `values` cümlenin içine
    giren adlar: etiketler, sektör, şehir.
    """

    kind: str
    values: list[str]


class TablemateResponse(BaseModel):
    """Masa arkadaşı kartı (M8: *"fotoğraf, ad, unvan, şirket"*)."""

    registration_id: int
    full_name: str | None
    title: str | None
    company: str | None
    photo_url: str | None
    reasons: list[MatchReasonResponse]


class MySlotResponse(BaseModel):
    """Katılımcının bir turu.

    `table_number` yoksa o turda oturmuyor. M8: *"Bir slotta eşleşmemişse o
    slot 'Bu turda serbestsin' olarak gösterilir. Boş bırakılmaz."* Cümleyi
    arayüz kuruyor; sunucu yalnızca boşluğu bildiriyor.
    """

    slot_number: int
    starts_at: datetime
    ends_at: datetime

    table_id: int | None
    table_number: int | None
    table_label: str | None

    tablemates: list[TablemateResponse]


class MyPlanResponse(BaseModel):
    """Katılımcının gördüğü planın tamamı.

    Plan yayında değilse `slots` **boş** ve `is_published` yanlış — o durumda
    sunucu atamaları hiç okumuyor (Bölüm 7).
    """

    is_published: bool
    plan_version: int | None
    slots: list[MySlotResponse]


class VenueTableResponse(BaseModel):
    """Krokideki bir masa. **Kimin oturduğu yok.**"""

    id: int
    number: int
    label: str | None
    grid_x: int | None
    grid_y: int | None


class VenueAreaResponse(BaseModel):
    id: int
    label: str
    grid_x: int
    grid_y: int
    width: int
    height: int


class VenueResponse(BaseModel):
    """Salon krokisi (M8: *"krokide masanın yeri işaretli"*).

    Otomatik düzende ızgara yok; kroki çizilemez, arayüz yalnızca masa
    numarasını gösterir.
    """

    mode: str
    grid_width: int | None
    grid_height: int | None
    tables: list[VenueTableResponse]
    areas: list[VenueAreaResponse]


class TablemateProfileResponse(BaseModel):
    """Masa arkadaşının tam profili (M8).

    Kendi profilinden farkı: tamamlanma yüzdesi ve başvuru eksikleri yok —
    onlar sahibine ait bilgiler.
    """

    registration_id: int
    full_name: str | None
    title: str | None
    city: str | None
    bio: str | None
    photo_url: str | None
    website: str | None
    linkedin_url: str | None

    company: CompanyResponse | None
    sector: SectorResponse | None
    offered_tags: list[TagResponse]
    sought_tags: list[TagResponse]
