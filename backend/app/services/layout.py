"""Manuel salon düzeninin ızgara kuralları (şartname M5).

*"Masalar serbestçe sürüklenir ama bırakıldığında en yakın ızgara noktasına
oturur. İki masa aynı hücreye konamaz."* Oturma hesabı istemcide yapılıyor —
sürükleme oradan görünüyor; buradaki kural sonucu doğruluyor.

Çakışma iki ayrı kaynaktan korunuyor:

* **Masa ↔ masa** — veritabanında `uq_tables_layout_cell` koşullu benzersiz
  indeksi var (Aşama 1). Buradaki kontrol onun yerine geçmiyor, **önüne**
  geçiyor: aynı `IntegrityError` numara çakışmasından da geliyor, ikisi ayırt
  edilemeden organizatöre yanlış mesaj giderdi.
* **Masa ↔ alan bloğu** — şemada hiç ifade edilemiyor, iki ayrı tabloyu
  kapsıyor. Aşama 1'de bu kural buraya ertelenmişti; tek yeri burası.

Bu modül piksel bilmez. Hücrenin kaç piksel çizileceği çizim kararıdır,
istemcide durur.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from app.models import Layout, LayoutArea, Table

# Varsayılan ızgara: 24×16 hücre. Salonlar genelde dikdörtgen, yatay oran
# gerçek bir fuar alanına benziyor; 384 hücre şartnamedeki 50 masalık ölçeğe
# (9.9) bol geliyor.
DEFAULT_GRID_WIDTH = 24
DEFAULT_GRID_HEIGHT = 16

# Alt sınır bir masayla bir alan bloğunun yan yana sığacağı en küçük tuval.
# Üst sınır 3600 hücre — bunun ötesi salon değil, kaybolunacak bir tuval.
MIN_GRID_SIDE = 2
MAX_GRID_SIDE = 60


@dataclass(frozen=True)
class Placement:
    """Izgarada bir dikdörtgen.

    Masa tek hücre, alan bloğu `width × height`. İkisi de aynı tipe indiriliyor
    ki çakışma kontrolü tek yerde yazılsın.
    """

    x: int
    y: int
    width: int = 1
    height: int = 1

    def overlaps(self, other: "Placement") -> bool:
        return (
            self.x < other.x + other.width
            and other.x < self.x + self.width
            and self.y < other.y + other.height
            and other.y < self.y + self.height
        )

    def fits_in(self, grid_width: int, grid_height: int) -> bool:
        return (
            self.x >= 0
            and self.y >= 0
            and self.x + self.width <= grid_width
            and self.y + self.height <= grid_height
        )

    def cells(self) -> Iterator[tuple[int, int]]:
        for offset_y in range(self.height):
            for offset_x in range(self.width):
                yield self.x + offset_x, self.y + offset_y


def table_placement(table: Table) -> Placement | None:
    """Masanın ızgaradaki yeri; otomatik modda konum yok."""
    if table.grid_x is None or table.grid_y is None:
        return None
    return Placement(table.grid_x, table.grid_y)


def area_placement(area: LayoutArea) -> Placement:
    return Placement(area.grid_x, area.grid_y, area.width, area.height)


def describe_table(table: Table) -> str:
    return f"{table.number} numaralı masa"


def describe_area(area: LayoutArea) -> str:
    return f"“{area.label}” alanı"


def find_cell_conflict(
    layout: Layout,
    placement: Placement,
    *,
    ignore_table_id: int | None = None,
    ignore_area_id: int | None = None,
) -> str | None:
    """Çakışılan öğenin adını döner; hücreler boşsa `None`.

    Ad doğrudan hata mesajına giriyor: organizatör hangi öğeyle çakıştığını
    görmeden düzeltemez. Taşınan öğenin kendisi `ignore_*` ile dışarıda
    bırakılıyor — yoksa masa kendi hücresine geri konamazdı.
    """
    for table in layout.tables:
        if table.id == ignore_table_id:
            continue
        other = table_placement(table)
        if other is not None and placement.overlaps(other):
            return describe_table(table)

    for area in layout.areas:
        if area.id == ignore_area_id:
            continue
        if placement.overlaps(area_placement(area)):
            return describe_area(area)

    return None


def items_outside_grid(layout: Layout, grid_width: int, grid_height: int) -> list[str]:
    """Verilen ızgaraya sığmayan öğelerin adları.

    Izgara küçültülürken kullanılıyor: dışarıda kalan varsa istek reddediliyor.
    Sessizce silmek organizatörün emeğini yok etmek olurdu.
    """
    outside = [
        describe_table(table)
        for table in sorted(layout.tables, key=lambda item: item.number)
        if (placement := table_placement(table)) is not None
        and not placement.fits_in(grid_width, grid_height)
    ]
    outside += [
        describe_area(area)
        for area in layout.areas
        if not area_placement(area).fits_in(grid_width, grid_height)
    ]
    return outside


def occupied_cells(layout: Layout) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for table in layout.tables:
        placement = table_placement(table)
        if placement is not None:
            cells.update(placement.cells())
    for area in layout.areas:
        cells.update(area_placement(area).cells())
    return cells


def plan_row_placements(
    layout: Layout, grid_width: int, grid_height: int
) -> list[tuple[Table, tuple[int, int]]] | None:
    """Konumu olmayan masalara satır satır yer bulur.

    Otomatik moddan manuel moda geçerken bütün masalar buradan geçiyor:
    korunuyorlar, numara ve kapasite aynı kalıyor, yalnızca konum atanıyor.
    Organizatör 25 masayı yeniden kurmasın. Izgara yeniden boyutlandırılırken
    yerleşik masalara dokunulmuyor — onların konumu zaten var.

    Yer yetmezse `None` döner. Uygulamıyor, **planlıyor**: çağıran yer
    yetmediğini öğrendiğinde yarı taşınmış bir düzenle kalmasın.
    """
    unplaced = sorted(
        (table for table in layout.tables if table_placement(table) is None),
        key=lambda table: table.number,
    )
    if not unplaced:
        return []

    taken = occupied_cells(layout)
    free = ((x, y) for y in range(grid_height) for x in range(grid_width) if (x, y) not in taken)
    placements: list[tuple[Table, tuple[int, int]]] = []
    for table in unplaced:
        cell = next(free, None)
        if cell is None:
            return None
        placements.append((table, cell))
    return placements
