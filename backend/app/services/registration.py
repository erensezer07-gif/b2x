"""Etkinlik başvurusu (şartname M3).

Başvurunun önündeki kapılar burada, tek yerde. Uçlar yalnızca çağırıp hatayı
HTTP'ye çeviriyor.

Kapılardan biri Aşama 3'te kurulmuştu ama şimdiye kadar hiçbir şeyi
engellemiyordu: *"Etkinliğe başvurabilmek için profil en az şu alanları
içermeli... Eksikse başvuru butonu çalışmaz ve neyin eksik olduğu yazılır."*
`app.services.profile` bunu hesaplıyor, burada ilk kez iş görüyor.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import Event, EventStatus, Registration, RegistrationStatus

# Şartname Bölüm 6: "QR kodu (her katılımcı için benzersiz)". Tahmin
# edilebilir olmamalı — kimlik numarası değil, rastgele bir dizgi.
# Aşama 11 bunu okuyacak, üretmeyecek.
QR_CODE_BYTES = 24


def new_qr_code() -> str:
    return secrets.token_urlsafe(QR_CODE_BYTES)


class ApplicationBlocked(Exception):
    """Başvuru bir kapıya takıldı.

    Mesaj Türkçe ve kullanıcıya gösterilebilir; uç onu olduğu gibi taşıyor.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProfileIncomplete(Exception):
    """Profil başvuru için yeterli değil.

    Eksik kalemler **İngilizce anahtar** olarak taşınıyor; Türkçe cümleyi
    arayüz kuruyor (Aşama 3'teki kalıp). Ayrı bir hata tipi çünkü uç bunu
    422 ile ve eksik listesiyle döndürüyor — kullanıcı neyi düzelteceğini
    görmeli.
    """

    def __init__(self, missing: tuple[str, ...]) -> None:
        super().__init__("Profil başvuru için yeterli değil.")
        self.missing = missing


@dataclass(frozen=True, slots=True)
class RegistrationCounts:
    """Bir etkinliğin başvuru sayıları.

    **Kontenjanı yalnızca kabul edilenler doldurur.** Bekleyenler de sayılsaydı
    elle onay yapan organizatör kontenjandan fazla başvuru toplayıp aralarından
    seçemezdi — elle onayın tüm anlamı bu.
    """

    accepted: int
    pending: int

    def remaining(self, capacity: int) -> int:
        return max(capacity - self.accepted, 0)

    def is_full(self, capacity: int) -> bool:
        return self.accepted >= capacity


def deadline_passed(event: Event, *, now: datetime | None = None) -> bool:
    if event.registration_deadline is None:
        return False
    return (now or datetime.now(UTC)) > event.registration_deadline


def is_open_for_applications(
    event: Event, counts: RegistrationCounts, *, now: datetime | None = None
) -> bool:
    """*"Kontenjan dolduysa veya son başvuru tarihi geçtiyse başvuru kapanır."*"""
    return (
        event.status is EventStatus.REGISTRATION_OPEN
        and not deadline_passed(event, now=now)
        and not counts.is_full(event.capacity)
    )


def check_can_apply(
    event: Event,
    counts: RegistrationCounts,
    *,
    user_id: int,
    profile_missing: tuple[str, ...],
    existing: Registration | None,
    now: datetime | None = None,
) -> None:
    """Başvurunun önündeki kapılar. Geçerse sessizce döner.

    Sıra bilinçli: önce kullanıcıya özel engeller, sonra etkinliğe özel
    olanlar. Profili eksik birine "kontenjan dolu" demek yanıltıcı olurdu —
    profilini tamamlayınca yine başvuramayacak.
    """
    if event.organizer_id == user_id:
        # Rol etkinliğe göre belirleniyor (Bölüm 7); aynı kişi aynı etkinlikte
        # hem organizatör hem katılımcı olamaz.
        raise ApplicationBlocked("Kendi düzenlediğin etkinliğe başvuramazsın.")

    if existing is not None and existing.status is not RegistrationStatus.CANCELLED:
        raise ApplicationBlocked(
            {
                RegistrationStatus.PENDING: "Bu etkinliğe zaten başvurdun, yanıt bekleniyor.",
                RegistrationStatus.ACCEPTED: "Bu etkinliğe zaten kabul edildin.",
                RegistrationStatus.REJECTED: "Bu etkinliğe başvurun daha önce reddedildi.",
            }[existing.status]
        )

    if profile_missing:
        raise ProfileIncomplete(profile_missing)

    if event.status is not EventStatus.REGISTRATION_OPEN:
        raise ApplicationBlocked("Bu etkinlik başvuruya açık değil.")

    if deadline_passed(event, now=now):
        raise ApplicationBlocked("Son başvuru tarihi geçti.")

    if counts.is_full(event.capacity):
        raise ApplicationBlocked("Kontenjan doldu.")


def initial_status(event: Event) -> RegistrationStatus:
    """*"Başvurular otomatik mi kabul edilecek yoksa organizatör tek tek mi
    onaylayacak"* (M4)."""
    return (
        RegistrationStatus.ACCEPTED
        if event.auto_approve_registrations
        else RegistrationStatus.PENDING
    )


def check_can_approve(event: Event, counts: RegistrationCounts) -> None:
    """Onay kontenjanı aşamaz.

    Başvuru anında kontenjan doluysa engelleniyor; ama elle onayda bekleyenler
    kontenjanı doldurmuyor, dolayısıyla organizatör kontenjandan fazla
    bekleyenle karşılaşabilir. Kapı burada da lazım.
    """
    if counts.is_full(event.capacity):
        raise ApplicationBlocked(
            f"Kontenjan doldu: {event.capacity} kişi kabul edildi. "
            "Onaylamak için önce kontenjanı artır."
        )
