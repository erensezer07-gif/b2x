"""ARQ arka plan işçisi.

Eşleştirme motoru HTTP isteği içinde çalıştırılamaz (şartname 5.4) — istek zaman
aşımına uğrar. Uzun süren işler bu işçiye kuyruklanır.

Şu an iş listesi boş; kuyruk altyapısı ayakta durur, eşleştirme işi Aşama 7'de
eklenir.

Çalıştırma:  arq app.worker.WorkerSettings
"""

from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings


async def ping(ctx: dict[str, Any]) -> str:
    """Kuyruğun uçtan uca çalıştığını doğrulayan iş.

    `/health` ucunun kuyruk tarafındaki karşılığıdır: ürün mantığı içermez,
    yalnızca altyapının ayakta olduğunu gösterir. ARQ en az bir kayıtlı iş
    istediği için aynı zamanda işçinin açılabilmesini sağlar.
    """
    return "pong"


def build_redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings(host=settings.redis_host, port=settings.redis_port)


class WorkerSettings:
    """`arq` komutunun okuduğu yapılandırma sınıfı."""

    functions = [ping]
    redis_settings = build_redis_settings()
