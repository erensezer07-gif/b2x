"""Etkinlik başvurusu ve görüşme talebi.

Şartname sözlüğü: **katılımcı**, etkinliğe başvurup kabul edilmiş kullanıcıdır.
Bu yüzden atamalar, talepler ve gerekçeler `users` değil `registrations`
referansı tutar — "bu kişi bu etkinliğe kayıtlı" bilgisi şemadan gelir, ayrıca
kontrol edilmesi gerekmez.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import (
    AttendanceStatus,
    MeetingRequestStatus,
    RegistrationStatus,
    status_check,
    status_column,
)

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.user import User


class Registration(IdMixin, TimestampMixin, Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_registrations_event_user"),
        # Bileşik yabancı anahtarların hedefi. `meeting_requests` bunun sayesinde
        # talep eden ile talep edilenin aynı etkinlikte olduğunu şemada garanti
        # edebiliyor.
        UniqueConstraint("event_id", "id", name="uq_registrations_event_registration"),
        # "Geldi" işareti ile check-in zamanı birlikte hareket eder.
        CheckConstraint(
            "(attendance = 'present') = (checked_in_at IS NOT NULL)",
            name="checkin_consistent",
        ),
        status_check("status", RegistrationStatus, "registration_status"),
        status_check("attendance", AttendanceStatus, "attendance_status"),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    status: Mapped[RegistrationStatus] = mapped_column(
        status_column(RegistrationStatus, "registration_status"),
        nullable=False,
        server_default=text(f"'{RegistrationStatus.PENDING.value}'"),
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    attendance: Mapped[AttendanceStatus] = mapped_column(
        status_column(AttendanceStatus, "attendance_status"),
        nullable=False,
        server_default=text(f"'{AttendanceStatus.ABSENT.value}'"),
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Girişte okutulan kod. Birincil anahtarların aksine tahmin edilemez olmalı;
    # rastgele üretimi Aşama 11'de uygulama katmanında yapılır.
    qr_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    event: Mapped["Event"] = relationship(back_populates="registrations")
    user: Mapped["User"] = relationship(back_populates="registrations")


class MeetingRequest(IdMixin, TimestampMixin, Base):
    """Katılımcının "bu kişiyle görüşmek istiyorum" bildirimi.

    Şartname M9: talep gönderildiği kişiye bildirilmez, hak sınırlıdır ve
    karşılıklı talep tek taraflıdan çok daha güçlüdür. Bunların hepsi iş mantığı;
    şema yalnızca "aynı kişiye aynı etkinlikte ikinci talep gönderilemez"
    kuralını ve tarafların aynı etkinlikte olmasını garanti eder.
    """

    __tablename__ = "meeting_requests"
    __table_args__ = (
        # Tarafların ikisi de bu etkinliğin katılımcısı olmak zorunda. Bileşik
        # yabancı anahtar bunu şemada garanti eder, kontrol koda kalmaz.
        ForeignKeyConstraint(
            ["event_id", "requester_registration_id"],
            ["registrations.event_id", "registrations.id"],
            ondelete="CASCADE",
            name="fk_meeting_requests_requester",
        ),
        ForeignKeyConstraint(
            ["event_id", "target_registration_id"],
            ["registrations.event_id", "registrations.id"],
            ondelete="CASCADE",
            name="fk_meeting_requests_target",
        ),
        # Kayıtlar zaten etkinliğe özel olduğu için ikili benzersizliği
        # "aynı etkinlikte ikinci talep yok" demeye yeter.
        UniqueConstraint(
            "requester_registration_id",
            "target_registration_id",
            name="uq_meeting_requests_pair",
        ),
        CheckConstraint(
            "requester_registration_id <> target_registration_id",
            name="not_self",
        ),
        status_check("status", MeetingRequestStatus, "meeting_request_status"),
    )

    event_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requester_registration_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_registration_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[MeetingRequestStatus] = mapped_column(
        status_column(MeetingRequestStatus, "meeting_request_status"),
        nullable=False,
        server_default=text(f"'{MeetingRequestStatus.ACTIVE.value}'"),
    )
