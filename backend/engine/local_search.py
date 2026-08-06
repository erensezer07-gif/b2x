"""Adım 4 — yerel arama (şartname 9.7).

Açgözlü başlangıçtan alınır ve küçük değişiklikler denenir:

* iki kişinin yerini değiştir (**takas**)
* bir kişiyi başka masaya taşı (**taşıma**)
* bir kişiyi masadan çıkar (**çıkarma**)

Her değişiklikten sonra amaç değeri yeniden hesaplanır. İyileştirdiyse tutulur,
kötüleştirdiyse geri alınır. **Ara sıra kötüleştiren hamleler de kabul edilir** —
yoksa arama yerel bir tepede sıkışıp kalır. Kabul olasılığı sıcaklıkla azalır.

## Taşımanın kapsamı

Şartname üç hamle sayıyor. "Taşıma" burada kaynağın *hiçbir masa olmaması*
durumunu da kapsar — yani oturmayan birini masaya oturtmak da bir taşımadır.
Bu olmadan açgözlü aşamada yer bulamamış kimse bir daha asla oturamazdı ve
adalet kuralı (9.6) yerel aramadan hiç fayda göremezdi.

## Asgari grup kuralı

Bir kişiyi masadan çıkarmak geriye tek kişi bırakabilir; bu kesin kurala
aykırıdır (9.5). Böyle bir durumda kalan kişi de masadan çıkarılır ve hamlenin
geri alınması ikisini birden geri koyar. Plan her an geçerli kalır, dolayısıyla
amaç değeri her an anlamlıdır.
"""

import math
import random
from dataclasses import dataclass

from engine.state import UNSEATED, PlanState

# Kabul olasılığı exp(fark / sıcaklık). Amaç değerindeki tipik hamle farkı 1-3
# mertebesinde (adalet ağırlığı 2.0, masa skoru 0-1 arası), sıcaklık da o
# mertebeden başlayıp sıfıra yaklaşır.
INITIAL_TEMPERATURE = 0.6
FINAL_TEMPERATURE = 0.01

# Hamle türlerinin seçilme olasılıkları. Taşıma en verimlisi: hem masa
# değiştirir hem oturmayanı oturtur. Çıkarma en seyrek — çoğu zaman amaç
# değerini düşürür, yalnızca bir kişi masayı gerçekten bozuyorsa işe yarar.
RELOCATE_SHARE = 0.55
SWAP_SHARE = 0.35

# Kayan nokta gürültüsü yüzünden aynı planı "iyileşme" sanmamak için.
IMPROVEMENT_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class SearchReport:
    """Aramanın ne yaptığının özeti — ayar yaparken bakılır."""

    iterations: int
    applied: int
    accepted: int
    improvements: int
    objective_before: float
    objective_after: float


def optimise(
    state: PlanState, rng: random.Random, max_iterations: int | None = None
) -> SearchReport:
    """Planı yerinde iyileştirir ve gördüğü en iyi hâle geri döner."""
    budget = max_iterations if max_iterations is not None else state.input.settings.max_iterations
    started_at = state.objective()

    if budget <= 0 or state.participant_count == 0:
        return SearchReport(0, 0, 0, 0, started_at, started_at)

    current = started_at
    best_value = current
    best_plan = state.snapshot()

    applied = 0
    accepted = 0
    improvements = 0

    for iteration in range(budget):
        undo = _propose(state, rng)
        if undo is None:
            continue
        applied += 1

        candidate = state.objective()
        difference = candidate - current

        if difference >= 0 or rng.random() < math.exp(difference / _temperature(iteration, budget)):
            current = candidate
            accepted += 1
            if current > best_value + IMPROVEMENT_EPSILON:
                best_value = current
                best_plan = state.snapshot()
                improvements += 1
        else:
            undo()

    state.restore(best_plan)
    return SearchReport(budget, applied, accepted, improvements, started_at, best_value)


def _temperature(iteration: int, budget: int) -> float:
    """Geometrik soğutma: başta cesur, sonda ihtiyatlı."""
    if budget <= 1:
        return FINAL_TEMPERATURE
    progress = iteration / (budget - 1)
    return INITIAL_TEMPERATURE * (FINAL_TEMPERATURE / INITIAL_TEMPERATURE) ** progress


def _propose(state: PlanState, rng: random.Random):
    roll = rng.random()
    if roll < RELOCATE_SHARE:
        return _relocate(state, rng)
    if roll < RELOCATE_SHARE + SWAP_SHARE:
        return _swap(state, rng)
    return _remove(state, rng)


def _movable_slot(state: PlanState, rng: random.Random) -> int | None:
    slot = rng.randrange(state.slot_count)
    return None if slot in state.input.frozen_slots else slot


