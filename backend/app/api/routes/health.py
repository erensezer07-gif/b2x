"""Sağlık uçları.

Bunlar ürün özelliği değil, altyapıdır: Docker'ın konteyneri hazır sayması ve
"sistem ayağa kalktı" iddiasının doğrulanabilmesi için var.

* `/health` — bağımlılıklara bakmaz, yalnızca sürecin cevap verdiğini söyler.
* `/health/ready` — veritabanına ve Redis'e gerçekten ulaşılıyor mu ona bakar.
  Biri bile erişilemezse 503 döner, böylece bozuk bir kurulum sessizce geçmez.
"""

from typing import Any

from fastapi import APIRouter, Response, status
from redis.asyncio import Redis
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine

router = APIRouter(tags=["saglik"])


@router.get("/health", summary="Süreç ayakta mı")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _check_database() -> str:
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # bağlantı hatasının türü sürücüye göre değişir
        return f"hata: {type(exc).__name__}"
    return "ok"


async def _check_redis() -> str:
    client = Redis.from_url(get_settings().redis_url)
    try:
        await client.ping()
    except Exception as exc:
        return f"hata: {type(exc).__name__}"
    finally:
        await client.aclose()
    return "ok"


@router.get("/health/ready", summary="Bağımlılıklara erişilebiliyor mu")
async def ready(response: Response) -> dict[str, Any]:
    checks = {
        "database": await _check_database(),
        "redis": await _check_redis(),
    }
    healthy = all(result == "ok" for result in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "hata", "checks": checks}
