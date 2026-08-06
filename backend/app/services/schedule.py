"""Etkinlik programının hesaplanması (şartname M3, M4).

*"Organizatör başlangıç saati, slot süresi, mola süresi ve slot sayısı girer;
sistem 'Slot 1: 10:00-10:30, Slot 2: 10:40-11:10...' şeklinde programı üretir."*

Program **saklanmıyor, hesaplanıyor.** Ayrı bir `slots` tablosu yok (Aşama 1):
dört alandan türetilebilen bir şeyi kaydetmek, alanlar değiştiğinde iki kaynağın
ayrışması demekti.

Bu modül saf: veritabanı, HTTP veya uygulama katmanı görmez. Aynı formül Flutter
tarafında da var (M4 "girildikçe anlık gösterilir" istiyor, her tuş vuruşunda
sunucuya gitmek anlamsız). İki tarafın ayrışmaması için aynı senaryolar iki
tarafta da test ediliyor.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class SlotTiming:
    """Bir görüşme turunun saatleri."""

    number: int
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class Schedule:
    """Etkinliğin tüm programı."""

    slots: tuple[SlotTiming, ...]

    @property
    def starts_at(self) -> datetime:
        return self.slots[0].starts_at

    @property
    def ends_at(self) -> datetime:
        """Son slotun bitişi.

        Son slottan **sonra mola yoktur**: etkinlik son görüşme biter bitmez
        biter. Molayı da eklemek toplam süreyi bir mola kadar uzun gösterirdi.
        """
        return self.slots[-1].ends_at

    @property
    def total_minutes(self) -> int:
        """Baştan sona toplam süre — organizatörün "çok uzun sürüyor" dediği sayı."""
        return int((self.ends_at - self.starts_at).total_seconds() // 60)


def build_schedule(
    *,
    starts_at: datetime,
    slot_duration_minutes: int,
    break_duration_minutes: int,
    slot_count: int,
) -> Schedule:
    """Slot saatlerini hesaplar.

    Slot numaraları 1'den başlar: katılımcıya "Slot 1" diye gösteriliyor
    (M8). Motorun içindeki 0 tabanlı indeksle karıştırılmamalı — dönüşüm
    Aşama 7'de dış katmanda yapılacak.
    """
    if slot_count < 1:
        raise ValueError("Slot sayısı en az 1 olmalı.")
    if slot_duration_minutes < 1:
        raise ValueError("Slot süresi en az 1 dakika olmalı.")
    if break_duration_minutes < 0:
        raise ValueError("Mola süresi negatif olamaz.")

    step = timedelta(minutes=slot_duration_minutes + break_duration_minutes)
    duration = timedelta(minutes=slot_duration_minutes)

    slots = tuple(
        SlotTiming(
            number=index + 1,
            starts_at=starts_at + index * step,
            ends_at=starts_at + index * step + duration,
        )
        for index in range(slot_count)
    )
    return Schedule(slots=slots)