def _occupied_tables(state: PlanState, slot: int) -> list[int]:
    return [table for table in range(state.table_count) if state.seats[slot][table]]


def _leftover_singleton(state: PlanState, slot: int, table: int) -> int | None:
    """Masada tek kişi kaldıysa o kişiyi döndürür (9.5 asgari grup)."""
    occupants = state.seats[slot][table]
    return occupants[0] if len(occupants) == 1 else None


def _relocate(state: PlanState, rng: random.Random):
    """Bir kişiyi başka masaya taşır. Kaynak "hiçbir masa" da olabilir."""
    slot = _movable_slot(state, rng)
    if slot is None:
        return None

    participant = rng.randrange(state.participant_count)
    if state.is_pinned(slot, participant):
        return None

    target = rng.randrange(state.table_count)
    origin = int(state.location[slot, participant])
    if origin == target:
        return None

    # Boş masaya taşımak tek kişilik masa yaratır — kesin kural ihlali (9.5).
    #
    # Bu, amaç fonksiyonunun görebileceği bir hata da değildi: tek kişilik masa
    # "kullanılmıyor" sayıldığı için 0 puan alıyor, oturan kişi ise adalet
    # teriminden puan kazanıyordu. Arama bu yüzden insanları boş masalara yalnız
    # park edip adalet skorunu şişiriyor, plan sonunda temizlenince o kişiler
    # hedefin altına düşüyordu.
    #
    # Yeni masa açmak açgözlü başlangıcın (Adım 3) ve adalet düzeltmesinin
    # (Adım 5) işi; ikisi de masayı en az iki kişiyle açar.
    if not state.seats[slot][target]:
        return None

    evicted: int | None = None
    if origin != UNSEATED:
        state.unseat(slot, origin, participant)
        leftover = _leftover_singleton(state, slot, origin)
        if leftover is not None:
            if state.is_pinned(slot, leftover):
                state.seat(slot, origin, participant)
                return None
            state.unseat(slot, origin, leftover)
            evicted = leftover

    if not state.can_seat(slot, target, participant):
        if origin != UNSEATED:
            state.seat(slot, origin, participant)
            if evicted is not None:
                state.seat(slot, origin, evicted)
        return None

    state.seat(slot, target, participant)

    def undo() -> None:
        state.unseat(slot, target, participant)
        if origin != UNSEATED:
            state.seat(slot, origin, participant)
            if evicted is not None:
                state.seat(slot, origin, evicted)

    return undo


def _swap(state: PlanState, rng: random.Random):
    """İki kişinin yerini değiştirir. Masa boyutları değişmez."""
    slot = _movable_slot(state, rng)
    if slot is None:
        return None

    occupied = _occupied_tables(state, slot)
    if len(occupied) < 2:
        return None

    first_table = occupied[rng.randrange(len(occupied))]
    second_table = occupied[rng.randrange(len(occupied))]
    if first_table == second_table:
        return None

    first_occupants = state.seats[slot][first_table]
    second_occupants = state.seats[slot][second_table]
    first = first_occupants[rng.randrange(len(first_occupants))]
    second = second_occupants[rng.randrange(len(second_occupants))]

    if state.is_pinned(slot, first) or state.is_pinned(slot, second):
        return None

    state.unseat(slot, first_table, first)
    state.unseat(slot, second_table, second)

    if not (
        state.can_seat(slot, second_table, first) and state.can_seat(slot, first_table, second)
    ):
        state.seat(slot, first_table, first)
        state.seat(slot, second_table, second)
        return None

    state.seat(slot, second_table, first)
    state.seat(slot, first_table, second)

    def undo() -> None:
        state.unseat(slot, second_table, first)
        state.unseat(slot, first_table, second)
        state.seat(slot, first_table, first)
        state.seat(slot, second_table, second)

    return undo


def _remove(state: PlanState, rng: random.Random):
    """Bir kişiyi masadan çıkarır — boş bırakmak daha iyiyse."""
    slot = _movable_slot(state, rng)
    if slot is None:
        return None

    occupied = _occupied_tables(state, slot)
    if not occupied:
        return None

    table = occupied[rng.randrange(len(occupied))]
    occupants = state.seats[slot][table]
    participant = occupants[rng.randrange(len(occupants))]
    if state.is_pinned(slot, participant):
        return None

    state.unseat(slot, table, participant)

    evicted: int | None = None
    leftover = _leftover_singleton(state, slot, table)
    if leftover is not None:
        if state.is_pinned(slot, leftover):
            state.seat(slot, table, participant)
            return None
        state.unseat(slot, table, leftover)
        evicted = leftover

    def undo() -> None:
        state.seat(slot, table, participant)
        if evicted is not None:
            state.seat(slot, table, evicted)

    return undo
