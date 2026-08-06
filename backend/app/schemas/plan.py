"""Plan, eşleştirme ve elle düzeltme modelleri (şartname M6, M7, 5.4)."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models import JobStatus, PlanStatus
from app.schemas.meeting_request import UnmetRequestResponse
from app.services.plan_editing import TableQuality


class MatchingCheckResponse(BaseModel):
    """Çalıştırma öncesi kontrol listesi (M6).

    *"Sorun varsa organizatör uyarılır ama çalıştırma engellenmez."*
    `warnings` İngilizce anahtar taşıyor; Türkçe cümleyi arayüz kuruyor —
    profil eksikleriyle aynı kalıp (Aşama 3).
    """

    accepted_count: int
    table_count: int
    seating_capacity: int
    request_count: int
    incomplete_profile_count: int
    slot_count: int
    requests_open: bool
    warnings: list[str]

    # Motor çalışabilir mi. Uyarılar engellemiyor; bu bayrak yalnızca "en az
    # iki kişi ve bir masa" gibi hesabın hiç anlamlı olmadığı durumu söylüyor.
    can_run: bool


class RunMatchingRequest(BaseModel):
    """Eşleştirmeyi başlatma isteği.

    Tohum verilebiliyor: 5.3 gereği aynı tohum aynı sonucu üretir, organizatör
    bir çalıştırmayı tekrar etmek isteyebilir. Verilmezse ortam dosyasındaki
    varsayılan kullanılıyor.
    """

    seed: int | None = Field(default=None, ge=0)


class PlanSummaryResponse(BaseModel):
    """Bir plan versiyonu ve hesabının durumu."""

    id: int
    version: int
    status: PlanStatus
    job_status: JobStatus
    job_error: str | None
    created_at: datetime
    published_at: datetime | None
    seed: int

    # Motor bitene kadar boş. Plan satırı iş kuyruğa girer girmez oluşuyor.
    total_meetings: int | None
    min_meetings_per_person: int | None
    average_table_score: float | None
    runtime_ms: int | None

    # Hesap bitince dolan sayılar; özet panelin kaynağı (M7).
    assignment_count: int
    participant_count: int

    # *"Hiç eşleşmemiş kişi var mı, varsa kimler"* (M7). Kabul edilmiş ama
    # hiçbir turda masaya oturmamış kişiler.
    unmatched: list[str]

    # *"Karşılanan talep sayısı / toplam talep"* (M7).
    satisfied_requests: int
    total_requests: int

    # *"Organizatör plan ekranında karşılanmayan talepleri görür."* (M9)
    # Karşılanmışlar dönmüyor: yapılacak bir şey kalmamış.
    unmet_requests: list[UnmetRequestResponse]


class SeatedPersonResponse(BaseModel):
    """Bir masada oturan kişi (M7: *"ad, şirket"*)."""

    assignment_id: int
    registration_id: int
    full_name: str | None
    company: str | None
    is_pinned: bool


class TableViewResponse(BaseModel):
    """Slot görünümündeki bir masa (M7).

    Boş masalar da dönüyor: organizatör birini boş sandalyeye taşıyabilmeli.
    """

    table_id: int
    number: int
    label: str | None
    capacity: int
    occupants: list[SeatedPersonResponse]

    # *"Masa kalite göstergesi — sayı değil, üç seviye."* Sayı yine de
    # dönüyor ama organizatöre gösterilmiyor; hata ayıklama ve sıralama için.
    quality: TableQuality
    score: float


class SlotViewResponse(BaseModel):
    slot_number: int
    tables: list[TableViewResponse]


class SwapRequest(BaseModel):
    """Takas ya da boş yere taşıma (M7).

    İkinci kişi verilirse yerleri değişiyor, masa verilirse kişi oraya
    taşınıyor. İkisi birden ya da hiçbiri geçersiz.
    """

    slot_number: int = Field(ge=1)
    assignment_id: int
    target_assignment_id: int | None = None
    target_table_id: int | None = None

    @model_validator(mode="after")
    def check_exactly_one_target(self) -> Self:
        if (self.target_assignment_id is None) == (self.target_table_id is None):
            raise ValueError("Hedef olarak ya bir kişi ya bir masa verilmeli.")
        return self


class SwapWarningResponse(BaseModel):
    """Takas sonrası uyarı.

    Anahtar İngilizce, Türkçe cümleyi arayüz kuruyor. `people` ve
    `table_number` cümlenin içine giren parçalar.
    """

    key: str
    table_number: int | None
    people: list[str]
    slot_number: int | None


class SwapResponse(BaseModel):
    """Takas sonucu: yeni slot görünümü ve uyarılar.

    Uyarılar takası **engellemiyor** (M7). Görünüm birlikte dönüyor ki
    istemci ikinci bir istek atmasın.
    """

    slot: SlotViewResponse
    warnings: list[SwapWarningResponse]


class PinRequest(BaseModel):
    is_pinned: bool
