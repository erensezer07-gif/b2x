"""Check-in (şartname M10).

Girişte katılımcıların kodu okutuluyor, gelenler işaretleniyor. Gelmeyenler
plan yenilenirken masadan çıkarılıyor (9.8).

## Kod tahmin edilemez

`registrations.qr_code` başvuru anında üretiliyor (`new_qr_code`, Aşama 6) ve
rastgele. Birincil anahtar kullanılsaydı biri sıradaki numarayı deneyerek
başkası adına giriş yapabilirdi.

Kod **etkinliğe özel değil, benzersiz**: şema `unique` diyor. Yine de okuma
etkinlikle sınırlı — başka etkinliğin kodu bu kapıdan geçmemeli.

## İşaretleme geri alınabilir

Yanlış kişi okutulabilir. `attendance` iki yönlü değişiyor ve `checked_in_at`
onunla birlikte: şemadaki `checkin_consistent` kısıtı ikisinin ayrışmasını
engelliyor.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AttendanceStatus,
    Event,
    Profile,
    Registration,
    RegistrationStatus,
    User,
)


class CheckInFailed(Exception):
    """Okuma veya işaretleme bir kapıya takıldı.

    Mesaj Türkçe ve kullanıcıya gösterilebilir; uç onu olduğu gibi taşıyor.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class AttendanceCounts:
    """*"Sayaç sürekli görünür: kaç kişi geldi, kaç kişi bekleniyor."* (M10)"""

    accepted: int
    present: int

    @property
    def expected(self) -> int:
        return max(self.accepted - self.present, 0)


def _with_profile():
    return (
        selectinload(Registration.user)
        .selectinload(User.profile)
        .options(selectinload(Profile.company)),
    )


async def counts(session: AsyncSession, event_id: int) -> AttendanceCounts:
    result = await session.execute(
        select(
            func.count(),
            func.count().filter(Registration.attendance == AttendanceStatus.PRESENT),
        )
        .select_from(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.ACCEPTED,
        )
    )
    accepted, present = result.one()
    return AttendanceCounts(accepted=accepted, present=present)


async def roster(
    session: AsyncSession, event_id: int, *, search: str | None = None
) -> list[Registration]:
    """Kabul edilmiş katılımcılar, geldi bilgisiyle.

    *"Elle arama da olmalı — telefonu bozulan, kodu bulamayan kişi listeden
    bulunup elle işaretlenebilir."* (M10)

    Arama Python tarafında: liste bir etkinliğin kabul edilmişleriyle sınırlı
    (birkaç yüz kişi) ve Türkçe harf katlaması veritabanı harmanlamasına
    bırakılamayacak kadar oynak.
    """
    result = await session.execute(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.ACCEPTED,
        )
        .options(*_with_profile())
        .order_by(Registration.id)
    )
    rows = list(result.scalars())
    if not search:
        return rows

    needle = _fold(search)
    return [row for row in rows if needle in _fold(_haystack(row))]


def _haystack(registration: Registration) -> str:
    profile = registration.user.profile
    if profile is None:
        return ""
    company = profile.company.name if profile.company else ""
    return f"{profile.full_name or ''} {company}"


def _fold(text: str) -> str:
    """Türkçe harfleri katlayarak karşılaştırılabilir hâle getirir.

    `str.lower()` yetmiyor: "İ" küçültülünce "i̇" (noktalı i + birleşen nokta)
    oluyor ve "i" ile eşleşmiyor. Aramada "İzmir" yazan da "izmir" yazan da
    aynı kişiyi bulmalı.
    """
    table = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")
    return text.translate(table).lower().strip()


async def find_by_code(session: AsyncSession, event_id: int, qr_code: str) -> Registration:
    """Okutulan kodun sahibini bulur.

    Kod başka bir etkinliğe aitse de "bu etkinlikte böyle bir kod yok" diyor:
    hangi etkinliğe ait olduğunu söylemek başka bir organizatörün katılımcı
    listesi hakkında bilgi sızdırırdı.
    """
    result = await session.execute(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.qr_code == qr_code.strip(),
            Registration.status == RegistrationStatus.ACCEPTED,
        )
        .options(*_with_profile())
    )
    registration = result.scalar_one_or_none()
    if registration is None:
        raise CheckInFailed("Bu etkinlikte böyle bir giriş kodu yok.")
    return registration


async def mark(
    session: AsyncSession,
    registration: Registration,
    *,
    present: bool,
    now: datetime | None = None,
) -> Registration:
    """Kişiyi geldi/gelmedi olarak işaretler.

    `checked_in_at` durumla birlikte değişiyor: şemadaki `checkin_consistent`
    kısıtı ikisinin ayrışmasını engelliyor, o yüzden ikisi tek yerde
    güncelleniyor.

    Zaten geldi işaretli birini tekrar okutmak hata değil — kapıda aynı kod
    iki kez okunabilir. Zaman **ilk** okumada kalıyor.
    """
    if present:
        if registration.attendance is not AttendanceStatus.PRESENT:
            registration.attendance = AttendanceStatus.PRESENT
            registration.checked_in_at = now or datetime.now(UTC)
    else:
        registration.attendance = AttendanceStatus.ABSENT
        registration.checked_in_at = None

    await session.commit()
    return registration


async def absent_registration_ids(session: AsyncSession, event_id: int) -> set[int]:
    """Kabul edilmiş ama gelmediği işaretlenmiş katılımcılar (9.8).

    Check-in hiç yapılmadıysa herkes `absent` sayılır ve bu küme bütün
    katılımcıları kapsar — o yüzden çağıran taraf check-in yapılıp
    yapılmadığına bakmalı. `has_check_in` bunu söylüyor.
    """
    result = await session.execute(
        select(Registration.id).where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.ACCEPTED,
            Registration.attendance == AttendanceStatus.ABSENT,
        )
    )
    return set(result.scalars())


async def has_check_in(session: AsyncSession, event_id: int) -> bool:
    """En az bir kişi geldi olarak işaretlendi mi.

    Minimum değişim modunun kapısı: kimse okutulmadan "gelmeyenleri çıkar"
    denirse plan tamamen boşalırdı.
    """
    result = await session.execute(
        select(Registration.id)
        .where(
            Registration.event_id == event_id,
            Registration.attendance == AttendanceStatus.PRESENT,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def started_slots(event: Event, *, now: datetime | None = None) -> set[int]:
    """Başlamış veya bitmiş turlar — 1 tabanlı (9.8).

    *"Başlamış veya bitmiş slotlara dokunulmaz. Sadece gelecek slotlar
    yeniden hesaplanır."*

    Programı `schedule.py` hesaplıyor; burada yalnızca "başladı mı" sorusu
    soruluyor.
    """
    from app.services.schedule import build_schedule

    moment = now or datetime.now(UTC)
    schedule = build_schedule(
        starts_at=event.starts_at,
        slot_count=event.slot_count,
        slot_duration_minutes=event.slot_duration_minutes,
        break_duration_minutes=event.break_duration_minutes,
    )
    return {timing.number for timing in schedule.slots if timing.starts_at <= moment}
