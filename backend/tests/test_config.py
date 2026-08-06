"""Ayarların ortamdan okunması.

Şartname Bölüm 0 ve Bölüm 10 (Taşınabilirlik): hiçbir ortam bilgisi koda gömülmez,
proje başka bir makinede yalnızca ortam dosyası değiştirilerek çalışır.

Testler `_env_file=None` ile çalışır — makinedeki gerçek `.env` dosyası sonucu
etkilemesin diye.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE_ENVIRONMENT = {
    "POSTGRES_USER": "kullanici",
    "POSTGRES_PASSWORD": "parola",
    "POSTGRES_DB": "veritabani",
    "POSTGRES_HOST": "sunucu.ornek",
    "POSTGRES_PORT": "5433",
    "REDIS_HOST": "kuyruk.ornek",
    "REDIS_PORT": "6380",
    "JWT_SECRET": "gizli",
}


def _build_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    for key, value in {**BASE_ENVIRONMENT, **overrides}.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_database_url_is_built_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(monkeypatch)
    assert settings.database_url == (
        "postgresql+asyncpg://kullanici:parola@sunucu.ornek:5433/veritabani"
    )


def test_redis_url_is_built_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(monkeypatch)
    assert settings.redis_url == "redis://kuyruk.ornek:6380"


def test_special_characters_in_password_are_escaped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parolada geçen '@' veya '/' adresi bozmamalı."""
    settings = _build_settings(monkeypatch, POSTGRES_PASSWORD="p@rola/1:2")
    assert "p%40rola%2F1%3A2" in settings.database_url
    assert settings.database_url.endswith("@sunucu.ornek:5433/veritabani")


def test_missing_secret_prevents_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gizli değer eksikse uygulama açılmamalı, varsayılanla devam etmemeli."""
    for key, value in BASE_ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("JWT_SECRET")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_cors_origins_are_split_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(monkeypatch, CORS_ORIGINS="https://a.ornek , https://b.ornek ,")
    assert settings.cors_origin_list == ["https://a.ornek", "https://b.ornek"]


def test_empty_cors_origins_yields_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(monkeypatch, CORS_ORIGINS="")
    assert settings.cors_origin_list == []


def test_secrets_are_not_exposed_in_string_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ayarlar loglanırsa parola ve anahtar düz metin olarak sızmamalı."""
    settings = _build_settings(monkeypatch)
    dumped = repr(settings)
    assert "parola" not in dumped
    assert "gizli" not in dumped
