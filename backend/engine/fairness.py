"""Adım 5 — adalet düzeltmesi (şartname 9.6).

*"Asgari görüşme sayısını tutturamamış kişiler bulunur. Bu kişiler için kalite
eşiği esnetilir ve uygun masalara yerleştirilmeye çalışılır."*

Bu adım olmazsa ürün en sık şu şekilde başarısız olur: motor "kalitesiz eşleşme
yapmayayım" der, çoğunluk sekiz turun sekizinde masada oturur, azınlık birinde.
O azınlık bilete para vermiştir.

Buradaki tek fark **kalite eşiğinin uygulanmamasıdır**. Kesin kurallar (kapasite,
şirket ayrımı, tekrar yok, tek yer, asgari grup) burada da çiğnenmez — onlar
"asla ihlal edilemez" (9.5).

İki yol denenir, bu sırayla:

1. **Mevcut masaya katılma.** Kişiyi, oturan iki veya daha fazla kişinin olduğu
   ve kapasitesi yeten bir masaya koymak. Masa skorunu en az bozan masa seçilir.
2. **Yeni masa açma.** Hedefin altındaki iki kişiyi boş bir masaya birlikte
   oturtmak. Tek kişilik masa kurulamayacağı için (9.5) ikili gerekir.

Ulaşılamayan durumlar olabilir — şartname bunu kabul ediyor: *"o zaman motor
mümkün olan en yüksek asgariyi hedefler ve özet raporunda bunu bildirir."*
"""

from dataclasses import dataclass

import numpy as np

from engine.state import PlanState


@dataclass(frozen=True, slots=True)
class FairnessReport:
    """Düzeltmenin ne başardığı."""

    placements: int
    below_target_before: int
    below_target_after: int
    lowest_rounds: int


def repair_fairness(state: PlanState) -> FairnessReport:
    """Hedefin altında kalanları, eşiği esneterek yerleştirmeye çalışır."""
    target = state.input.settings.min_meetings_per_person
    before = len(state.participants_below_target())
    placements = 0

    while True:
        candidates = _below_target(state, target)
        if not candidates:
            break

        progress = False
        for participant in candidates:
            if state.rounds[participant] >= target:
                continue
            if _join_existing_table(state, participant):
                placements += 1
                progress = True

        if not progress and _open_table_for_pair(state, _below_target(state, target)):
            placements += 2
            progress = True

        if not progress:
            # Kalanlar için yapılabilecek bir şey yok; özet bunu bildirecek.
            break

    return FairnessReport(
        placements=placements,
        below_target_before=before,
        below_target_after=len(state.participants_below_target()),
        lowest_rounds=int(state.rounds.min()) if state.participant_count else 0,
    )


def _below_target(state: PlanState, target: int) -> list[int]:
    """Hedefin altındakiler, en az tur alandan başlayarak.

    `stable` sıralama determinizm için: eşit tur sayısına sahip kişiler her
    zaman aynı sırada işlenir (5.3).
    """
    order = np.argsort(state.rounds, kind="stable")
    return [int(index) for index in order if state.rounds[index] < target]


def _join_existing_table(state: PlanState, participant: int) -> bool:
    """Kişiyi, masa skorunu en az bozan mevcut masaya oturtur.

    Kalite eşiği bilerek uygulanmaz — bu adımın varlık sebebi o.
    """
    best_seat: tuple[int, int] | None = None
    best_score = -1.0

    for slot in range(state.slot_count):
        if slot in state.input.frozen_slots:
            continue
        if state.is_seated(slot, participant):
            continue
        for table in range(state.table_count):
            # Yalnızca zaten kullanılan masalar: boş masaya tek kişi konamaz.
            if len(state.seats[slot][table]) < 2:
                continue
            if not state.can_seat(slot, table, participant):
                continue
            score = state.score_if_seated(slot, table, participant)
            if score > best_score:
                best_score = score
                best_seat = (slot, table)

    if best_seat is None:
        return False

    state.seat(best_seat[0], best_seat[1], participant)
    return True


def _open_table_for_pair(state: PlanState, candidates: list[int]) -> bool:
    """Hedefin altındaki iki kişiyi boş bir masaya birlikte oturtur."""
    if len(candidates) < 2:
        return False

    for slot in range(state.slot_count):
        if slot in state.input.frozen_slots:
            continue

        empty_tables = [
            table
            for table in range(state.table_count)
            if not state.seats[slot][table] and int(state.capacity[table]) >= 2
        ]
        if not empty_tables:
            continue
        table = empty_tables[0]

        for position, first in enumerate(candidates):
            if state.is_seated(slot, first) or not state.can_seat(slot, table, first):
                continue
            state.seat(slot, table, first)

            for second in candidates[position + 1 :]:
                if state.is_seated(slot, second):
                    continue
                if state.can_seat(slot, table, second):
                    state.seat(slot, table, second)
                    return True

            # Eşi bulunamadı; tek kişilik masa bırakmamak için geri alınır.
            state.unseat(slot, table, first)

    return False
