"""Görüşme talepleri (şartname M9).

Katılımcı, kabul edilmiş diğer katılımcıların listesini görür ve içlerinden
seçtiklerine *"görüşmek istiyorum"* der. Motor bunu bonus olarak değerlendirir
(9.3): karşılıklı talep neredeyse kesin eşleşme, tek taraflı güçlü bir tercih.

## Kimin ne gördüğü

M9: *"Talep gönderildiği kişiye bildirilmez. Karşı taraf kimin kendisini
istediğini görmez. Sebep: sosyal baskı yaratmamak."*

Bu yüzden **gelen talep diye bir uç yok.** Katılımcı yalnızca kendi
gönderdiklerini okuyabiliyor; okunacak bir yer olmadığı için sızacak bir yer
de yok — Aşama 9'daki kalıbın aynısı.

Katılımcı listesi de tam profil açmıyor: ad, unvan, şirket, sektör. Tam profil
yalnızca aynı masaya düşenler için (Bölüm 7).

## Kıtlık

*"Bu sınır olmazsa herkes herkese talep atar ve sistem 'en çok talep atan
kazanır'a döner. Kıtlık, insanı gerçekten istediğini seçmeye zorlar."*

Hak `event.request_quota`. Geri çekmek hakkı **iade ediyor**: kıtlığın anlamı
"aynı anda kaç kişiyi istiyorsun", yanlış kişiye gönderilen talep
düzeltilebilmeli.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Event,
    MeetingRequest,
    MeetingRequestStatus,
    Registration,
    RegistrationStatus,
)


class RequestBlocked(Exception):
    """Talep bir kapıya takıldı.

    Mesaj Türkçe ve kullanıcıya gösterilebilir; uç onu olduğu gibi taşıyor
    (Aşama 6'daki `ApplicationBlocked` kalıbı).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class RequestQuota:
    """Katılımcının talep hakkı.

    `used` yalnızca **aktif** talepleri sayıyor; geri çekilenler hakkı geri
    veriyor.
    """

    quota: int
    used: int

    @property
    def remaining(self) -> int:
        return max(self.quota - self.used, 0)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0


def requests_open(event: Event, *, now: datetime | None = None) -> bool:
    """Talep sistemi açık mı (M9).

    *"Talepler bir zamanda kapanır... Kapanmazsa plan hiç kilitlenemez."*
    Kapanış zamanı verilmemişse sistem hiç kapanmamış sayılıyor — kontrol
    listesindeki `REQUESTS_STILL_OPEN` uyarısıyla aynı okuma.
    """
    if event.requests_close_at is None:
        return True
    return (now or datetime.now(UTC)) <= event.requests_close_at


async def quota_of(session: AsyncSession, event: Event, registration_id: int) -> RequestQuota:
    used = await session.execute(
        select(func.count())
        .select_from(MeetingRequest)
        .where(
            MeetingRequest.requester_registration_id == registration_id,
            MeetingRequest.status == MeetingRequestStatus.ACTIVE,
        )
    )
    return RequestQuota(quota=event.request_quota, used=used.scalar_one())


async def sent_requests(session: AsyncSession, registration_id: int) -> dict[int, MeetingRequest]:
    """Kişinin **gönderdiği** aktif talepler: hedef kimliği → satır.

    Yalnızca gönderilenler. Gelen talepler hiçbir yerde okunmuyor (M9).
    """
    result = await session.execute(
        select(MeetingRequest).where(
            MeetingRequest.requester_registration_id == registration_id,
            MeetingRequest.status == MeetingRequestStatus.ACTIVE,
        )
    )
    return {item.target_registration_id: item for item in result.scalars()}


async def _accepted(session: AsyncSession, event_id: int, registration_id: int) -> bool:
    result = await session.execute(
        select(Registration.id).where(
            Registration.id == registration_id,
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.ACCEPTED,
        )
    )
    return result.scalar_one_or_none() is not None


async def send_request(
    session: AsyncSession,
    event: Event,
    requester: Registration,
    target_registration_id: int,
) -> MeetingRequest:
    """Talep gönderir. Kapıların hepsi burada.

    Geri çekilmiş bir satır varsa **yeniden canlandırılıyor**: ikili
    benzersizliği duruma bakmıyor, yeni satır eklemek `IntegrityError`
    verirdi. Aşama 6'daki başvuru kalıbının aynısı.
    """
    if not requests_open(event):
        raise RequestBlocked("Görüşme talepleri kapandı.")
    if target_registration_id == requester.id:
        raise RequestBlocked("Kendine talep gönderemezsin.")
    if not await _accepted(session, event.id, target_registration_id):
        raise RequestBlocked("Bu kişi etkinliğin katılımcısı değil.")

    existing = await session.execute(
        select(MeetingRequest).where(
            MeetingRequest.requester_registration_id == requester.id,
            MeetingRequest.target_registration_id == target_registration_id,
        )
    )
    request = existing.scalar_one_or_none()
    if request is not None and request.status == MeetingRequestStatus.ACTIVE:
        raise RequestBlocked("Bu kişiye zaten talep gönderdin.")

    quota = await quota_of(session, event, requester.id)
    if quota.exhausted:
        raise RequestBlocked(
            f"Talep hakkın doldu. Bu etkinlikte {quota.quota} talep "
            "gönderebilirsin; birini geri çekip yeniden deneyebilirsin."
        )

    if request is None:
        request = MeetingRequest(
            event_id=event.id,
            requester_registration_id=requester.id,
            target_registration_id=target_registration_id,
            status=MeetingRequestStatus.ACTIVE,
        )
        session.add(request)
    else:
        request.status = MeetingRequestStatus.ACTIVE

    await session.commit()
    return request


async def withdraw_request(
    session: AsyncSession, event: Event, requester: Registration, request_id: int
) -> None:
    """Talebi geri çeker ve hakkı iade eder.

    Satır **silinmiyor**, durumu değişiyor: aynı kişiye tekrar talep
    gönderilebilmesi için ikili benzersizliğinin korunması gerekiyor.

    Talepler kapandıktan sonra geri çekme de kapalı (M9): açık bırakmak
    kilitlenmiş bir planı yeniden oynatırdı.
    """
    if not requests_open(event):
        raise RequestBlocked("Görüşme talepleri kapandı; talep geri çekilemez.")

    result = await session.execute(
        select(MeetingRequest).where(
            MeetingRequest.id == request_id,
            # Başkasının talebi geri çekilemez. Kimlik jetondan geliyor.
            MeetingRequest.requester_registration_id == requester.id,
            MeetingRequest.status == MeetingRequestStatus.ACTIVE,
        )
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise RequestBlocked("Böyle bir talebin yok.")

    request.status = MeetingRequestStatus.CANCELLED
    await session.commit()
