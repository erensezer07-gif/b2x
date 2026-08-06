"""Durum ve tür listeleri.

Veritabanında metin olarak saklanır ve CHECK kısıtıyla sınırlandırılır.
Postgres'in yerel ENUM tipi kullanılmaz: ona sonradan değer eklemek ya da
çıkarmak migration tarafında zahmetlidir, metin + CHECK ise sade kalır.

Değerler İngilizce ve küçük harf. Kullanıcıya gösterilecek Türkçe karşılıkları
arayüz katmanında üretilir — veritabanı gösterim metni tutmaz.
"""

from enum import StrEnum

from sqlalchemy import CheckConstraint
from sqlalchemy import Enum as SqlEnum


def status_column(enum_class: type[StrEnum], type_name: str) -> SqlEnum:
    """Bir `StrEnum`'u metin sütununa çevirir.

    `values_callable` olmadan SQLAlchemy üye *adını* ("REGISTRATION_OPEN")
    saklardı; değerin ("registration_open") saklanmasını istiyoruz.

    Değer denetimi burada değil, `status_check` ile ayrıca eklenir — sebebi
    aşağıda.
    """
    return SqlEnum(
        enum_class,
        native_enum=False,
        # SQLAlchemy'nin kendi ürettiği CHECK kısıtı kullanılmıyor. O kısıt
        # tabloya yalnızca DDL üretilirken ekleniyor, model üzerinde görünmüyor;
        # sonuçta Alembic autogenerate onu "modelde yok" sayıp her seferinde
        # silmeye çalışıyordu. Kısıtı elle yazınca hem veritabanında hem modelde
        # duruyor ve autogenerate temiz kalıyor.
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda enum: [member.value for member in enum],
        name=type_name,
    )


def status_check(
    column_name: str, enum_class: type[StrEnum], constraint_name: str
) -> CheckConstraint:
    """Sütuna yalnızca listedeki değerlerin yazılabilmesini garanti eder.

    Bu kısıt olmadan durum sütunu denetimsiz bir metin olur ve veritabanına
    listede bulunmayan bir durum yazılabilir.
    """
    values = ", ".join(f"'{member.value}'" for member in enum_class)
    return CheckConstraint(f"{column_name} IN ({values})", name=constraint_name)


class TagDirection(StrEnum):
    """Etiketin profildeki yönü.

    Şartname Bölüm 6: "ne sunuyorum" ve "ne arıyorum" aynı etiket havuzundan
    seçilir. Bu yüzden iki ayrı tablo değil, tek tabloda yön alanı var.
    """

    OFFERED = "offered"
    SOUGHT = "sought"


class EventStatus(StrEnum):
    """Etkinlik durumu — yalnızca başvuru akışını yönetir.

    Planın hazır veya yayında olup olmadığı buraya yazılmaz; o bilgi `plans`
    tablosundadır (şartname Bölüm 5.2 ve Bölüm 13).
    """

    DRAFT = "draft"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    COMPLETED = "completed"


class LayoutMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class TableKind(StrEnum):
    SEATED = "seated"
    STANDING = "standing"


class RegistrationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AttendanceStatus(StrEnum):
    """Check-in ile işaretlenir (şartname M10)."""

    ABSENT = "absent"
    PRESENT = "present"


class MeetingRequestStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class PlanStatus(StrEnum):
    """Bir etkinlikte aynı anda en fazla bir plan `PUBLISHED` olabilir.

    Bu kural `plans` tablosundaki koşullu benzersiz indeksle zorlanır.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class JobStatus(StrEnum):
    """Eşleştirme hesabının durumu (şartname 5.4).

    **Plan durumuyla karıştırılmamalı.** `PlanStatus` planın kendisini anlatır
    (taslak / yayında / arşiv), bu ise onu üreten **hesabın** nerede olduğunu.
    Bir plan hesabı bitmiş (`DONE`) ama hâlâ taslak olabilir; organizatör
    inceleyip yayınlayana kadar öyle kalır.

    İkisini tek alanda toplamak Bölüm 13'ün "plan görünürlüğünü etkinlik
    durumundan okumak" hatasının kardeşi olurdu.
    """

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
