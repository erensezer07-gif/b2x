"""Etkinlik keşfi ve başvuru modelleri (şartname M3).

Katılımcının gördüğü etkinlik, organizatörün gördüğünden **daha azdır**. Ayrı
şemalar bu yüzden var: `EventResponse` içindeki `auto_approve_registrations`,
`request_quota` ve `capacity_summary` organizatöre ait bilgiler, katılımcıya
sızmamalı (Bölüm 7).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import RegistrationStatus
from app.schemas.company import CompanyResponse
from app.schemas.event import SlotTimingResponse
from app.schemas.taxonomy import SectorResponse


class MyRegistrationResponse(BaseModel):
    """Oturumdaki kullanıcının bu etkinlikteki başvurusu.

    *"Başvuru durumları kullanıcıya net gösterilir: başvurmadı / beklemede /
    kabul edildi / reddedildi."* Başvurmamışsa alan `null` geliyor.
    """

    id: int
    status: RegistrationStatus
    applied_at: datetime


class DiscoverEventResponse(BaseModel):
    """Keşif kartı (M3).

    *"Her kart: ad, tarih, yer, kalan kontenjan, başvuru durumu."*
    """

    id: int
    name: str
    cover_url: str | None
    starts_at: datetime
    venue_name: str | None
    slot_count: int

    capacity: int
    remaining_capacity: int
    registration_deadline: datetime | None

    # Başvuru şu anda mümkün mü — kontenjan, son tarih ve etkinlik durumu
    # birlikte değerlendirilerek. Arayüz düğmeyi buna bakarak kapatıyor;
    # asıl kapı uçta.
    is_open: bool

    my_registration: MyRegistrationResponse | None


class PublicEventResponse(BaseModel):
    """Katılımcının gördüğü etkinlik detayı (M3).

    *"Açıklama, program (slot saatleri hesaplanmış halde), yer bilgisi, kaç
    kişi katılıyor, başvur butonu."*
    """

    id: int
    name: str
    description: str | None
    cover_url: str | None
    starts_at: datetime
    venue_name: str | None
    address: str | None

    slot_duration_minutes: int
    break_duration_minutes: int
    slot_count: int
    schedule: list[SlotTimingResponse]
    ends_at: datetime
    total_minutes: int

    capacity: int
    remaining_capacity: int
    accepted_count: int
    registration_deadline: datetime | None
    is_open: bool

    my_registration: MyRegistrationResponse | None


class ApplicantResponse(BaseModel):
    """Başvuran kişinin özeti — organizatörün onay ekranı için.

    Organizatör kendi etkinliğinin her şeyini görür (Bölüm 7); kimi kabul
    ettiğini görmeden karar veremez.
    """

    model_config = ConfigDict(from_attributes=True)

    full_name: str | None
    title: str | None
    photo_url: str | None
    company: CompanyResponse | None
    sector: SectorResponse | None


class RegistrationResponse(BaseModel):
    """Organizatörün başvuru listesindeki bir satır."""

    id: int
    status: RegistrationStatus
    applied_at: datetime
    applicant: ApplicantResponse


class RegistrationSummaryResponse(BaseModel):
    """Başvuru listesi ve sayılar.

    Sayılar listeyle birlikte geliyor: organizatör süzgeci değiştirdiğinde
    "kaç bekleyen kaldı" bilgisi kaybolmasın.
    """

    registrations: list[RegistrationResponse]
    pending_count: int
    accepted_count: int
    rejected_count: int
    capacity: int
    remaining_capacity: int
