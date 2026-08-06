"""Etkinlik.

Şartname Bölüm 6: **etkinlik durumu yalnızca başvuru akışını yönetir.** Planın
hazır olup olmadığı, yayınlanıp yayınlanmadığı buraya yazılmaz — o bilgi `plans`
tablosunda durur. Bölüm 13 bunu sık yapılan hatalar arasında sayıyor:
"Plan görünürlüğünü etkinlik durumundan okumak."

Slot saatleri saklanmaz, hesaplanır (M3): başlangıç saati, slot süresi, mola
süresi ve slot sayısı yeterli. Ayrı bir `slots` tablosu yoktur.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import EventStatus, status_check, status_column

if TYPE_CHECKING:
    from app.models.layout import Layout
    from app.models.plan import Plan
    from app.models.registration import Registration
    from app.models.user import User


class Event(IdMixin, TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("slot_duration_minutes > 0", name="slot_duration_positive"),
        CheckConstraint("break_duration_minutes >= 0", name="break_non_negative"),
        CheckConstraint("slot_count > 0", name="slot_count_positive"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("request_quota >= 0", name="request_quota_non_negative"),
        status_check("status", EventStatus, "event_status"),
    )

    organizer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_key: Mapped[str | None] = mapped_column(String(500))

    # Tarih ve başlangıç saati tek alanda: program hesabı ikisini birlikte
    # kullanıyor, ayrı tutmak saat dilimi kaymasına açık kapı bırakırdı.
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    venue_name: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)

    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    break_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_count: Mapped[int] = mapped_column(Integer, nullable=False)

    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[EventStatus] = mapped_column(
        status_column(EventStatus, "event_status"),
        nullable=False,
        server_default=text(f"'{EventStatus.DRAFT.value}'"),
    )

    # Talep sistemi kapanış zamanı (M9). Kapanmazsa plan hiç kilitlenemez.
    requests_close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Aşağıdaki iki alan şartname Bölüm 6'nın events listesinde sayılmıyor ama
    # M4 ve M9'un tarif ettiği davranış bunlar olmadan çalışmaz. Varsayılan
    # verilmez: organizatör sihirbazda ikisini de açıkça belirler, `request_quota`
    # başlangıç değeri ortam dosyasındaki varsayılandan gelir.
    auto_approve_registrations: Mapped[bool] = mapped_column(Boolean, nullable=False)
    request_quota: Mapped[int] = mapped_column(Integer, nullable=False)

    organizer: Mapped["User"] = relationship(back_populates="organized_events")
    layout: Mapped["Layout | None"] = relationship(
        back_populates="event", cascade="all, delete-orphan", uselist=False
    )
    registrations: Mapped[list["Registration"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    plans: Mapped[list["Plan"]] = relationship(back_populates="event", cascade="all, delete-orphan")
