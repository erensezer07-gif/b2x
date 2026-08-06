"""ARQ arka plan işçisi.

Eşleştirme motoru HTTP isteği içinde çalıştırılamaz (şartname 5.4) — istek zaman
aşımına uğrar. Uzun süren işler bu işçiye kuyruklanır.

Çalıştırma:  arq app.worker.WorkerSettings

**Bu işçi çalışmıyorsa eşleştirme kuyrukta bekler.** Plan `queued` durumunda
kalır, hata vermez. Geliştirirken en sık atlanan adım bu.
"""

from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings
from app.db import get_session_factory
from app.services.plan_runner import execute_plan

# Motor 200 kişilik bir etkinlikte saniyeler sürüyor (9.9). ARQ'nun
# varsayılan zaman aşımı bunun için kısa; ölçekli bir etkinlikte iş yarıda
# kesilirdi.
MATCHING_JOB_TIMEOUT_SECONDS = 600


async def ping(ctx: dict[str, Any]) -> str:
    """Kuyruğun uçtan uca çalıştığını doğrulayan iş.

    `/health` ucunun kuyruk tarafındaki karşılığıdır: ürün mantığı içermez,
    yalnızca altyapının ayakta olduğunu gösterir.
    """
    return "pong"


async def run_matching_job(ctx: dict[str, Any], plan_id: int) -> None:
    """Eşleştirmeyi çalıştırır (5.4).

    Kendi oturumunu açıyor: işçi HTTP isteği bağlamında değil, `SessionDep`
    yok. Durum takibi ve hata kaydı `execute_plan` içinde.
    """
    async with get_session_factory()() as session:
        await execute_plan(session, plan_id)


def build_redis_settings() -> RedisSettings:
    settings = get_settings()
    return RedisSettings(host=settings.redis_host, port=settings.redis_port)


class WorkerSettings:
    """`arq` komutunun okuduğu yapılandırma sınıfı."""

    functions = [ping, run_matching_job]
    redis_settings = build_redis_settings()
    job_timeout = MATCHING_JOB_TIMEOUT_SECONDS
