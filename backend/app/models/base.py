"""ORM temeli ve her tabloda tekrarlanan alanlar.

Birincil anahtarlar `bigint` ve otomatik artan. Motor kendi içinde tam sayı indeks
kullandığı için (şartname 9.2) dönüşüm bedelsiz olur; günlükler ve adresler de
okunabilir kalır.

Kimliği tahmin edilemez olması gereken tek alan katılımcının QR kodudur ve o,
`registrations.qr_code` içinde ayrıca rastgele üretilir.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Kısıt ve indeks adları elle verilmezse Postgres kendi adını üretir
# ("companies_normalized_name_key" gibi). O adlar migration'a rastgele girer ve
# geri alma işlemleri kırılganlaşır. Bu kural hepsini öngörülebilir hale getirir.
#
# Not: CheckConstraint'lere kısa ad verilir ("email_lowercase"); önekini bu kural
# ekler ve sonuç "ck_users_email_lowercase" olur.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Tüm ORM modellerinin temeli."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class IdMixin:
    """Otomatik artan birincil anahtar.

    `sort_order` negatif: mixin'den geldiği için normalde kolon listesinin sonuna
    düşerdi, oysa `id` en başta okunur.
    """

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True, sort_order=-100)


class TimestampMixin:
    """Oluşturma ve son değişiklik zamanı.

    Zaman damgaları saat dilimi taşır. Etkinlikler fiziksel ve yerel olsa da
    saklama tarafında tek bir referans olması, farklı makinelerde çalışırken
    kaymayı önler.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=100,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        sort_order=100,
    )
