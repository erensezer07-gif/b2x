"""Plan ve eşleştirme çalıştırma modelleri (şartname M6, 5.4)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import JobStatus, PlanStatus


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
