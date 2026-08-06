"""Adım 2 ve 3 — sabit atamalar ve açgözlü başlangıç (şartname 9.7).

**Adım 2:** çapa kişiler ve kilitli atamalar önce yerine konur; motor bunları hiç
oynatmaz.

**Adım 3:** her slot için en yüksek skorlu ikili bir masaya oturtulur, sonra o
masaya en uyumlu üçüncü kişi eklenir, sonra dördüncü. Kesin kurallar her adımda
kontrol edilir. Masa dolunca veya uygun kimse kalmayınca yeni masaya geçilir.

Sonuç mükemmel değildir ama **geçerli** bir plandır — Adım 4 bunun üzerine
çalışır.

## Aday seçimi

Masa skoru en zayıf bağ olduğu için (9.4), masaya eklenecek adayın doğru ölçütü
"kendisiyle en yüksek skoru olan" değil, **"masanın en zayıf bağını en az
bozan"**dır. Bir aday mevcut üyelerden ikisiyle mükemmel, üçüncüsüyle berbat
uyumluysa masayı berbat eder.

## Kalite eşiği

Eşiğin altına düşüren aday alınmaz; masa eksik kalır. 9.5: *"Boş sandalye, kötü
eşleşmeden iyidir."* Eşik yüzünden yerleşemeyen kişileri Adım 5 (adalet
düzeltmesi) toplar — orada eşik esnetilir.
"""

import numpy as np

from engine.scoring import SynergyModel
from engine.state import UNSEATED, PlanState
from engine.types import EngineInput

# Geçersiz ikilileri argmax'ın seçemeyeceği bir değere iter.
_IMPOSSIBLE = -1.0


def build_initial_plan(engine_input: EngineInput, model: SynergyModel) -> PlanState:
    """Adım 2 ve 3'ü çalıştırıp geçerli bir başlangıç planı üretir."""
    state = PlanState(engine_input, model)
    place_fixed_assignments(state)
    fill_greedily(state)
    state.drop_single_occupant_tables()
    return state


def place_fixed_assignments(state: PlanState) -> None:
    """Adım 2 — çapa kişileri ve kilitli atamaları yerine koyar.

    Bunlar değiştirilemez olduğu için çakışan bir girdi sessizce düzeltilemez;
    hata verilir. Aksi hâlde organizatör kilitlediği bir atamanın kaybolduğunu
    ancak planı gözle karşılaştırınca fark ederdi.
    """
    for fixed in sorted(
        state.input.fixed_assignments,
        key=lambda item: (item.slot, item.table, item.participant),
    ):
        if not state.can_seat(fixed.slot, fixed.table, fixed.participant, respect_frozen=False):
            raise ValueError(
                f"Sabit atama yerleştirilemedi: slot {fixed.slot}, masa {fixed.table}, "
                f"katılımcı {fixed.participant}. Kapasite, aynı şirket ayrımı veya "
                f"tek yer kuralıyla çakışıyor."
            )
        state.seat(fixed.slot, fixed.table, fixed.participant)


def fill_greedily(state: PlanState) -> None:
    """Adım 3 — her slotu masa masa doldurur."""
    for slot in range(state.slot_count):
        if slot in state.input.frozen_slots:
            continue
        for table in _table_order(state):
            _fill_table(state, slot, table)


def _table_order(state: PlanState) -> list[int]:
    """Büyük masalar önce.

    Aday havuzu en genişken büyük masaları kurmak, sonlara doğru kalan az sayıda
    kişinin küçük masalara sığmasını kolaylaştırır. Eşitlikte indeks sırası —
    determinizm için (5.3).
    """
    return sorted(
        range(state.table_count),
        key=lambda table: (-int(state.capacity[table]), table),
    )


def _fill_table(state: PlanState, slot: int, table: int) -> None:
    threshold = state.input.settings.quality_threshold
    capacity = int(state.capacity[table])

    if not state.occupants(slot, table):
        pair = _best_available_pair(state, slot, table, threshold)
        if pair is None:
            return
        first, second = pair
        state.seat(slot, table, first)
        state.seat(slot, table, second)

    while len(state.occupants(slot, table)) < capacity:
        candidate = _best_candidate(state, slot, table, threshold)
        if candidate is None:
            break
        state.seat(slot, table, candidate)


def _available(state: PlanState, slot: int) -> np.ndarray:
    """Bu slotta henüz hiçbir masaya oturmamış katılımcılar."""
    return np.flatnonzero(state.location[slot] == UNSEATED)


def _best_available_pair(
    state: PlanState, slot: int, table: int, threshold: float
) -> tuple[int, int] | None:
    """Masayı açacak en yüksek skorlu geçerli ikili.

    Kalite eşiğinin altındaysa masa boş bırakılır.
    """
    available = _available(state, slot)
    if available.size < 2 or int(state.capacity[table]) < 2:
        return None

    scores = state.score[np.ix_(available, available)].copy()

    # Aynı şirket ve daha önce karşılaşmış ikililer elenir (9.5).
    companies = state.company[available]
    blocked = companies[:, None] == companies[None, :]
    blocked |= state.met[np.ix_(available, available)]
    np.fill_diagonal(blocked, True)
    scores[blocked] = _IMPOSSIBLE

    flat_index = int(np.argmax(scores))
    best = float(scores.flat[flat_index])
    if best < threshold:
        return None

    row, column = divmod(flat_index, available.size)
    first = int(available[row])
    second = int(available[column])
    return (first, second) if first < second else (second, first)


def _best_candidate(state: PlanState, slot: int, table: int, threshold: float) -> int | None:
    """Masanın en zayıf bağını en az bozan aday.

    Eşiğin altına düşüren aday alınmaz — masa eksik kalır.
    """
    best_candidate: int | None = None
    best_score = -1.0

    for participant in _available(state, slot):
        candidate = int(participant)
        if not state.can_seat(slot, table, candidate):
            continue
        resulting = state.score_if_seated(slot, table, candidate)
        if resulting < threshold:
            continue
        # Kesin `>`: eşitlikte küçük indeksli aday kazanır, sonuç deterministik.
        if resulting > best_score:
            best_score = resulting
            best_candidate = candidate

    return best_candidate
