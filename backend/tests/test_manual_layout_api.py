"""Manuel salon düzeni (şartname M5, Bölüm 10).

Kabul kriterleri: *"Masa sürüklenip bırakıldığında ızgaraya oturuyor. İki masa
aynı hücreye konamıyor. Aynı numara iki kez verilemiyor. Sayfa yenilendiğinde
düzen kayıpsız geliyor."*

Izgaraya oturma istemcide oluyor — sunucu hücre koordinatı alıyor. Buradaki
testler sunucunun tuttuğu sözü doğruluyor: dolu hücre reddediliyor, ızgara
dışına çıkılamıyor, düzen olduğu gibi geri geliyor.
"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Plan, PlanStatus, Registration, User
from app.services.layout import DEFAULT_GRID_HEIGHT, DEFAULT_GRID_WIDTH
from tests.test_layout_api import create_event, seated_layout


async def manual_layout(client: AsyncClient, event_id: int, **grid) -> dict:
    response = await client.put(f"/events/{event_id}/layout/manual", json=grid)
    assert response.status_code == 200, response.text
    return response.json()


async def add_table(client: AsyncClient, event_id: int, **overrides) -> dict:
    response = await client.post(
        f"/events/{event_id}/tables",
        json={"kind": "seated", "seat_count": 6, "grid_x": 0, "grid_y": 0, **overrides},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_area(client: AsyncClient, event_id: int, **overrides) -> dict:
    response = await client.post(
        f"/events/{event_id}/areas",
        json={"label": "Sahne", "grid_x": 5, "grid_y": 5, **overrides},
    )
    assert response.status_code == 201, response.text
    return response.json()


def table_at(layout: dict, grid_x: int, grid_y: int) -> dict | None:
    return next(
        (t for t in layout["tables"] if t["grid_x"] == grid_x and t["grid_y"] == grid_y), None
    )


# --- Izgara ve mod geçişi ----------------------------------------------------


async def test_manual_mode_starts_with_the_default_grid(
    authenticated_client: AsyncClient,
) -> None:
    """*"Tuval: boş bir ızgara."* Boyut verilmezse varsayılan kuruluyor."""
    event = await create_event(authenticated_client)
    layout = await manual_layout(authenticated_client, event["id"])

    assert layout["mode"] == "manual"
    assert layout["grid_width"] == DEFAULT_GRID_WIDTH
    assert layout["grid_height"] == DEFAULT_GRID_HEIGHT
    assert layout["tables"] == []
    assert layout["areas"] == []


async def test_switching_from_auto_keeps_the_tables_and_arranges_them(
    authenticated_client: AsyncClient,
) -> None:
    """Otomatik moddaki masalar korunuyor, ızgaraya satır satır diziliyor.

    Organizatör 25 masayı yeniden kurmasın; numara ve kapasite aynı kalıyor.
    """
    event = await create_event(authenticated_client)
    await seated_layout(authenticated_client, event["id"], table_count=8, seat_count=6)

    layout = await manual_layout(authenticated_client, event["id"], grid_width=3, grid_height=4)

    assert [table["number"] for table in layout["tables"]] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert layout["seating_capacity"] == 48
    # 3 sütunlu ızgarada satır satır: (0,0) (1,0) (2,0) (0,1) ...
    positions = [(table["grid_x"], table["grid_y"]) for table in layout["tables"]]
    assert positions == [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2)]


async def test_resizing_the_grid_leaves_placed_tables_alone(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"], grid_width=10, grid_height=10)
    await add_table(authenticated_client, event["id"], grid_x=7, grid_y=3)

    layout = await manual_layout(authenticated_client, event["id"], grid_width=12, grid_height=12)

    assert (layout["tables"][0]["grid_x"], layout["tables"][0]["grid_y"]) == (7, 3)
    assert layout["grid_width"] == 12


async def test_shrinking_the_grid_is_refused_when_something_falls_outside(
    authenticated_client: AsyncClient,
) -> None:
    """Sessizce silmek organizatörün emeğini yok etmek olurdu."""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"], grid_width=10, grid_height=10)
    await add_table(authenticated_client, event["id"], number=7, grid_x=9, grid_y=9)

    response = await authenticated_client.put(
        f"/events/{event['id']}/layout/manual",
        json={"grid_width": 5, "grid_height": 5},
    )

    assert response.status_code == 409
    assert "7 numaralı masa" in response.json()["detail"]


async def test_switching_to_manual_is_refused_when_tables_do_not_fit(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    await seated_layout(authenticated_client, event["id"], table_count=8, seat_count=6)

    response = await authenticated_client.put(
        f"/events/{event['id']}/layout/manual",
        json={"grid_width": 2, "grid_height": 2},
    )

    assert response.status_code == 409
    assert "sığmıyor" in response.json()["detail"]


async def test_switching_back_to_auto_clears_the_grid_and_the_areas(
    authenticated_client: AsyncClient,
) -> None:
    """Otomatik modda ızgara yok; `grid_matches_mode` bunu şart koşuyor.

    Manuel moddan dönerken ızgara alanları temizlenmezse şema kısıtı patlar ve
    uç 500 döner.
    """
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    await add_table(authenticated_client, event["id"], grid_x=1, grid_y=1)
    await add_area(authenticated_client, event["id"])

    layout = await seated_layout(authenticated_client, event["id"], table_count=4)

    assert layout["mode"] == "auto"
    assert layout["grid_width"] is None
    assert layout["grid_height"] is None
    assert layout["areas"] == []
    assert all(table["grid_x"] is None for table in layout["tables"])


async def test_grid_size_bounds_are_enforced(authenticated_client: AsyncClient) -> None:
    event = await create_event(authenticated_client)
    response = await authenticated_client.put(
        f"/events/{event['id']}/layout/manual",
        json={"grid_width": 1, "grid_height": 400},
    )
    assert response.status_code == 422


# --- Masa yerleştirme --------------------------------------------------------


async def test_a_table_is_placed_numbered_and_moved(
    authenticated_client: AsyncClient,
) -> None:
    """*"Araç çubuğundan tip seçilir, tuvale dokunulur, masa oraya konur."*

    Numara verilmezse otomatik artıyor (M5).
    """
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])

    first = await add_table(authenticated_client, event["id"], grid_x=2, grid_y=3)
    assert first["tables"][0]["number"] == 1
    assert (first["tables"][0]["grid_x"], first["tables"][0]["grid_y"]) == (2, 3)

    second = await add_table(authenticated_client, event["id"], grid_x=4, grid_y=3)
    assert [table["number"] for table in second["tables"]] == [1, 2]

    table_id = second["tables"][0]["id"]
    moved = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{table_id}",
        json={"grid_x": 8, "grid_y": 9},
    )
    assert moved.status_code == 200
    assert table_at(moved.json(), 8, 9)["id"] == table_id


async def test_a_table_can_be_deleted(authenticated_client: AsyncClient) -> None:
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    layout = await add_table(authenticated_client, event["id"], grid_x=1, grid_y=1)

    response = await authenticated_client.delete(
        f"/events/{event['id']}/tables/{layout['tables'][0]['id']}"
    )

    assert response.status_code == 200
    assert response.json()["tables"] == []


async def test_a_table_can_stay_where_it_is(authenticated_client: AsyncClient) -> None:
    """Masa kendi hücresine geri konabilmeli — sürüklenip aynı yere bırakılırsa."""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    layout = await add_table(authenticated_client, event["id"], grid_x=3, grid_y=3)

    response = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{layout['tables'][0]['id']}",
        json={"grid_x": 3, "grid_y": 3},
    )
    assert response.status_code == 200


async def test_two_tables_cannot_share_a_cell(authenticated_client: AsyncClient) -> None:
    """*"İki masa aynı hücreye konamaz."*"""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    await add_table(authenticated_client, event["id"], grid_x=4, grid_y=4)

    placing = await authenticated_client.post(
        f"/events/{event['id']}/tables",
        json={"kind": "seated", "seat_count": 6, "grid_x": 4, "grid_y": 4},
    )
    assert placing.status_code == 409
    assert "1 numaralı masa" in placing.json()["detail"]

    second = await add_table(authenticated_client, event["id"], grid_x=5, grid_y=4)
    moving = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{table_at(second, 5, 4)['id']}",
        json={"grid_x": 4, "grid_y": 4},
    )
    assert moving.status_code == 409


async def test_a_table_cannot_leave_the_grid(authenticated_client: AsyncClient) -> None:
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"], grid_width=6, grid_height=6)

    response = await authenticated_client.post(
        f"/events/{event['id']}/tables",
        json={"kind": "seated", "seat_count": 6, "grid_x": 6, "grid_y": 0},
    )
    assert response.status_code == 409
    assert "6×6" in response.json()["detail"]


async def test_duplicate_number_is_still_refused_in_manual_mode(
    authenticated_client: AsyncClient,
) -> None:
    """*"İki masa aynı numarayı alamaz."* Katılımcı masasını numarayla buluyor."""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    await add_table(authenticated_client, event["id"], number=3, grid_x=1, grid_y=1)

    response = await authenticated_client.post(
        f"/events/{event['id']}/tables",
        json={"kind": "seated", "seat_count": 6, "number": 3, "grid_x": 2, "grid_y": 1},
    )
    assert response.status_code == 409
    assert "numara" in response.json()["detail"]


async def test_position_needs_both_axes(authenticated_client: AsyncClient) -> None:
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    layout = await add_table(authenticated_client, event["id"], grid_x=1, grid_y=1)

    response = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{layout['tables'][0]['id']}",
        json={"grid_x": 5},
    )
    assert response.status_code == 422


async def test_auto_mode_tables_cannot_be_positioned(
    authenticated_client: AsyncClient,
) -> None:
    """Otomatik modda ızgara yok; konum vermek anlamsız."""
    event = await create_event(authenticated_client)
    layout = await seated_layout(authenticated_client, event["id"])

    response = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{layout['tables'][0]['id']}",
        json={"grid_x": 1, "grid_y": 1},
    )
    assert response.status_code == 409


async def test_tables_cannot_be_placed_before_manual_mode(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    await seated_layout(authenticated_client, event["id"])

    response = await authenticated_client.post(
        f"/events/{event['id']}/tables",
        json={"kind": "seated", "seat_count": 6, "grid_x": 0, "grid_y": 0},
    )
    assert response.status_code == 409


# --- Alan blokları -----------------------------------------------------------


async def test_an_area_block_covers_several_cells(
    authenticated_client: AsyncClient,
) -> None:
    """*"Sahne, giriş, büfe gibi işaretler konabilir."* Eşleştirmeye girmez."""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])

    layout = await add_area(
        authenticated_client, event["id"], label="Sahne", grid_x=2, grid_y=0, width=6, height=2
    )

    area = layout["areas"][0]
    assert (area["label"], area["width"], area["height"]) == ("Sahne", 6, 2)
    # Alan blokları kapasiteye sayılmaz.
    assert layout["seating_capacity"] == 0


async def test_an_area_block_cannot_cover_a_table(
    authenticated_client: AsyncClient,
) -> None:
    """Aşama 1'den devreden kural: masa ile alan bloğu aynı hücrede olamaz.

    Şemada ifade edilemiyor — iki ayrı tabloyu kapsıyor.
    """
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    await add_table(authenticated_client, event["id"], number=4, grid_x=5, grid_y=1)

    response = await authenticated_client.post(
        f"/events/{event['id']}/areas",
        json={"label": "Büfe", "grid_x": 3, "grid_y": 0, "width": 4, "height": 3},
    )

    assert response.status_code == 409
    assert "4 numaralı masa" in response.json()["detail"]


async def test_a_table_cannot_be_placed_on_an_area_block(
    authenticated_client: AsyncClient,
) -> None:
    """Aynı kural ters yönde: blok önce konmuşsa masa üstüne gelemez."""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    await add_area(
        authenticated_client, event["id"], label="Giriş", grid_x=0, grid_y=0, width=3, height=3
    )

    response = await authenticated_client.post(
        f"/events/{event['id']}/tables",
        json={"kind": "seated", "seat_count": 6, "grid_x": 2, "grid_y": 2},
    )
    assert response.status_code == 409
    assert "Giriş" in response.json()["detail"]


async def test_adjacent_area_blocks_do_not_collide(
    authenticated_client: AsyncClient,
) -> None:
    """Bitişik olmak çakışmak değil: 0-2 ile 3-5 yan yana durabilir."""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    await add_area(
        authenticated_client, event["id"], label="Sahne", grid_x=0, grid_y=0, width=3, height=2
    )

    layout = await add_area(
        authenticated_client, event["id"], label="Büfe", grid_x=3, grid_y=0, width=3, height=2
    )
    assert len(layout["areas"]) == 2


async def test_an_area_block_is_moved_resized_and_deleted(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    layout = await add_area(authenticated_client, event["id"], grid_x=1, grid_y=1)
    area_id = layout["areas"][0]["id"]

    moved = await authenticated_client.patch(
        f"/events/{event['id']}/areas/{area_id}",
        json={"grid_x": 8, "grid_y": 2, "width": 4, "label": "Kayıt Masası"},
    )
    assert moved.status_code == 200
    area = moved.json()["areas"][0]
    assert (area["grid_x"], area["width"], area["label"]) == (8, 4, "Kayıt Masası")

    removed = await authenticated_client.delete(f"/events/{event['id']}/areas/{area_id}")
    assert removed.status_code == 200
    assert removed.json()["areas"] == []


async def test_an_area_block_cannot_grow_over_a_table(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    layout = await add_area(
        authenticated_client, event["id"], label="Sahne", grid_x=0, grid_y=0, width=2, height=2
    )
    await add_table(authenticated_client, event["id"], number=9, grid_x=3, grid_y=0)

    response = await authenticated_client.patch(
        f"/events/{event['id']}/areas/{layout['areas'][0]['id']}",
        json={"width": 5},
    )
    assert response.status_code == 409
    assert "9 numaralı masa" in response.json()["detail"]


async def test_an_area_block_cannot_leave_the_grid(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"], grid_width=8, grid_height=8)

    response = await authenticated_client.post(
        f"/events/{event['id']}/areas",
        json={"label": "Sahne", "grid_x": 6, "grid_y": 0, "width": 4, "height": 1},
    )
    assert response.status_code == 409


# --- Kalıcılık ---------------------------------------------------------------


async def test_the_layout_survives_a_reload(authenticated_client: AsyncClient) -> None:
    """Kabul kriteri: *"Sayfa yenilendiğinde düzen kayıpsız geliyor."*"""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"], grid_width=12, grid_height=9)
    await add_table(
        authenticated_client, event["id"], number=5, grid_x=2, grid_y=6, label="Sponsor Masası"
    )
    await add_area(
        authenticated_client, event["id"], label="Sahne", grid_x=0, grid_y=0, width=4, height=2
    )

    response = await authenticated_client.get(f"/events/{event['id']}/layout")
    layout = response.json()

    assert (layout["grid_width"], layout["grid_height"]) == (12, 9)
    table = layout["tables"][0]
    assert (table["number"], table["grid_x"], table["grid_y"]) == (5, 2, 6)
    assert table["label"] == "Sponsor Masası"
    area = layout["areas"][0]
    assert (area["label"], area["grid_x"], area["width"], area["height"]) == ("Sahne", 0, 4, 2)


# --- Görünürlük ve kilit -----------------------------------------------------


async def test_manual_layout_of_another_event_is_not_reachable(
    authenticated_client: AsyncClient,
) -> None:
    """Bölüm 7: başkasının etkinliğine 404, 403 değil."""
    first = await create_event(authenticated_client, name="Birinci")
    second = await create_event(authenticated_client, name="İkinci")
    await manual_layout(authenticated_client, first["id"])
    layout = await add_table(authenticated_client, first["id"], grid_x=1, grid_y=1)
    await manual_layout(authenticated_client, second["id"])

    foreign_table = layout["tables"][0]["id"]
    assert (
        await authenticated_client.delete(f"/events/{second['id']}/tables/{foreign_table}")
    ).status_code == 404

    foreign_area = (await add_area(authenticated_client, first["id"]))["areas"][0]["id"]
    assert (
        await authenticated_client.patch(
            f"/events/{second['id']}/areas/{foreign_area}", json={"label": "Kaçak"}
        )
    ).status_code == 404


async def test_manual_layout_is_locked_after_a_plan_exists(
    authenticated_client: AsyncClient, session: AsyncSession
) -> None:
    """Atamalar masa kimliğine bağlı; düzeni değiştirmek planı bozardı."""
    event = await create_event(authenticated_client)
    await manual_layout(authenticated_client, event["id"])
    layout = await add_table(authenticated_client, event["id"], grid_x=1, grid_y=1)
    layout = await add_area(authenticated_client, event["id"])
    table_id = layout["tables"][0]["id"]
    area_id = layout["areas"][0]["id"]

    # `authenticated_client` en son kaydolan kullanıcıyı kullanıyor.
    newest_user = select(User).order_by(User.id.desc()).limit(1)
    user = (await session.execute(newest_user)).scalar_one()
    registration = Registration(
        event_id=event["id"], user_id=user.id, qr_code=f"qr-manual-{event['id']}"
    )
    session.add(registration)
    plan = Plan(event_id=event["id"], version=1, status=PlanStatus.DRAFT, seed=7)
    session.add(plan)
    await session.flush()
    session.add(
        Assignment(
            plan_id=plan.id, slot_number=1, table_id=table_id, registration_id=registration.id
        )
    )
    await session.flush()

    event_id = event["id"]
    assert (
        await authenticated_client.put(
            f"/events/{event_id}/layout/manual", json={"grid_width": 20, "grid_height": 20}
        )
    ).status_code == 409
    assert (
        await authenticated_client.post(
            f"/events/{event_id}/tables",
            json={"kind": "seated", "seat_count": 6, "grid_x": 9, "grid_y": 9},
        )
    ).status_code == 409
    assert (
        await authenticated_client.patch(
            f"/events/{event_id}/tables/{table_id}", json={"grid_x": 4, "grid_y": 4}
        )
    ).status_code == 409
    assert (
        await authenticated_client.delete(f"/events/{event_id}/tables/{table_id}")
    ).status_code == 409
    assert (
        await authenticated_client.post(
            f"/events/{event_id}/areas", json={"label": "Büfe", "grid_x": 9, "grid_y": 9}
        )
    ).status_code == 409
    assert (
        await authenticated_client.patch(
            f"/events/{event_id}/areas/{area_id}", json={"label": "Sahne 2"}
        )
    ).status_code == 409
    assert (
        await authenticated_client.delete(f"/events/{event_id}/areas/{area_id}")
    ).status_code == 409


async def test_manual_layout_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.put("/events/1/layout/manual", json={})).status_code == 401
    assert (
        await client.post(
            "/events/1/tables", json={"kind": "seated", "seat_count": 6, "grid_x": 0, "grid_y": 0}
        )
    ).status_code == 401
    assert (
        await client.post("/events/1/areas", json={"label": "Sahne", "grid_x": 0, "grid_y": 0})
    ).status_code == 401
