"""Sağlık uçları.

`/health` bilerek bağımlılıklara bakmaz — bu yüzden veritabanı veya Redis
çalışmadan da test edilebilir. `/health/ready` gerçek bağlantı gerektirdiği için
burada test edilmez; onun doğrulaması `docker compose up` sonrası elle yapılır.
"""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_unknown_path_returns_404() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/olmayan-bir-yol")

    assert response.status_code == 404
