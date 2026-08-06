"""Otomatik salon düzeni (şartname M5, Bölüm 10).

Kabul kriteri: *"Masa sayısı ve sandalye sayısı girilince masalar numaralı
olarak oluşuyor."*
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Plan, PlanStatus, Registration, User


async def create_event(client: AsyncClient, **overrides) -> dict:
    response = await client.post(
        "/events",
        json={
            "name": "İhracat Forumu",
            "starts_at": datetime(2026, 10, 1, 9, 0, tzinfo=UTC).isoformat(),
            "slot_duration_minutes": 30,
            "break_duration_minutes": 10,
            "slot_count": 6,
            "capacity": 80,
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def seated_layout(client: AsyncClient, event_id: int, **overrides) -> dict:
    response = await client.put(
        f"/events/{event_id}/layout/auto",
        json={"kind": "seated", "table_count": 8, "seat_count": 6, **overrides},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- Otomatik düzen ---------------------------------------------------------


async def test_tables_are_numbered_from_one(authenticated_client: AsyncClient) -> None:
    """*"Sistem masaları oluşturur ve 1'den başlayarak numaralandırır."*"""
    event = await create_event(authenticated_client)
    layout = await seated_layout(authenticated_client, event["id"])

    assert [table["number"] for table in layout["tables"]] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert layout["mode"] == "auto"
    assert layout["seating_capacity"] == 48


async def test_standing_tables_carry_a_people_range(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    response = await authenticated_client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "standing", "table_count": 5, "min_people": 3, "max_people": 8},
    )

    layout = response.json()
    assert all(table["kind"] == "standing" for table in layout["tables"])
    assert all(table["seat_count"] is None for table in layout["tables"])
    # Kapasite üst sınırdan hesaplanıyor; alt sınır bir hedef (9.5).
    assert layout["seating_capacity"] == 40


async def test_rebuilding_replaces_the_previous_tables(
    authenticated_client: AsyncClient,
) -> None:
    """`PUT` yerine koyuyor: her denemede masa birikmemeli."""
    event = await create_event(authenticated_client)
    await seated_layout(authenticated_client, event["id"], table_count=8)

    layout = await seated_layout(authenticated_client, event["id"], table_count=3)

    assert len(layout["tables"]) == 3
    assert [table["number"] for table in layout["tables"]] == [1, 2, 3]


async def test_seated_layout_rejects_a_people_range(
    authenticated_client: AsyncClient,
) -> None:
    """Masa tipi ile kapasite alanları tutarsızsa istemci hatası dönmeli."""
    event = await create_event(authenticated_client)
    response = await authenticated_client.put(
        f"/events/{event['id']}/layout/auto",
        json={
            "kind": "seated",
            "table_count": 4,
            "seat_count": 6,
            "min_people": 2,
            "max_people": 8,
        },
    )
    assert response.status_code == 422


async def test_standing_layout_needs_both_bounds(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    response = await authenticated_client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "standing", "table_count": 4, "min_people": 3},
    )
    assert response.status_code == 422


async def test_layout_is_absent_before_it_is_built(
    authenticated_client: AsyncClient,
) -> None:
    event = await create_event(authenticated_client)
    response = await authenticated_client.get(f"/events/{event['id']}/layout")
    assert response.status_code == 404


# --- Masa düzenleme (M5) ----------------------------------------------------


async def test_a_single_table_can_be_resized(
    authenticated_client: AsyncClient,
) -> None:
    """*"Masalar farklı sandalye sayısına sahip olabilmeli."*"""
    event = await create_event(authenticated_client)
    layout = await seated_layout(authenticated_client, event["id"])
    table_id = layout["tables"][0]["id"]

    response = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{table_id}",
        json={"seat_count": 10, "label": "Sponsor Masası"},
    )

    updated = next(t for t in response.json()["tables"] if t["id"] == table_id)
    assert updated["seat_count"] == 10
    assert updated["label"] == "Sponsor Masası"
    # 7×6 + 10 = 52
    assert response.json()["seating_capacity"] == 52


async def test_duplicate_table_number_is_rejected(
    authenticated_client: AsyncClient,
) -> None:
    """*"İki masa aynı numarayı alamaz."* Katılımcı masasını numarayla buluyor."""
    event = await create_event(authenticated_client)
    layout = await seated_layout(authenticated_client, event["id"])
    first, second = layout["tables"][0], layout["tables"][1]

    response = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{second['id']}",
        json={"number": first["number"]},
    )
    assert response.status_code == 409


async def test_table_of_another_event_is_not_found(
    authenticated_client: AsyncClient,
) -> None:
    first = await create_event(authenticated_client, name="Birinci")
    second = await create_event(authenticated_client, name="İkinci")
    layout = await seated_layout(authenticated_client, first["id"])
    foreign_table = layout["tables"][0]["id"]

    response = await authenticated_client.patch(
        f"/events/{second['id']}/tables/{foreign_table}", json={"seat_count": 8}
    )
    assert response.status_code == 404


# --- Plan üretilmişse düzen kilitlenir ---------------------------------------


async def test_layout_cannot_change_after_a_plan_exists(
    authenticated_client: AsyncClient, session: AsyncSession
) -> None:
    """Atamalar masa kimliğine bağlı; masaları silmek planı bozardı."""
    event = await create_event(authenticated_client)
    layout = await seated_layout(authenticated_client, event["id"])

    # `authenticated_client` en son kaydolan kullanıcıyı kullanıyor.
    newest_user = select(User).order_by(User.id.desc()).limit(1)
    user = (await session.execute(newest_user)).scalar_one()
    registration = Registration(
        event_id=event["id"], user_id=user.id, qr_code=f"qr-plan-{event['id']}"
    )
    session.add(registration)
    plan = Plan(event_id=event["id"], version=1, status=PlanStatus.DRAFT, seed=42)
    session.add(plan)
    await session.flush()

    session.add(
        Assignment(
            plan_id=plan.id,
            slot_number=1,
            table_id=layout["tables"][0]["id"],
            registration_id=registration.id,
        )
    )
    await session.flush()

    rebuild = await authenticated_client.put(
        f"/events/{event['id']}/layout/auto",
        json={"kind": "seated", "table_count": 3, "seat_count": 6},
    )
    assert rebuild.status_code == 409

    resize = await authenticated_client.patch(
        f"/events/{event['id']}/tables/{layout['tables'][0]['id']}",
        json={"seat_count": 12},
    )
    assert resize.status_code == 409


# --- Yetki ------------------------------------------------------------------


async def test_layout_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events/1/layout")).status_code == 401
    assert (
        await client.put(
            "/events/1/layout/auto",
            json={"kind": "seated", "table_count": 4, "seat_count": 6},
        )
    ).status_code == 401
