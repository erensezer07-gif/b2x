"""Etkinlik istek ve yanıt modelleri (şartname M4)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import EventStatus


class EventCreateRequest(BaseModel):
    """Taslak oluşturma.

    Sihirbazın ilk adımı bu ucu çağırıyor; geri kalan alanlar sonraki adımlarda
    `PATCH` ile doldurulacak (M4: *"taslak olarak kaydedilebilir, sonra devam
    edilebilir"*).

    Varsayılanlar makul bir başlangıç veriyor ki organizatör program adımına
    geçtiğinde boş bir ekranla karşılaşmasın; hepsi değiştirilebilir.
    """

    name: str = Field(min_length=1, max_length=200)
    starts_at: datetime

    slot_duration_minutes: int = Field(default=30, ge=1, le=480)
    break_duration_minutes: int = Field(default=10, ge=0, le=240)
    slot_count: int = Field(default=6, ge=1, le=50)
    capacity: int = Field(default=100, ge=1, le=10_000)


class EventUpdateRequest(BaseModel):
    """Kısmi güncelleme — sihirbazın her adımı.

    Gönderilmeyen alan değişmez; açıkça `null` gönderilen alan temizlenir.
    Profil sihirbazıyla aynı kalıp (Aşama 3).
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    starts_at: datetime | None = None
    venue_name: str | None = Field(default=None, max_length=200)
    address: str | None = None

    slot_duration_minutes: int | None = Field(default=None, ge=1, le=480)
    break_duration_minutes: int | None = Field(default=None, ge=0, le=240)
    slot_count: int | None = Field(default=None, ge=1, le=50)

    capacity: int | None = Field(default=None, ge=1, le=10_000)
    registration_deadline: datetime | None = None
    auto_approve_registrations: bool | None = None
    request_quota: int | None = Field(default=None, ge=0, le=50)
    requests_close_at: datetime | None = None


class SlotTimingResponse(BaseModel):
    """Bir turun saatleri (M3).

    Program saklanmıyor, her istekte hesaplanıyor — dört alandan türetilebilen
    bir şeyi kaydetmek iki kaynağın ayrışması demekti.
    """

    number: int
    starts_at: datetime
    ends_at: datetime


class CapacitySummary(BaseModel):
    """Kontenjan ile salon kapasitesinin karşılaştırması (M4).

    *"Kontenjan kapasiteden büyükse organizatör uyarılır. Bu bir engel değil
    uyarıdır, çünkü gelmeyecekler hesaba katılabilir."*
    """

    capacity: int
    seating_capacity: int
    table_count: int
    exceeds_seating: bool


class EventSummaryResponse(BaseModel):
    """Liste görünümü için kısa özet."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    starts_at: datetime
    venue_name: str | None
    status: EventStatus
    slot_count: int
    capacity: int


class EventResponse(BaseModel):
    """Etkinliğin tamamı: alanlar, hesaplanmış program ve kapasite özeti."""

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

    capacity: int
    registration_deadline: datetime | None
    auto_approve_registrations: bool
    request_quota: int
    requests_close_at: datetime | None

    status: EventStatus

    schedule: list[SlotTimingResponse]
    ends_at: datetime
    total_minutes: int
    capacity_summary: CapacitySummary

    # Salon düzeni kurulmadan kayıtlar açılamaz (M4, Bölüm 10). Arayüz düğmeyi
    # buna bakarak kapatıyor; asıl kontrol sunucuda.
    has_layout: bool
    can_open_registration: bool
