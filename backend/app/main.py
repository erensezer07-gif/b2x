"""FastAPI uygulaması.

Çalıştırma (Windows, geliştirme):  uvicorn app.main:app --reload
Konteynerde:                       uvicorn app.main:app --host ... --port ...
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    auth,
    company,
    event,
    health,
    layout,
    meeting_request,
    participant_plan,
    plan,
    profile,
    registration,
    taxonomy,
)
from app.config import get_settings
from app.db import dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="B2X API",
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    origins = settings.cors_origin_list
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            # Jeton Authorization başlığıyla taşınır, çerez kullanılmaz.
            # allow_credentials=True olsaydı CORS_ORIGINS="*" geçersiz olurdu.
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(profile.router)
    application.include_router(company.router)
    application.include_router(taxonomy.router)
    # Keşif ucu etkinlik ucundan **önce** kaydediliyor: `/events/{event_id}`
    # daha önce gelseydi `/events/discover` ona eşleşir ve "discover" bir
    # kimlik sanılıp 422 dönerdi.
    application.include_router(registration.router)
    application.include_router(event.router)
    application.include_router(layout.router)
    application.include_router(plan.router)
    application.include_router(participant_plan.router)
    application.include_router(meeting_request.router)

    _mount_local_storage(application, settings.storage_backend, settings.storage_local_path)
    return application


def _mount_local_storage(application: FastAPI, backend: str, local_path: str) -> None:
    """Yerel diske yazılan dosyaları sunar (MVP).

    Yalnızca yerel depolamada gerekli: bulut depolamaya geçildiğinde dosyaları
    sağlayıcı sunar ve bu bağlama düşer (Bölüm 3).

    Klasör yoksa oluşturuluyor — ilk fotoğraf yüklenmeden önce de uygulama
    açılabilmeli.
    """
    if backend != "local":
        return

    root = Path(local_path)
    root.mkdir(parents=True, exist_ok=True)
    application.mount("/files", StaticFiles(directory=root), name="files")


app = create_app()
