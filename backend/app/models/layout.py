"""Salon düzeni, masalar ve alan blokları.

Şartname M5: iki mod var. Otomatik modda görsel kroki yoktur, katılımcıya yalnızca
masa numarası gösterilir. Manuel modda organizatör salonu ızgara üzerinde kurar.

Masa numarası kritik: katılımcı yerini numarayla buluyor. Bu yüzden aynı düzende
iki masanın aynı numarayı alması şemada engellenir.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin
from app.models.enums import LayoutMode, TableKind, status_check, status_column

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.plan import Assignment


class Layout(IdMixin, TimestampMixin, Base):
    """Etkinliğe birebir bağlı tek düzen kaydı."""

    __tablename__ = "layouts"
    __table_args__ = (
        # Izgara boyutu yalnızca manuel modda anlamlı.
        CheckConstraint(
            "(mode = 'manual' AND grid_width IS NOT NULL AND grid_height IS NOT NULL)"
            " OR (mode = 'auto' AND grid_width IS NULL AND grid_height IS NULL)",
            name="grid_matches_mode",
        ),
        CheckConstraint("grid_width IS NULL OR grid_width > 0", name="grid_width_positive"),
        CheckConstraint("grid_height IS NULL OR grid_height > 0", name="grid_height_positive"),
        status_check("mode", LayoutMode, "layout_mode"),
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    mode: Mapped[LayoutMode] = mapped_column(
        status_column(LayoutMode, "layout_mode"), nullable=False
    )
    grid_width: Mapped[int | None] = mapped_column(Integer)
    grid_height: Mapped[int | None] = mapped_column(Integer)

    event: Mapped["Event"] = relationship(back_populates="layout")
    tables: Mapped[list["Table"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan"
    )
    areas: Mapped[list["LayoutArea"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan"
    )


class Table(IdMixin, TimestampMixin, Base):
    """Masa.

    Sınıf adı şartname sözlüğündeki terimle aynı tutuldu ("Masa (Table)").
    Bu modülde `sqlalchemy.Table` bilerek import edilmiyor — ad çakışması olur.

    Kapasite kuralları (şartname 9.5):
    * Oturmalı masada sandalye sayısı kesin üst sınırdır.
    * Ayaklı masada üst sınır kesindir, alt sınır bir hedeftir.
    """

    __tablename__ = "tables"
    __table_args__ = (
        # Katılımcı masasını numarayla bulur; çakışma kabul edilemez.
        UniqueConstraint("layout_id", "number", name="uq_tables_layout_number"),
        # Manuel modda iki masa aynı hücreye konamaz. Otomatik modda konum
        # olmadığı için kısıt yalnızca konumu dolu satırlara uygulanır.
        Index(
            "uq_tables_layout_cell",
            "layout_id",
            "grid_x",
            "grid_y",
            unique=True,
            postgresql_where=text("grid_x IS NOT NULL AND grid_y IS NOT NULL"),
        ),
        CheckConstraint("number > 0", name="number_positive"),
        # Masa tipi ile kapasite alanları tutarlı olmak zorunda: oturmalıda
        # sandalye sayısı, ayaklıda kişi aralığı dolu olur.
        CheckConstraint(
            "(kind = 'seated' AND seat_count IS NOT NULL"
            " AND min_people IS NULL AND max_people IS NULL)"
            " OR (kind = 'standing' AND seat_count IS NULL"
            " AND min_people IS NOT NULL AND max_people IS NOT NULL)",
            name="capacity_matches_kind",
        ),
        CheckConstraint("seat_count IS NULL OR seat_count > 0", name="seat_count_positive"),
        CheckConstraint("min_people IS NULL OR min_people > 0", name="min_people_positive"),
        CheckConstraint(
            "max_people IS NULL OR min_people IS NULL OR max_people >= min_people",
            name="people_range",
        ),
        status_check("kind", TableKind, "table_kind"),
    )

    layout_id: Mapped[int] = mapped_column(
        ForeignKey("layouts.id", ondelete="CASCADE"), nullable=False
    )

    # Otomatik artan üretilir ama organizatör değiştirebilir (şartname M5).
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    kind: Mapped[TableKind] = mapped_column(status_column(TableKind, "table_kind"), nullable=False)
    seat_count: Mapped[int | None] = mapped_column(Integer)
    min_people: Mapped[int | None] = mapped_column(Integer)
    max_people: Mapped[int | None] = mapped_column(Integer)

    grid_x: Mapped[int | None] = mapped_column(Integer)
    grid_y: Mapped[int | None] = mapped_column(Integer)

    label: Mapped[str | None] = mapped_column(String(100))

    layout: Mapped["Layout"] = relationship(back_populates="tables")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="table")


class LayoutArea(IdMixin, TimestampMixin, Base):
    """Sahne, giriş, büfe gibi masa olmayan işaretler.

    Yalnızca görsel yön bulma amaçlı; eşleştirmeye hiç girmez (şartname Bölüm 6).

    Not: alan blokları da ızgaraya oturur ve masalarla aynı hücreyi paylaşamaz.
    Bu kural iki ayrı tabloyu kapsadığı için tek bir benzersiz indeksle ifade
    edilemez — Aşama 5'te uygulama katmanında kontrol edilecek.
    """

    __tablename__ = "layout_areas"
    __table_args__ = (CheckConstraint("width > 0 AND height > 0", name="size_positive"),)

    layout_id: Mapped[int] = mapped_column(
        ForeignKey("layouts.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    grid_x: Mapped[int] = mapped_column(Integer, nullable=False)
    grid_y: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    layout: Mapped["Layout"] = relationship(back_populates="areas")
