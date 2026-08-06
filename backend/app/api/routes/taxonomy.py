"""Sektör ve etiket havuzu uçları (şartname Bölüm 6).

Havuzun **içeriği** Bölüm 12'de açık karar olarak duruyordu; başlangıç seti
`0002` migration'ı ile yükleniyor ve buradan sunuluyor.

Etiketlerin tek havuzdan gelmesi kritik: "ne sunuyorum" ve "ne arıyorum" aynı
listeden seçilir, yoksa sinerji hesabı karşılaştırma yapamaz (Bölüm 6, 9.3).
"""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.models import Sector, TagCategory
from app.schemas.taxonomy import SectorResponse, TagCategoryResponse

router = APIRouter(tags=["taksonomi"])


@router.get("/sectors", summary="Sektör listesi")
async def list_sectors(session: SessionDep, user: CurrentUser) -> list[SectorResponse]:
    result = await session.execute(select(Sector).order_by(Sector.sort_order, Sector.name))
    return [SectorResponse.model_validate(sector) for sector in result.scalars()]


@router.get("/tag-categories", summary="Etiket havuzu")
async def list_tag_categories(session: SessionDep, user: CurrentUser) -> list[TagCategoryResponse]:
    """Kategoriler ve altlarındaki etiketler, tek istekte."""
    result = await session.execute(
        select(TagCategory)
        .options(selectinload(TagCategory.tags))
        .order_by(TagCategory.sort_order, TagCategory.name)
    )
    categories = list(result.scalars())

    for category in categories:
        category.tags.sort(key=lambda tag: (tag.sort_order, tag.name))

    return [TagCategoryResponse.model_validate(category) for category in categories]
