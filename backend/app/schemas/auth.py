"""Kimlik istek ve yanıt modelleri (şartname M1)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import PASSWORD_MIN_LENGTH


class RegisterRequest(BaseModel):
    """Kayıt.

    MVP'de e-posta doğrulaması yok: kayıt anında hesap doğrudan kullanılabilir
    hale gelir (M1).
    """

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    """Kısa ömürlü erişim ve uzun ömürlü yenileme jetonu (M1)."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Hesap bilgisi.

    `password_hash` bilerek yok — şifre hiçbir yanıtta görünmez.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    created_at: datetime
