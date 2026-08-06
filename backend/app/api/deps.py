"""Ortak API bağımlılıkları.

Görünürlük kuralları sunucuda uygulanır (şartname Bölüm 7): *"Arayüzde
göstermiyoruz yeterli değil — istek doğrudan atılsa bile veri dönmemeli."*
Her korumalı uç `CurrentUser` üzerinden geçer; kimliği doğrulanmamış istek
uca hiç ulaşmaz.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenError, TokenType, decode_token
from app.db import get_session
from app.models import Event, User
from app.services.queue import JobQueue, get_job_queue
from app.services.storage import Storage, get_storage

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Depolama bağımlılık olarak veriliyor: uçlar somut sınıfı değil sözleşmeyi
# görüyor (Bölüm 3) ve testler `dependency_overrides` ile geçici bir klasöre
# yönlendirebiliyor.
StorageDep = Annotated[Storage, Depends(get_storage)]

# İş kuyruğu aynı gerekçeyle bağımlılık: testler gerçek Redis'e iş atmamalı
# (5.4). Ayrıntı `app/services/queue.py` başlığında.
JobQueueDep = Annotated[JobQueue, Depends(get_job_queue)]

# `auto_error=False`: eksik başlığı da kendimiz yanıtlıyoruz ki mesaj Türkçe
# olsun ve "jeton yok" ile "jeton geçersiz" aynı cevabı versin.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORISED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Oturum doğrulanamadı.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Erişim jetonunu doğrular ve kullanıcıyı getirir.

    Yenileme jetonuyla buraya girilemez: `decode_token` beklenen türü kontrol
    eder (M1).
    """
    if credentials is None:
        raise _UNAUTHORISED

    try:
        user_id = decode_token(credentials.credentials, TokenType.ACCESS)
    except TokenError as error:
        raise _UNAUTHORISED from error

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        # Hesap silinmiş veya kapatılmışsa jeton hâlâ geçerli olabilir; kaynağı
        # kullanıcı kaydı belirler.
        raise _UNAUTHORISED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_owned_event(event_id: int, user: CurrentUser, session: SessionDep) -> Event:
    """Etkinliği yükler ve oturumdaki kullanıcının organizatörü olduğunu doğrular.

    Şartname Bölüm 7: *"Organizatör kendi etkinliğinin her şeyini görür. Başka
    organizatörlerin etkinliklerinin planlarına erişemez."* Ayrı bir yetki
    katmanı yok — rol etkinliğe göre belirleniyor, bu yüzden kontrol her uçta
    sahiplikle yapılıyor.

    Başkasının etkinliğine **404** dönüyor, 403 değil: 403 "böyle bir etkinlik
    var ama giremezsin" bilgisini sızdırırdı. Dışarıdan bakan biri etkinlik
    kimliklerini tarayarak hangilerinin var olduğunu öğrenememeli.
    """
    event = await session.get(Event, event_id)
    if event is None or event.organizer_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Etkinlik bulunamadı.",
        )
    return event


OwnedEvent = Annotated[Event, Depends(get_owned_event)]
