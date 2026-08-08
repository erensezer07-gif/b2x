"""Salon düzeni uçları (şartname M5).

İki mod var. **Otomatik:** sistem masaları oluşturur ve 1'den başlayarak
numaralandırır, görsel kroki yoktur, katılımcıya sadece masa numarası
gösterilir. **Manuel:** organizatör salonu ızgara üzerinde kurar; masalar ve
alan blokları hücrelere oturur.

Izgara kuralları — çakışma, sınır, satır satır dizme — `app.services.layout`
içinde. Uçlar yalnızca kilidi kontrol eder, kuralı çağırır, hatayı Türkçeye
çevirir.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import OwnedEvent, SessionDep
from app.models import (
    Assignment,
    Layout,
    LayoutArea,
    LayoutMode,
    Plan,
    Table,
    TableKind,
)
from app.schemas.layout import (
    AreaCreateRequest,
    AreaUpdateRequest,
    AutoLayoutRequest,
    LayoutResponse,
    ManualLayoutRequest,
    TableCreateRequest,
    TableUpdateRequest,
)
from app.services.event import build_layout_response
from app.services.layout import (
    Placement,
    area_placement,
    find_cell_conflict,
    items_outside_grid,
    plan_row_placements,
)

router = APIRouter(prefix="/events/{event_id}", tags=["salon duzeni"])


async def _load_layout(session: SessionDep, event_id: int) -> Layout | None:
    result = await session.execute(
        select(Layout)
        .where(Layout.event_id == event_id)
        .options(selectinload(Layout.tables), selectinload(Layout.areas))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _has_assignments(session: SessionDep, event_id: int) -> bool:
    """Bu etkinlik için üretilmiş bir plan var mı.

    Varsa masalar değiştirilemez: atamalar masa kimliğine bağlı, masaları silmek
    planı bozardı.
    """
    result = await session.execute(
        select(func.count())
        .select_from(Assignment)
        .join(Plan, Plan.id == Assignment.plan_id)
        .where(Plan.event_id == event_id)
    )
    return (result.scalar_one() or 0) > 0


async def _ensure_editable(session: SessionDep, event: OwnedEvent) -> None:
    if event.status is not EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Kayıtları açılmış veya tamamlanmış bir etkinliğin salon düzeni değiştirilemez.",
        )
    if await _has_assignments(session, event.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu etkinlik için plan üretilmiş; salon düzeni artık değiştirilemez.",
        )


async def _require_layout(session: SessionDep, event_id: int) -> Layout:
    layout = await _load_layout(session, event_id)
    if layout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu etkinlik için henüz salon düzeni kurulmadı.",
        )
    return layout


async def _require_manual_layout(session: SessionDep, event_id: int) -> Layout:
    """Manuel moda özel uçların kapısı.

    Otomatik modda ızgara yok: konum vermek şemadaki `grid_matches_mode`
    kısıtına ters düşerdi ve zaten anlamsız — o modda görsel kroki yok.
    """
    layout = await _require_layout(session, event_id)
    if layout.mode is not LayoutMode.MANUAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu işlem yalnızca manuel salon düzeninde yapılabilir.",
        )
    return layout


def _reject_conflict(
    layout: Layout,
    placement: Placement,
    *,
    ignore_table_id: int | None = None,
    ignore_area_id: int | None = None,
) -> None:
    """Hücre doluysa 409 fırlatır.

    *"İki masa aynı hücreye konamaz."* *"Alan blokları da ızgaraya oturur ve
    masalarla aynı hücreyi paylaşamaz."*
    """
    grid_width = layout.grid_width or 0
    grid_height = layout.grid_height or 0
    if not placement.fits_in(grid_width, grid_height):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu konum ızgaranın dışında. Izgara {grid_width}×{grid_height} hücre.",
        )

    conflict = find_cell_conflict(
        layout,
        placement,
        ignore_table_id=ignore_table_id,
        ignore_area_id=ignore_area_id,
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu hücre dolu: {conflict}.",
        )


def _next_table_number(layout: Layout) -> int:
    """*"Numara: varsayılan otomatik artan, ama elle değiştirilebilir."*"""
    return max((table.number for table in layout.tables), default=0) + 1


def _find_table(layout: Layout, table_id: int) -> Table:
    table = next((item for item in layout.tables if item.id == table_id), None)
    if table is None:
        # Başka bir etkinliğin masası da buraya düşer: kullanıcı yalnızca kendi
        # düzenindeki masaları görebilmeli.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Masa bulunamadı.")
    return table


def _find_area(layout: Layout, area_id: int) -> LayoutArea:
    area = next((item for item in layout.areas if item.id == area_id), None)
    if area is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alan bloğu bulunamadı.")
    return area


async def _commit_table(session: SessionDep) -> None:
    """Masa yazımını tamamlar; numara çakışmasını 409'a çevirir.

    Hücre çakışması buraya gelmeden yakalanıyor (`_reject_conflict`). Veritabanı
    yine de `uq_tables_layout_cell` ile bekçilik ediyor; yarış durumunda mesaj
    genel kalır ama veri bozulmaz.
    """
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        # Katılımcı masasını numarayla bulduğu için bu kritik (M5). Kapasite
        # alanlarının tiple tutarsızlığı da buraya düşer.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu numara başka bir masada kullanılıyor veya "
            "kapasite bilgisi masa tipiyle uyuşmuyor.",
        ) from error


# --- Düzen -------------------------------------------------------------------


@router.get("/layout", summary="Salon düzeni")
async def read_layout(event: OwnedEvent, session: SessionDep) -> LayoutResponse:
    return build_layout_response(await _require_layout(session, event.id))


@router.put("/layout/auto", summary="Otomatik salon düzeni kur")
async def create_auto_layout(
    payload: AutoLayoutRequest, event: OwnedEvent, session: SessionDep
) -> LayoutResponse:
    """Masaları oluşturur ve 1'den başlayarak numaralandırır (M5).

    `PUT` bilinçli: çağrı mevcut düzenin **yerine geçiyor**, üstüne eklemiyor.
    Organizatör masa sayısını değiştirdiğinde eski masalar silinip yenileri
    kuruluyor — aksi hâlde her denemede masa birikirdi.

    Plan üretilmişse reddediliyor: atamalar masa kimliğine bağlı.
    """
    await _ensure_editable(session, event)

    layout = await _load_layout(session, event.id)
    if layout is None:
        # Otomatik modda ızgara yok; şemadaki CHECK kısıtı da grid alanlarının
        # boş olmasını zorluyor (Aşama 1).
        layout = Layout(event_id=event.id, mode=LayoutMode.AUTO)
        session.add(layout)
        await session.flush()
    else:
        layout.mode = LayoutMode.AUTO
        # Manuel moddan dönülüyorsa ızgara temizlenmeli: `grid_matches_mode`
        # otomatik modda bu alanların boş olmasını şart koşuyor. Alan blokları
        # da gidiyor — otomatik modda görsel kroki yok, yerleri kalmaz.
        layout.grid_width = None
        layout.grid_height = None
        for area in list(layout.areas):
            await session.delete(area)
        for table in list(layout.tables):
            await session.delete(table)
        await session.flush()

    seated = payload.kind == TableKind.SEATED
    for number in range(1, payload.table_count + 1):
        session.add(
            Table(
                layout_id=layout.id,
                number=number,
                kind=payload.kind,
                seat_count=payload.seat_count if seated else None,
                min_people=None if seated else payload.min_people,
                max_people=None if seated else payload.max_people,
            )
        )

    await session.commit()
    return build_layout_response(await _require_layout(session, event.id))


@router.put("/layout/manual", summary="Manuel salon düzenine geç")
async def create_manual_layout(
    payload: ManualLayoutRequest, event: OwnedEvent, session: SessionDep
) -> LayoutResponse:
    """Izgarayı kurar ve modu manuele çevirir (M5).

    *"Tuval: boş bir ızgara. Boyutu ayarlanabilir (kaça kaç hücre)."*

    Otomatik modda kurulmuş masalar **korunuyor**: numara ve kapasite aynı
    kalıyor, yalnızca ızgara konumu atanıyor. Organizatör 25 masayı yeniden
    kurmasın, sürükleyerek düzeltsin.

    Aynı uç ızgarayı yeniden boyutlandırmak için de çağrılıyor. Küçültme
    dışarıda öğe bırakacaksa reddediliyor — sessizce silmek organizatörün
    emeğini yok etmek olurdu.
    """
    await _ensure_editable(session, event)

    layout = await _load_layout(session, event.id)
    if layout is None:
        layout = Layout(
            event_id=event.id,
            mode=LayoutMode.MANUAL,
            grid_width=payload.grid_width,
            grid_height=payload.grid_height,
        )
        session.add(layout)
        await session.commit()
        return build_layout_response(await _require_layout(session, event.id))

    outside = items_outside_grid(layout, payload.grid_width, payload.grid_height)
    if outside:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu ızgaraya sığmayan öğeler var: {', '.join(outside)}. Önce onları taşıyın.",
        )

    # Önce planlanıyor, sonra uygulanıyor: yer yetmezse düzen yarı taşınmış
    # hâlde kalmasın.
    placements = plan_row_placements(layout, payload.grid_width, payload.grid_height)
    if placements is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{len(layout.tables)} masa {payload.grid_width}×{payload.grid_height} "
            "hücrelik ızgaraya sığmıyor. Daha büyük bir ızgara seçin.",
        )

    layout.mode = LayoutMode.MANUAL
    layout.grid_width = payload.grid_width
    layout.grid_height = payload.grid_height
    for table, (grid_x, grid_y) in placements:
        table.grid_x = grid_x
        table.grid_y = grid_y

    await session.commit()
    return build_layout_response(await _require_layout(session, event.id))


# --- Masalar -----------------------------------------------------------------


@router.post("/tables", status_code=status.HTTP_201_CREATED, summary="Tuvale masa koy")
async def create_table(
    payload: TableCreateRequest, event: OwnedEvent, session: SessionDep
) -> LayoutResponse:
    """*"Araç çubuğundan tip seçilir, tuvale dokunulur, masa oraya konur."*"""
    await _ensure_editable(session, event)
    layout = await _require_manual_layout(session, event.id)

    _reject_conflict(layout, Placement(payload.grid_x, payload.grid_y))

    seated = payload.kind == TableKind.SEATED
    session.add(
        Table(
            layout_id=layout.id,
            number=payload.number or _next_table_number(layout),
            kind=payload.kind,
            seat_count=payload.seat_count if seated else None,
            min_people=None if seated else payload.min_people,
            max_people=None if seated else payload.max_people,
            grid_x=payload.grid_x,
            grid_y=payload.grid_y,
            label=payload.label,
        )
    )

    await _commit_table(session)
    return build_layout_response(await _require_layout(session, event.id))


@router.patch("/tables/{table_id}", summary="Masayı düzenle")
async def update_table(
    table_id: int,
    payload: TableUpdateRequest,
    event: OwnedEvent,
    session: SessionDep,
) -> LayoutResponse:
    """Tek masayı düzenler (M5).

    *"Masalar farklı sandalye sayısına sahip olabilmeli — organizatör sonradan
    tek tek düzenleyebilir."* Sürükle-bırak da buraya geliyor: konum
    değiştiğinde masa yeni hücreye taşınıyor.
    """
    layout = await _require_layout(session, event.id)
    table = _find_table(layout, table_id)
    await _ensure_editable(session, event)

    changes = payload.model_dump(exclude_unset=True)

    if "grid_x" in changes:
        if layout.mode is not LayoutMode.MANUAL:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Izgara konumu yalnızca manuel salon düzeninde verilebilir.",
            )
        if changes["grid_x"] is None:
            # Konumu boşaltmak masayı krokiden düşürürdü; manuel modda her
            # masanın bir yeri var. Kaldırmak isteyen masayı siler.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Manuel düzende masanın ızgara konumu boş bırakılamaz.",
            )
        _reject_conflict(
            layout,
            Placement(changes["grid_x"], changes["grid_y"]),
            ignore_table_id=table.id,
        )

    for field, value in changes.items():
        setattr(table, field, value)

    await _commit_table(session)
    return build_layout_response(await _require_layout(session, event.id))


@router.delete("/tables/{table_id}", summary="Masayı sil")
async def delete_table(table_id: int, event: OwnedEvent, session: SessionDep) -> LayoutResponse:
    layout = await _require_layout(session, event.id)
    table = _find_table(layout, table_id)
    await _ensure_editable(session, event)

    await session.delete(table)
    await session.commit()
    return build_layout_response(await _require_layout(session, event.id))


# --- Alan blokları -----------------------------------------------------------


@router.post("/areas", status_code=status.HTTP_201_CREATED, summary="Alan bloğu ekle")
async def create_area(
    payload: AreaCreateRequest, event: OwnedEvent, session: SessionDep
) -> LayoutResponse:
    """*"Sahne, giriş, büfe gibi işaretler konabilir. Sadece metin etiketi ve
    konum. Katılımcının salonda yön bulmasına yarar."*

    Eşleştirmeye hiç girmez (Bölüm 6); kapasiteye de sayılmaz.
    """
    await _ensure_editable(session, event)
    layout = await _require_manual_layout(session, event.id)

    _reject_conflict(
        layout, Placement(payload.grid_x, payload.grid_y, payload.width, payload.height)
    )

    session.add(
        LayoutArea(
            layout_id=layout.id,
            label=payload.label,
            grid_x=payload.grid_x,
            grid_y=payload.grid_y,
            width=payload.width,
            height=payload.height,
        )
    )
    await session.commit()
    return build_layout_response(await _require_layout(session, event.id))


@router.patch("/areas/{area_id}", summary="Alan bloğunu düzenle")
async def update_area(
    area_id: int,
    payload: AreaUpdateRequest,
    event: OwnedEvent,
    session: SessionDep,
) -> LayoutResponse:
    layout = await _require_layout(session, event.id)
    area = _find_area(layout, area_id)
    await _ensure_editable(session, event)

    changes = payload.model_dump(exclude_unset=True)
    current = area_placement(area)
    moved = Placement(
        changes.get("grid_x", current.x),
        changes.get("grid_y", current.y),
        changes.get("width", current.width),
        changes.get("height", current.height),
    )
    if moved != current:
        _reject_conflict(layout, moved, ignore_area_id=area.id)

    for field, value in changes.items():
        setattr(area, field, value)

    await session.commit()
    return build_layout_response(await _require_layout(session, event.id))


@router.delete("/areas/{area_id}", summary="Alan bloğunu sil")
async def delete_area(area_id: int, event: OwnedEvent, session: SessionDep) -> LayoutResponse:
    layout = await _require_layout(session, event.id)
    area = _find_area(layout, area_id)
    await _ensure_editable(session, event)

    await session.delete(area)
    await session.commit()
    return build_layout_response(await _require_layout(session, event.id))
