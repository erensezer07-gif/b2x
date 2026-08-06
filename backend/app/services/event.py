"""Etkinlik iş mantığı (şartname M4, M5).

Uçlar ince tutuluyor; kapasite hesabı, program üretimi ve yanıt kurma burada.
Aynı hesap hem etkinlik detayında hem düzen kurulduktan sonra gerekiyor.
"""

from app.models import Event, Layout, Table
from app.schemas.event import CapacitySummary, EventResponse, SlotTimingResponse
from app.schemas.layout import AreaResponse, LayoutResponse, TableResponse
from app.services.schedule import build_schedule
from app.services.storage import Storage


def table_capacity(table: Table) -> int:
    """Bir masaya oturabilecek azami kişi (şartname 9.5).

    Oturmalı masada sandalye sayısı, ayaklı masada üst sınır. İkisi de kesin
    üst sınır; ayaklı masanın **alt** sınırı bir hedeftir, kapasiteye girmez.
    """
    return table.seat_count or table.max_people or 0


def seating_capacity(layout: Layout | None) -> int:
    """Salonun toplam oturma kapasitesi — bir slotta kaç kişi oturabilir."""
    if layout is None:
        return 0
    return sum(table_capacity(table) for table in layout.tables)


def build_capacity_summary(event: Event, layout: Layout | None) -> CapacitySummary:
    """Kontenjan ile salon kapasitesini karşılaştırır (M4).

    Kontenjan kapasiteyi aşıyorsa uyarı bayrağı kalkar. **Engel değil uyarı:**
    organizatör gelmeyecekleri hesaba katıyor olabilir.
    """
    seats = seating_capacity(layout)
    return CapacitySummary(
        capacity=event.capacity,
        seating_capacity=seats,
        table_count=len(layout.tables) if layout else 0,
        exceeds_seating=seats > 0 and event.capacity > seats,
    )


def build_layout_response(layout: Layout) -> LayoutResponse:
    tables = sorted(layout.tables, key=lambda table: table.number)
    # Alan blokları eklendikleri sırayla dönüyor; aralarında bir öncelik yok,
    # kimlik sırası istemcide kararlı bir çizim düzeni veriyor.
    areas = sorted(layout.areas, key=lambda area: area.id)
    return LayoutResponse(
        id=layout.id,
        mode=layout.mode,
        grid_width=layout.grid_width,
        grid_height=layout.grid_height,
        tables=[TableResponse.model_validate(table) for table in tables],
        areas=[AreaResponse.model_validate(area) for area in areas],
        seating_capacity=seating_capacity(layout),
    )


def build_event_response(event: Event, layout: Layout | None, storage: Storage) -> EventResponse:
    """Etkinliğin tam yanıtı: alanlar, program ve kapasite özeti."""
    schedule = build_schedule(
        starts_at=event.starts_at,
        slot_duration_minutes=event.slot_duration_minutes,
        break_duration_minutes=event.break_duration_minutes,
        slot_count=event.slot_count,
    )
    has_layout = layout is not None and len(layout.tables) > 0

    return EventResponse(
        id=event.id,
        name=event.name,
        description=event.description,
        # Anahtar değil kullanılabilir adres dönüyor (Bölüm 3).
        cover_url=(storage.public_url(event.cover_image_key) if event.cover_image_key else None),
        starts_at=event.starts_at,
        venue_name=event.venue_name,
        address=event.address,
        slot_duration_minutes=event.slot_duration_minutes,
        break_duration_minutes=event.break_duration_minutes,
        slot_count=event.slot_count,
        capacity=event.capacity,
        registration_deadline=event.registration_deadline,
        auto_approve_registrations=event.auto_approve_registrations,
        request_quota=event.request_quota,
        requests_close_at=event.requests_close_at,
        status=event.status,
        schedule=[
            SlotTimingResponse(number=slot.number, starts_at=slot.starts_at, ends_at=slot.ends_at)
            for slot in schedule.slots
        ],
        ends_at=schedule.ends_at,
        total_minutes=schedule.total_minutes,
        capacity_summary=build_capacity_summary(event, layout),
        has_layout=has_layout,
        # Salon düzeni kurulmadan kayıtlar açılamaz (M4, Bölüm 10). Arayüz
        # düğmeyi buna bakarak kapatıyor; asıl kapı uçta.
        can_open_registration=has_layout,
    )
