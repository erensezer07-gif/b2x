"""Şifre özetleme ve jetonlar (şartname M1).

*"Şifreler modern bir özetleme algoritmasıyla saklanır. Düz metin şifre hiçbir
yere yazılmaz, loglanmaz."*

Argon2id kullanılıyor — parola özetleme yarışmasının kazananı ve OWASP'ın ilk
önerisi. Tuz özetin içinde taşınır, ayrı bir sütun gerekmez.

## Jetonlar

Kısa ömürlü **erişim** jetonu ve uzun ömürlü **yenileme** jetonu. Süresi dolan
erişim jetonu, yenileme jetonuyla arka planda sessizce tazelenir; kullanıcı
tekrar giriş yapmak zorunda kalmaz (M1, Bölüm 10).

İkisi de aynı imzayla üretildiği için `type` iddiası zorunlu: yenileme jetonuyla
korumalı bir uca girilemesin diye her doğrulamada beklenen tür kontrol edilir.

**Sunucuda iptal listesi yok.** MVP'de e-posta altyapısı olmadığı için oturum
sonlandırma akışı da yok; çıkış istemcide jetonu silmekle olur. Erişim jetonunun
ömrü kısa tutularak risk sınırlanıyor. Sunucu tarafında iptal gerekirse
`jti` iddiası hazır — bir kara liste tablosu eklemek yeterli olur.
"""

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.config import get_settings

ALGORITHM = "HS256"

# Kayıt ekranındaki asgari kural (M1). Kurtarma seçeneği olmadığı için kullanıcı
# bunu bilerek seçiyor; aşırı kısıt koymak, unutulan şifreyi telafi edilemez
# yapardı.
PASSWORD_MIN_LENGTH = 8

_hasher = PasswordHasher()


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Jeton okunamadı, süresi doldu veya beklenen türde değil."""


def hash_password(password: str) -> str:
    """Şifreyi Argon2id ile özetler. Düz metin hiçbir yerde saklanmaz."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Şifre özetle eşleşiyor mu.

    Argon2 eşleşmeme durumunda istisna atar; burada sade bir doğru/yanlışa
    çevriliyor. Bozuk bir özet de "eşleşmedi" sayılır — hangi hesabın özetinin
    bozuk olduğunu dışarıya sızdırmamak için.
    """
    try:
        return _hasher.verify(password_hash, password)
    except Argon2Error:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Argon2 parametreleri sertleştirildiyse özet yenilenmeli."""
    return _hasher.check_needs_rehash(password_hash)


def create_token(user_id: int, token_type: TokenType) -> str:
    """Kullanıcı için imzalı jeton üretir."""
    settings = get_settings()
    now = datetime.now(UTC)

    if token_type is TokenType.ACCESS:
        lifetime = timedelta(minutes=settings.jwt_access_token_minutes)
    else:
        lifetime = timedelta(days=settings.jwt_refresh_token_days)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + lifetime,
        # Aynı saniyede üretilen iki jeton birbirinin aynısı olmasın: yenileme
        # akışında eski jetonla yenisi ayırt edilebilmeli.
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> int:
    """Jetonu doğrular ve kullanıcı kimliğini döndürür.

    Beklenen tür kontrolü kritik: yenileme jetonu erişim jetonu yerine
    kullanılabilseydi, uzun ömürlü bir jeton korumalı uçlara girerdi.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "type"]},
        )
    except jwt.PyJWTError as error:
        raise TokenError("Jeton geçersiz veya süresi dolmuş.") from error

    if payload.get("type") != expected_type.value:
        raise TokenError("Jeton türü beklenenden farklı.")

    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as error:
        raise TokenError("Jeton geçersiz bir kullanıcı taşıyor.") from error
