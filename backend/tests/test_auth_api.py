"""Kimlik uçları (şartname M1, Bölüm 10).

Kabul kriteri: *"Kayıt olan kullanıcı doğrudan giriş yapabiliyor. Erişim
jetonunun süresi dolduğunda kullanıcı fark etmeden yenileniyor."*
"""

from collections.abc import Callable

from httpx import AsyncClient

PASSWORD = "cok-gizli-sifre"


async def test_registration_returns_a_working_session(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Kayıt olan doğrudan oturum açmış olmalı — ayrı bir giriş adımı yok."""
    response = await client.post(
        "/auth/register", json={"email": unique_email(), "password": PASSWORD}
    )
    assert response.status_code == 201

    tokens = response.json()
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200


async def test_email_is_stored_lowercase(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    email = unique_email()
    response = await client.post(
        "/auth/register", json={"email": email.upper(), "password": PASSWORD}
    )
    tokens = response.json()

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["email"] == email.lower()


async def test_login_works_regardless_of_email_case(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})

    response = await client.post("/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert response.status_code == 200


async def test_duplicate_email_is_rejected(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})

    response = await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 409


async def test_wrong_password_is_rejected(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})

    response = await client.post("/auth/login", json={"email": email, "password": "yanlis-sifre"})
    assert response.status_code == 401


async def test_unknown_email_gives_the_same_answer_as_wrong_password(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Ayrı cevaplar verilseydi kimlerin kayıtlı olduğu dışarıdan öğrenilebilirdi."""
    email = unique_email()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})

    wrong_password = await client.post(
        "/auth/login", json={"email": email, "password": "yanlis-sifre"}
    )
    unknown_email = await client.post(
        "/auth/login", json={"email": unique_email(), "password": PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code
    assert wrong_password.json() == unknown_email.json()


async def test_short_password_is_rejected(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Kayıt ekranında şifre gücü için asgari kural uygulanır (M1)."""
    response = await client.post(
        "/auth/register", json={"email": unique_email(), "password": "kisa"}
    )
    assert response.status_code == 422


async def test_refresh_token_produces_a_new_access_token(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Bölüm 10: süresi dolan erişim jetonu kullanıcı fark etmeden yenileniyor."""
    response = await client.post(
        "/auth/register", json={"email": unique_email(), "password": PASSWORD}
    )
    tokens = response.json()

    refreshed = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != tokens["access_token"]

    me = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200


async def test_refresh_token_cannot_be_used_as_an_access_token(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Uzun ömürlü jeton korumalı uçlara giremez — jeton türü kontrol ediliyor."""
    response = await client.post(
        "/auth/register", json={"email": unique_email(), "password": PASSWORD}
    )
    refresh_token = response.json()["refresh_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert me.status_code == 401


async def test_access_token_cannot_be_used_to_refresh(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    response = await client.post(
        "/auth/register", json={"email": unique_email(), "password": PASSWORD}
    )
    access_token = response.json()["access_token"]

    refreshed = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert refreshed.status_code == 401


async def test_protected_endpoint_needs_a_token(client: AsyncClient) -> None:
    """Görünürlük sunucuda uygulanır (Bölüm 7): jetonsuz istek veri döndürmez."""
    assert (await client.get("/auth/me")).status_code == 401
    assert (await client.get("/profile")).status_code == 401
    assert (await client.get("/sectors")).status_code == 401
    assert (await client.get("/companies?q=abc")).status_code == 401


async def test_garbage_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/auth/me", headers={"Authorization": "Bearer sacma-sapan"})
    assert response.status_code == 401


async def test_password_never_appears_in_any_response(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """*"Düz metin şifre hiçbir yere yazılmaz, loglanmaz."* (M1)"""
    email = unique_email()
    register = await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    login = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )

    for response in (register, login, me):
        body = response.text
        assert PASSWORD not in body
        assert "password_hash" not in body
