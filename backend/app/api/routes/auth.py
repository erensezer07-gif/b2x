"""Kimlik uçları (şartname M1).

Kayıt, giriş ve jeton yenileme. **E-posta doğrulaması ve şifre sıfırlama yok** —
MVP'de e-posta gönderimi bulunmadığı için (Bölüm 2). Kayıt anında hesap doğrudan
kullanılabilir hale gelir.

## Çıkış neden burada yok

Jetonlar durumsuz: sunucuda oturum kaydı tutulmuyor. Çıkış, istemcinin jetonu
güvenli depodan silmesiyle olur. İş yapmayan bir `/auth/logout` ucu, sunucunun
oturumu gerçekten sonlandırdığı izlenimi verirdi — yanıltıcı olurdu.

Sunucu tarafında iptal gerekirse `app.core.security` içindeki `jti` iddiası
hazır; bir kara liste tablosu eklemek yeterli olur.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, SessionDep
from app.core.security import (
    TokenError,
    TokenType,
    create_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models import Profile, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["kimlik"])

# Giriş başarısız olduğunda hangi adımın tuttuğu söylenmez: "böyle bir e-posta
# yok" ile "şifre yanlış" ayrı yanıtlar verseydi, kimlerin kayıtlı olduğu
# dışarıdan öğrenilebilirdi.
_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="E-posta veya şifre hatalı.",
)


def _issue_tokens(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_token(user_id, TokenType.ACCESS),
        refresh_token=create_token(user_id, TokenType.REFRESH),
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Kayıt ol",
)
async def register(payload: RegisterRequest, session: SessionDep) -> TokenPair:
    """Hesap açar ve doğrudan oturum başlatır.

    Bölüm 10: *"Kayıt olan kullanıcı doğrudan giriş yapabiliyor."* Ayrı bir
    giriş adımı istenmiyor, jetonlar burada dönüyor.
    """
    user = User(
        # E-posta her zaman küçük harf saklanır; şemada bunu zorlayan bir CHECK
        # kısıtı var (Aşama 1).
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
    )
    session.add(user)

    try:
        await session.flush()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta adresi zaten kayıtlı.",
        ) from error

    # Profil kaydı hemen açılır: sihirbaz ilk adımdan itibaren kaydedebilsin (M2).
    session.add(Profile(user_id=user.id))
    await session.commit()

    return _issue_tokens(user.id)


@router.post("/login", summary="Giriş yap")
async def login(payload: LoginRequest, session: SessionDep) -> TokenPair:
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise _INVALID_CREDENTIALS
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu hesap kapatılmış.",
        )

    # Argon2 parametreleri sertleştirilmişse özet sessizce yenilenir; kullanıcı
    # bir şey fark etmez.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        await session.commit()

    return _issue_tokens(user.id)


@router.post("/refresh", summary="Jetonu tazele")
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenPair:
    """Süresi dolan erişim jetonunu yenileme jetonuyla tazeler.

    Bölüm 10: *"Erişim jetonunun süresi dolduğunda kullanıcı fark etmeden
    yenileniyor."* İstemci bunu araya giren bir katmanda, kullanıcıya hiç
    göstermeden yapar.
    """
    try:
        user_id = decode_token(payload.refresh_token, TokenType.REFRESH)
    except TokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yenileme jetonu geçersiz veya süresi dolmuş.",
        ) from error

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yenileme jetonu geçersiz veya süresi dolmuş.",
        )

    return _issue_tokens(user.id)


@router.get("/me", summary="Oturumdaki hesap")
async def read_me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
