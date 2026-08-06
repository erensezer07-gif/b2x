"""Program hesaplama (şartname M3, M4, Bölüm 10).

Kabul kriteri: *"Slot ve mola süreleri girildiğinde program anlık hesaplanıyor
ve bitiş saati görünüyor."*

Buradaki senaryolar Flutter tarafında da aynen çalışıyor: aynı formül iki dilde
yazıldığı için ikisinin ayrışmadığından emin olmak gerekiyor.

Bu testler veritabanı istemez.
"""

from datetime import UTC, datetime

import pytest

from app.services.schedule import build_schedule


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 15, hour, minute, tzinfo=UTC)


def test_spec_example() -> None:
    """Şartnamenin verdiği örnek: 10:00 başlangıç, 30 dakika slot, 10 dakika mola."""
    schedule = build_schedule(
        starts_at=at(10),
        slot_duration_minutes=30,
        break_duration_minutes=10,
        slot_count=3,
    )

    assert [(slot.starts_at, slot.ends_at) for slot in schedule.slots] == [
        (at(10, 0), at(10, 30)),
        (at(10, 40), at(11, 10)),
        (at(11, 20), at(11, 50)),
    ]


def test_slot_numbers_start_at_one() -> None:
    """Katılımcıya "Slot 1" gösteriliyor (M8), 0 değil."""
    schedule = build_schedule(
        starts_at=at(9),
        slot_duration_minutes=20,
        break_duration_minutes=5,
        slot_count=4,
    )
    assert [slot.number for slot in schedule.slots] == [1, 2, 3, 4]


def test_no_break_after_the_last_slot() -> None:
    """Etkinlik son görüşme biter bitmez biter; sondaki mola sayılmaz."""
    schedule = build_schedule(
        starts_at=at(10),
        slot_duration_minutes=30,
        break_duration_minutes=10,
        slot_count=2,
    )
    assert schedule.ends_at == at(11, 10)
    # 30 + 10 + 30 = 70; sondaki molayla 80 olurdu.
    assert schedule.total_minutes == 70


def test_single_slot_has_no_break_at_all() -> None:
    schedule = build_schedule(
        starts_at=at(14),
        slot_duration_minutes=45,
        break_duration_minutes=15,
        slot_count=1,
    )
    assert schedule.starts_at == at(14)
    assert schedule.ends_at == at(14, 45)
    assert schedule.total_minutes == 45


def test_zero_break_runs_slots_back_to_back() -> None:
    schedule = build_schedule(
        starts_at=at(10),
        slot_duration_minutes=30,
        break_duration_minutes=0,
        slot_count=3,
    )
    assert [slot.starts_at for slot in schedule.slots] == [at(10), at(10, 30), at(11)]
    assert schedule.ends_at == at(11, 30)


def test_schedule_may_cross_midnight() -> None:
    """Akşam başlayan uzun bir etkinlik ertesi güne taşabilir."""
    schedule = build_schedule(
        starts_at=at(23),
        slot_duration_minutes=30,
        break_duration_minutes=10,
        slot_count=4,
    )
    # 23:00, 23:40, 00:20, 01:00 — sonuncusu 01:30'da biter.
    assert [slot.starts_at.hour for slot in schedule.slots] == [23, 23, 0, 1]
    assert schedule.ends_at == datetime(2026, 9, 16, 1, 30, tzinfo=UTC)
    assert schedule.total_minutes == 150


def test_spec_scale_fits_a_working_day() -> None:
    """Şartname 9.9'un ölçeği: 8 tur. Organizatör toplam süreyi görebilmeli."""
    schedule = build_schedule(
        starts_at=at(10),
        slot_duration_minutes=30,
        break_duration_minutes=10,
        slot_count=8,
    )
    assert len(schedule.slots) == 8
    # 8×30 + 7×10 = 310 dakika
    assert schedule.total_minutes == 310
    assert schedule.ends_at == at(15, 10)


@pytest.mark.parametrize(
    ("slot_count", "slot_duration", "break_duration"),
    [
        (0, 30, 10),
        (-1, 30, 10),
        (4, 0, 10),
        (4, -5, 10),
        (4, 30, -1),
    ],
)
def test_invalid_input_is_rejected(
    slot_count: int, slot_duration: int, break_duration: int
) -> None:
    """Geçersiz girdi sessizce tuhaf bir program üretmemeli."""
    with pytest.raises(ValueError):
        build_schedule(
            starts_at=at(10),
            slot_duration_minutes=slot_duration,
            break_duration_minutes=break_duration,
            slot_count=slot_count,
        )
