"""Salon düzeni istek ve yanıt modelleri (şartname M5)."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import LayoutMode, TableKind
from app.services.layout import (
    DEFAULT_GRID_HEIGHT,
    DEFAULT_GRID_WIDTH,
    MAX_GRID_SIDE,
    MIN_GRID_SIDE,
)


class _TableCapacity(BaseModel):
    """Masa tipi ve ona bağlı kapasite alanları.

    Hem otomatik düzende hem tek masa eklerken aynı kural geçerli; kontrol tek
    yerde dursun diye ortak taban.
    """

    kind: TableKind

    # Oturmalı masada zorunlu, ayaklıda boş.
    seat_count: int | None = Field(default=None, ge=2, le=50)

    # Ayaklı masada zorunlu, oturmalıda boş.
    min_people: int | None = Field(default=None, ge=2, le=50)
    max_people: int | None = Field(default=None, ge=2, le=50)

    @model_validator(mode="after")
    def check_capacity_matches_kind(self) -> Self:
        """Masa tipi ile kapasite alanları tutarlı olmalı.

        Aynı kural veritabanında da CHECK kısıtı olarak var (Aşama 1); buradaki
        kontrol kullanıcıya anlaşılır bir mesaj vermek için — kısıt ihlali
        500'e dönüşürdü.
        """
        if self.kind is TableKind.SEATED:
            if self.seat_count is None:
                raise ValueError("Oturmalı masada sandalye sayısı gerekli.")
            if self.min_people is not None or self.max_people is not None:
                raise ValueError("Oturmalı masada kişi aralığı verilmez.")
        else:
            if self.min_people is None or self.max_people is None:
                raise ValueError("Ayaklı masada alt ve üst kişi sınırı gerekli.")
            if self.seat_count is not None:
                raise ValueError("Ayaklı masada sandalye sayısı verilmez.")
            if self.max_people < self.min_people:
                raise ValueError("Üst sınır alt sınırdan küçük olamaz.")
        return self


class AutoLayoutRequest(_TableCapacity):
    """Otomatik mod (M5).

    *"Organizatör sadece şunları girer: masa tipi, masa sayısı, oturmalı ise
    sandalye sayısı, ayaklı ise alt ve üst kişi sınırı."*
    """

    table_count: int = Field(ge=1, le=500)


class ManualLayoutRequest(BaseModel):
    """Manuel mod (M5).

    *"Tuval: boş bir ızgara. Boyutu ayarlanabilir (kaça kaç hücre)."*

    Boyut verilmezse varsayılan ızgara kuruluyor; organizatör önce salonu
    kursun, ölçüyü sonra ayarlasın.
    """

    grid_width: int = Field(default=DEFAULT_GRID_WIDTH, ge=MIN_GRID_SIDE, le=MAX_GRID_SIDE)
    grid_height: int = Field(default=DEFAULT_GRID_HEIGHT, ge=MIN_GRID_SIDE, le=MAX_GRID_SIDE)


class TableCreateRequest(_TableCapacity):
    """Tuvale masa koyma (M5).

    *"Araç çubuğundan tip seçilir, tuvale dokunulur, masa oraya konur."*

    Numara verilmezse sıradaki boş numara atanıyor: *"varsayılan otomatik
    artan, ama elle değiştirilebilir."*
    """

    grid_x: int = Field(ge=0, lt=MAX_GRID_SIDE)
    grid_y: int = Field(ge=0, lt=MAX_GRID_SIDE)
    number: int | None = Field(default=None, ge=1)
    label: str | None = Field(default=None, max_length=100)


class TableUpdateRequest(BaseModel):
    """Tek masayı düzenleme (M5).

    *"Masaya dokununca panel açılır. Değiştirilebilenler: numara, sandalye
    sayısı, etiket, silme."* Konum ayrıca burada: sürükle-bırak da bu ucu
    çağırıyor.
    """

    number: int | None = Field(default=None, ge=1)
    seat_count: int | None = Field(default=None, ge=2, le=50)
    min_people: int | None = Field(default=None, ge=2, le=50)
    max_people: int | None = Field(default=None, ge=2, le=50)
    label: str | None = Field(default=None, max_length=100)
    grid_x: int | None = Field(default=None, ge=0, lt=MAX_GRID_SIDE)
    grid_y: int | None = Field(default=None, ge=0, lt=MAX_GRID_SIDE)

    @model_validator(mode="after")
    def check_position_is_complete(self) -> Self:
        """Konumun iki ekseni birlikte verilir.

        Tek eksen gelirse masa yarı taşınmış olurdu; ızgara konumu bölünmez.
        """
        if (self.grid_x is None) != (self.grid_y is None):
            raise ValueError("Izgara konumu için hem yatay hem dikey değer gerekli.")
        return self


class AreaCreateRequest(BaseModel):
    """Alan bloğu (M5).

    *"Sahne, giriş, büfe gibi işaretler konabilir. Sadece metin etiketi ve
    konum."* Tip alanı yok — hazır etiketler arayüzün önerisi, veri değil.
    """

    label: str = Field(min_length=1, max_length=100)
    grid_x: int = Field(ge=0, lt=MAX_GRID_SIDE)
    grid_y: int = Field(ge=0, lt=MAX_GRID_SIDE)
    width: int = Field(default=1, ge=1, le=MAX_GRID_SIDE)
    height: int = Field(default=1, ge=1, le=MAX_GRID_SIDE)


class AreaUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    grid_x: int | None = Field(default=None, ge=0, lt=MAX_GRID_SIDE)
    grid_y: int | None = Field(default=None, ge=0, lt=MAX_GRID_SIDE)
    width: int | None = Field(default=None, ge=1, le=MAX_GRID_SIDE)
    height: int | None = Field(default=None, ge=1, le=MAX_GRID_SIDE)

    @model_validator(mode="after")
    def check_position_is_complete(self) -> Self:
        if (self.grid_x is None) != (self.grid_y is None):
            raise ValueError("Izgara konumu için hem yatay hem dikey değer gerekli.")
        return self


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: int
    kind: TableKind
    seat_count: int | None
    min_people: int | None
    max_people: int | None
    label: str | None

    # Yalnızca manuel modda dolu; otomatik modda görsel kroki yok (M5).
    grid_x: int | None
    grid_y: int | None

    @property
    def capacity(self) -> int:
        return self.seat_count or self.max_people or 0


class AreaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    grid_x: int
    grid_y: int
    width: int
    height: int


class LayoutResponse(BaseModel):
    """Düzen, masaları ve alan blokları.

    Otomatik modda ızgara boyutu boş, alan bloğu listesi boş: o modda görsel
    kroki yok (M5), katılımcıya yalnızca masa numarası gösteriliyor.
    """

    id: int
    mode: LayoutMode
    grid_width: int | None
    grid_height: int | None
    tables: list[TableResponse]
    areas: list[AreaResponse]
    seating_capacity: int
