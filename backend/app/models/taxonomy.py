"""Sektör listesi ve etiket havuzu.

Şartname Bölüm 6: kullanıcı serbest metin yazamaz, kategorileri gezerek seçer.
Bu yüzden hem sektörler hem etiketler tablodan gelir.

**Etiket havuzu tektir.** "Ne sunuyorum" ve "ne arıyorum" aynı `tags` tablosundan
seçilir — sinerji hesabının temeli bu. A'nın sunduğu etiketle B'nin aradığı etiket
aynı satıra denk gelmezse karşılaştırma yapılamaz.

Havuzun **içeriği** (kaç kategori, hangi etiketler, sektör listesi) şartname
Bölüm 12'de hâlâ açık karar. Bu yüzden tablolar boş kurulur, veri sonra girilir.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.profile import Profile, ProfileTag


class Sector(IdMixin, TimestampMixin, Base):
    __tablename__ = "sectors"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Listede gösterim sırası. Alfabetik olmayan bir sıra istenirse buradan.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    profiles: Mapped[list["Profile"]] = relationship(back_populates="sector")


class TagCategory(IdMixin, TimestampMixin, Base):
    """Etiket kategorisi: yazılım hizmetleri, finansman, üretim, lojistik gibi."""

    __tablename__ = "tag_categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    tags: Mapped[list["Tag"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class Tag(IdMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_tags_category_name"),)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("tag_categories.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    category: Mapped["TagCategory"] = relationship(back_populates="tags")
    profile_links: Mapped[list["ProfileTag"]] = relationship(back_populates="tag")
