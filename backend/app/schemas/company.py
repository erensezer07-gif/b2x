"""Şirket istek ve yanıt modelleri (şartname Bölüm 6)."""

from pydantic import BaseModel, ConfigDict, Field


class CompanyResponse(BaseModel):
    """Kullanıcıya gösterilen şirket.

    `normalized_name` dışarı verilmez: o bir iç karşılaştırma anahtarı, kullanıcı
    kendi yazdığı adı görmeli.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CompanyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
