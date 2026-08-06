"""Sektör ve etiket havuzu yanıt modelleri (şartname Bölüm 6).

*"Kullanıcı kategorileri gezerek seçer, serbest metin yazamaz."* Bu yüzden
listeler sunucudan gelir; istemci kendi listesini tutmaz.
"""

from pydantic import BaseModel, ConfigDict


class SectorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TagCategoryResponse(BaseModel):
    """Kategori ve altındaki etiketler.

    Etiketler kategoriyle birlikte dönüyor: seçici ekranı kategorileri gezerek
    çalışıyor, her kategori için ayrı istek atmak gereksiz gidiş geliş olurdu.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tags: list[TagResponse]
