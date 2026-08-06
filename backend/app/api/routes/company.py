"""Şirket uçları (şartname Bölüm 6).

*"Kullanıcı yazarken mevcut şirketler önerilir, varsa seçer, yoksa yeni
oluşturulur. Karşılaştırma serbest metinle değil, şirket kimliğiyle yapılır."*

Kimlik doğrulaması gerekiyor: şirket listesi katılımcı verisidir, açık uçtan
taranabilir olmamalı.
"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.company import CompanyCreateRequest, CompanyResponse
from app.services.company import find_or_create_company, search_companies

router = APIRouter(prefix="/companies", tags=["sirket"])


@router.get("", summary="Şirket ara")
async def search(
    session: SessionDep,
    user: CurrentUser,
    q: Annotated[str, Query(description="aranan şirket adı", max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[CompanyResponse]:
    """Yazarken öneri listesi.

    Arama normalleştirilmiş ad üzerinden yapılır: "abc yazilim" yazınca
    "ABC Yazılım A.Ş." de çıkar.
    """
    companies = await search_companies(session, q, limit=limit)
    return [CompanyResponse.model_validate(company) for company in companies]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Şirket ekle veya bul")
async def create(
    payload: CompanyCreateRequest,
    session: SessionDep,
    user: CurrentUser,
) -> CompanyResponse:
    """Şirketi bulur, yoksa oluşturur.

    Bölüm 10: *"aynı şirket iki kez oluşturulmuyor."* Bu yüzden uç her zaman 201
    döner ama yeni kayıt oluşturmayabilir — çağıran için ikisi arasında fark yok,
    her iki durumda da kullanılacak şirket kimliği geliyor.
    """
    company = await find_or_create_company(session, payload.name)
    await session.commit()
    return CompanyResponse.model_validate(company)
