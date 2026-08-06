"""Plan, atamalar ve eşleşme gerekçeleri.

Şartname Bölüm 5.2: **plan yaşayan bir nesnedir.** Tek seferlik bir çıktı değil,
versiyonlanan bir kayıt. Organizatör düzeltir, check-in sonrası yenilenir. Eski
versiyonlar silinmez; "kimin yeri değişti" sorusunun cevabı iki versiyonu
karşılaştırarak bulunur.

Bu yüzden Bölüm 11 şunu şart koşuyor: "Plan versiyonlama yapısı baştan doğru
kurulur, sonradan eklenmez."

**Görünürlüğün tek kaynağı plan durumudur.** Katılımcının bir atamayı görüp
göremeyeceği yalnızca ilgili versiyonun `published` olup olmadığına bakılarak
belirlenir; etkinlik durumu bu soruya karışmaz (Bölüm 5.2 ve Bölüm 13).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import JobStatus, PlanStatus, status_check, status_column

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.layout import Table
    from app.models.registration import Registration


class Plan(IdMixin, TimestampMixin, Base):
    __tablename__ = "plans"
    __table_args__ = (
        UniqueConstraint("event_id", "version", name="uq_plans_event_version"),
        # Şartnamenin en kritik veri kuralı: bir etkinlikte aynı anda en fazla
        # bir plan yayında olabilir. Koşullu benzersiz indeks bunu veritabanı
        # seviyesinde imkânsız kılar — uygulama hatası veriyi bozamaz.
        Index(
            "uq_plans_single_published",
            "event_id",
            unique=True,
            postgresql_where=text(f"status = '{PlanStatus.PUBLISHED.value}'"),
        ),
        CheckConstraint("version > 0", name="version_positive"),
        # Taslak plan yayınlanmış olamaz; yayındaki planın yayın zamanı olmak
        # zorunda. Arşiv durumu serbest bırakıldı: arşive giden plan yayın
        # zamanını korur.
        CheckConstraint(
            "status <> 'draft' OR published_at IS NULL",
            name="draft_has_no_publish_time",
        ),
        CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="published_has_publish_time",
        ),
        # Hesap bitmeden plan yayınlanamaz: yarım bir plan katılımcıya
        # gösterilemez (5.4, Bölüm 7).
        CheckConstraint(
            "status <> 'published' OR job_status = 'done'",
            name="published_needs_finished_job",
        ),
        status_check("status", PlanStatus, "plan_status"),
        status_check("job_status", JobStatus, "job_status"),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PlanStatus] = mapped_column(
        status_column(PlanStatus, "plan_status"),
        nullable=False,
        server_default=text(f"'{PlanStatus.DRAFT.value}'"),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Motor deterministiktir (şartname 5.3): aynı girdi ve aynı tohum aynı sonucu
    # verir. Tohum planla birlikte saklanmazsa sonuç tekrar üretilemez.
    seed: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Hesabın durumu (şartname 5.4) ---
    #
    # *"İşin durumu takip edilebilir olmalı: kuyrukta / çalışıyor / bitti /
    # hata."* Planın kendi durumundan ayrı: plan satırı iş kuyruğa girer girmez
    # oluşuyor, motor sonra çalışıyor. O aralıkta plan var ama içi boş.
    job_status: Mapped[JobStatus] = mapped_column(
        status_column(JobStatus, "job_status"),
        nullable=False,
        server_default=text(f"'{JobStatus.QUEUED.value}'"),
    )

    # Hata mesajı — yalnızca `failed` durumunda dolu. Organizatör "neden
    # çalışmadı" sorusunun cevabını ekranda görmeli.
    job_error: Mapped[str | None] = mapped_column(Text)

    # Kuyruk kimliği. İşin akıbetini kuyruk tarafından da izleyebilmek için.
    job_id: Mapped[str | None] = mapped_column(String(64))

    # Hesaplama özeti. Motor çalışmadan önce plan satırı oluşabildiği için
    # (Aşama 7'de iş kuyruğa girer, sonra biter) hepsi boş geçilebilir.
    total_meetings: Mapped[int | None] = mapped_column(Integer)
    # Özet panelindeki en önemli sayı (şartname M7).
    min_meetings_per_person: Mapped[int | None] = mapped_column(Integer)
    average_table_score: Mapped[float | None] = mapped_column(Double)
    runtime_ms: Mapped[int | None] = mapped_column(Integer)

    # Hangi versiyondan türediği. Silinirse zincir kopar ama plan durur.
    previous_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL")
    )

    # Minimum değişim modunda mı üretildi (şartname 9.8, M10).
    #
    # `previous_plan_id` bunu söylemiyor: her plan bir öncekinden türüyor ama
    # yalnızca check-in sonrası çalıştırma önceki planı **başlangıç noktası**
    # olarak alıyor. İş kuyruğa girerken karar veriliyor, işçi bu alanı
    # okuyor — istek gövdesi o noktada elde değil.
    minimal_change: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    event: Mapped["Event"] = relationship(back_populates="plans")
    previous_plan: Mapped["Plan | None"] = relationship(remote_side="Plan.id")
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    match_reasons: Mapped[list["MatchReason"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Assignment(IdMixin, TimestampMixin, Base):
    """Planın bir satırı: "şu katılımcı, şu slotta, şu masada".

    Bir kişi bir slotta hiçbir masaya atanmamış olabilir — o slot için satır
    oluşmaz (şartname Bölüm 6). Katılımcı ekranında bu durum "Bu turda serbestsin"
    olarak gösterilir.
    """

    __tablename__ = "assignments"
    __table_args__ = (
        # Kesin kural "Tek yer" (şartname 9.5): bir kişi bir slotta en fazla bir
        # masada olabilir.
        UniqueConstraint(
            "plan_id",
            "slot_number",
            "registration_id",
            name="uq_assignments_plan_slot_registration",
        ),
        # Bir slottaki bir masanın kimlerden oluştuğu en sık yapılan sorgu.
        Index("ix_assignments_plan_slot_table", "plan_id", "slot_number", "table_id"),
        CheckConstraint("slot_number > 0", name="slot_number_positive"),
    )

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="RESTRICT"), nullable=False
    )
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False
    )

    # Çapa kişi veya organizatörün elle sabitlediği atama. Motor tekrar
    # çalıştırılsa bile bu satırı değiştiremez (şartname M7, 9.5).
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    plan: Mapped["Plan"] = relationship(back_populates="assignments")
    table: Mapped["Table"] = relationship(back_populates="assignments")
    registration: Mapped["Registration"] = relationship()


class MatchReason(IdMixin, TimestampMixin, Base):
    """İki kişinin neden aynı masaya konduğunun kaydı.

    Katılımcıya "neden bu kişiyle eşleştim" cevabını verir. Motor skoru
    hesaplarken bu bilgiye zaten sahiptir, burada yalnızca saklanır.

    **Katılımcıya sayı gösterilmez** (şartname M8 ve Bölüm 13). `total_score`
    organizatör tarafı ve hata ayıklama içindir; kullanıcının gördüğü cümle
    `breakdown` içindeki kalıplardan üretilir.
    """

    __tablename__ = "match_reasons"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "slot_number",
            "registration_a_id",
            "registration_b_id",
            name="uq_match_reasons_pair",
        ),
        # İkili sırasızdır. Kanonik sırada saklanmasa aynı çift hem (A,B) hem
        # (B,A) olarak iki kez yazılabilir ve benzersizlik anlamını yitirirdi.
        CheckConstraint(
            "registration_a_id < registration_b_id",
            name="canonical_order",
        ),
        CheckConstraint("slot_number > 0", name="slot_number_positive"),
    )

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    registration_a_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False
    )
    registration_b_id: Mapped[int] = mapped_column(
        ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False
    )

    total_score: Mapped[float] = mapped_column(Double, nullable=False)

    # Hangi kriterden kaç puan geldiği ve insan diliyle açıklaması. Kriter listesi
    # motor geliştikçe değişeceği için sabit kolonlar yerine JSON tutuluyor.
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)

    plan: Mapped["Plan"] = relationship(back_populates="match_reasons")
