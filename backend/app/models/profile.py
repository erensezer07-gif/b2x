"""Katılımcı profili ve seçtiği etiketler.

Şartname M2: profil sihirbazı adım adım ilerler, her adım kaydedilir, kullanıcı
yarıda bırakıp sonra devam edebilir. Bu yüzden `user_id` dışındaki alanların hepsi
boş geçilebilir — yarım profil geçerli bir kayıttır.

"Etkinliğe başvurmak için profil yeterli mi" kontrolü (ad soyad, şirket, sektör,
en az üçer etiket) iş mantığında yapılır, NOT NULL ile değil. Şema onu zorlasaydı
sihirbaz hiç kaydedemezdi.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import TagDirection, status_check, status_column

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.taxonomy import Sector, Tag
    from app.models.user import User


class Profile(IdMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    # Kullanıcı başına tek profil.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    full_name: Mapped[str | None] = mapped_column(String(150))
    title: Mapped[str | None] = mapped_column(String(150))

    # Şirket serbest metin değil, kimlik üzerinden bağlanır — aynı şirketten iki
    # kişinin aynı masaya oturmaması kuralı buna dayanır (şartname 9.5).
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="RESTRICT"))
    sector_id: Mapped[int | None] = mapped_column(ForeignKey("sectors.id", ondelete="RESTRICT"))

    city: Mapped[str | None] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text)

    # Dosyanın kendisi depolama arayüzünün arkasında durur; burada yalnızca
    # anahtarı saklanır, tam adres değil (şartname Bölüm 3, dosya depolama notu).
    photo_key: Mapped[str | None] = mapped_column(String(500))

    website: Mapped[str | None] = mapped_column(String(500))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))

    user: Mapped["User"] = relationship(back_populates="profile")
    company: Mapped["Company | None"] = relationship(back_populates="profiles")
    sector: Mapped["Sector | None"] = relationship(back_populates="profiles")
    tags: Mapped[list["ProfileTag"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ProfileTag(Base):
    """Profilin bir etiketi — sunduğu ya da aradığı.

    Tek tablo, çünkü şartname Bölüm 6 "aynı etiket havuzu" diyor. İki ayrı tablo
    olsaydı iki havuzun ayrışması mümkün olurdu ve sinerji hesabı sessizce
    bozulurdu.

    Aynı etiket hem sunulan hem aranan olabilir; `direction` birincil anahtarın
    parçası olduğu için ikisi ayrı satırdır.
    """

    __tablename__ = "profile_tags"
    __table_args__ = (status_check("direction", TagDirection, "tag_direction"),)

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="RESTRICT"), primary_key=True
    )
    direction: Mapped[TagDirection] = mapped_column(
        status_column(TagDirection, "tag_direction"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    profile: Mapped["Profile"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship(back_populates="profile_links")
