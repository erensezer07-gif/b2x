"""Profil istek ve yanıt modelleri (şartname M2)."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.company import CompanyResponse
from app.schemas.taxonomy import SectorResponse, TagResponse


class ProfileUpdate(BaseModel):
    """Kısmi güncelleme.

    Sihirbaz adım adım kaydediyor ve kullanıcı yarıda bırakabiliyor (M2), bu
    yüzden her istek profilin tamamını taşımak zorunda değil.

    Gönderilmeyen alan **değişmez**; açıkça `null` gönderilen alan **temizlenir**.
    İkisi arasındaki farkı Pydantic'in "hangi alanlar verildi" bilgisi ayırıyor —
    varsayılan `None` ile gelen `null` aynı şey olsaydı, tek adımı kaydetmek
    diğer adımların verisini silerdi.
    """

    full_name: str | None = Field(default=None, max_length=150)
    title: str | None = Field(default=None, max_length=150)
    company_id: int | None = None
    sector_id: int | None = None
    city: str | None = Field(default=None, max_length=100)
    bio: str | None = None
    website: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)

    # Verilirse o yöndeki etiketlerin tamamının yerini alır.
    offered_tag_ids: list[int] | None = None
    sought_tag_ids: list[int] | None = None


class ProfileResponse(BaseModel):
    """Kullanıcının kendi profili.

    `completion_percent` ve `missing_for_application` hesaplanmış değerler;
    arayüzün aynı kuralları tekrar yazmasına gerek kalmasın diye burada.
    """

    model_config = ConfigDict(from_attributes=True)

    full_name: str | None
    title: str | None
    city: str | None
    bio: str | None

    # Fotoğrafın tam adresi. Veritabanında anahtar saklanıyor; adres depolama
    # arka ucuna göre üretiliyor, bu yüzden kaydedilmiyor (Bölüm 3).
    photo_url: str | None
    website: str | None
    linkedin_url: str | None

    company: CompanyResponse | None
    sector: SectorResponse | None
    offered_tags: list[TagResponse]
    sought_tags: list[TagResponse]

    completion_percent: int

    # Başvuruyu engelleyen eksik alanların İngilizce anahtarları
    # ("full_name", "company", ...). Türkçe cümleyi arayüz kurar.
    missing_for_application: list[str]
    can_apply: bool
