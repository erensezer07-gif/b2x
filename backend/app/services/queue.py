"""İş kuyruğu arayüzü (şartname 5.4).

Uçlar somut kuyruğu değil bu sözleşmeyi görüyor. Sebebi depolama arayüzüyle
aynı (`app/services/storage.py`): testler gerçek altyapıya dokunmamalı.
Bağımlılık olarak verilmeseydi her uç testi Redis'e gerçek bir iş atardı —
plan satırı testin sonunda geri alındığı için işçi onu hiç bulamaz, kuyruk
hayalet işlerle dolardı.

CLAUDE.md'deki tuzak: modül seviyesindeki fonksiyonu yamalamak işe yaramıyor,
uçlar `from ... import x` ile fonksiyonu kendi ad alanlarına kopyalıyor.
FastAPI bağımlılığı + `dependency_overrides` doğru yol.
"""

import logging
from abc import ABC, abstractmethod
from functools import lru_cache

from arq import create_pool

from app.worker import build_redis_settings

logger = logging.getLogger(__name__)


class JobQueue(ABC):
    """Arka plan işi kuyruğa atmanın sözleşmesi."""

    @abstractmethod
    async def enqueue(self, name: str, *args: object) -> str | None:
        """İşi kuyruğa atar ve kuyruk kimliğini döner.

        Kuyruğa ulaşılamıyorsa `None` döner, **hata fırlatmaz**: plan satırı
        zaten yazıldı ve `queued` durumunda. Organizatör ekranda "kuyrukta"
        görür, işçi ayağa kalkınca iş işlenir. Burada patlamak yeni bir plan
        versiyonunu boşuna harcardı.
        """


class RedisJobQueue(JobQueue):
    """ARQ üzerinden Redis kuyruğu — üretimdeki uygulama."""

    async def enqueue(self, name: str, *args: object) -> str | None:
        try:
            pool = await create_pool(build_redis_settings())
            try:
                job = await pool.enqueue_job(name, *args)
            finally:
                await pool.aclose()
            return job.job_id if job is not None else None
        except Exception:
            logger.exception("İş kuyruğa atılamadı: %s%r", name, args)
            return None


@lru_cache
def get_job_queue() -> JobQueue:
    """FastAPI bağımlılığı. Testler `dependency_overrides` ile değiştirir."""
    return RedisJobQueue()
