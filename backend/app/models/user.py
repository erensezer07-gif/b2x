"""Kullanıcı hesabı.

Şartname Bölüm 7: ayrı bir rol tablosu yoktur. Rol kullanıcıya değil etkinliğe
göre belirlenir — kendi oluşturduğu etkinlikte organizatör, başvurduğu etkinlikte
katılımcıdır. Bu yüzden burada yetki alanı bulunmaz.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.profile import Profile
    from app.models.registration import Registration


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # E-posta her zaman küçük harfle saklanır, böylece benzersizlik kuralı
        # "Ali@ornek.com" ile "ali@ornek.com" arasında da işler. Uygulama katmanı
        # küçültmeyi unutursa kayıt buradan geri döner.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # MVP'de e-posta gönderimi yok, dolayısıyla doğrulama da yok (şartname M1).
    # Alan ileride e-posta altyapısı eklendiğinde kullanılmak üzere duruyor ve
    # MVP akışında hiçbir yeri engellemiyor.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    organized_events: Mapped[list["Event"]] = relationship(back_populates="organizer")
    registrations: Mapped[list["Registration"]] = relationship(back_populates="user")
