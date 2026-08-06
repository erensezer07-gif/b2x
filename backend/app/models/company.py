"""Şirket.

Şartname Bölüm 6'daki kritik not: aynı şirketten iki kişi aynı masaya
oturamaz. Şirket adı serbest metin olsaydı "ABC Yazılım", "ABC Yazılım A.Ş." ve
"abc yazilim" ayrı şirket sanılır, kural sessizce işlemez hale gelirdi.

Bu yüzden karşılaştırma serbest metinle değil şirket kimliğiyle yapılır ve
tekilleştirme `normalized_name` üzerinden şemada zorlanır.

Normalleştirme kuralları (Türkçe büyük-küçük harf katlaması, tüzel kişilik
eklerinin atılması) Aşama 3'te uygulama katmanında yazılacak; burada yalnızca
sonucun benzersiz olduğu garanti edilir.
"""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import Profile


class Company(IdMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    # Kullanıcının yazdığı ve ekranda gösterilen hâli.
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Karşılaştırma için indirgenmiş hâli. Aynı şirketin iki kez oluşmasını
    # engelleyen alan budur.
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)

    profiles: Mapped[list["Profile"]] = relationship(back_populates="company")
