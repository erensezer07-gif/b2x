"""Adım 6 — gerekçe üretimi (şartname 9.7).

*"Nihai plandaki her masa arkadaşlığı için skor kırılımı toplanır ve saklanır."*

Bu tablo katılımcıya "neden bu kişiyle eşleştim" cevabını verir (M8). Motor skoru
hesaplarken bu bilgiye zaten sahiptir; burada yalnızca oturan ikililer için
yeniden toplanır — tüm ikililer için saklamak gereksiz yer kaplardı.

**Motor cümle kurmaz.** Yalnızca hangi bileşenden kaç puan geldiğini bildirir;
katılımcının göreceği Türkçe cümle arayüz katmanında kalıplardan üretilir
(Aşama 9). Sayı katılımcıya hiç gösterilmez (M8, Bölüm 13).
"""

from engine.scoring import SynergyModel
from engine.state import PlanState
from engine.types import PairReason


def build_reasons(state: PlanState, model: SynergyModel) -> tuple[PairReason, ...]:
    """Aynı masada oturan her ikili için skor kırılımı.

    Sıra sabit (slot, masa, küçük indeks, büyük indeks) — determinizm çıktıda da
    görünmeli (5.3). İkili her zaman kanonik sırada; veritabanı tarafında da
    `registration_a_id < registration_b_id` kısıtı var.
    """
    reasons: list[PairReason] = []

    for slot in range(state.slot_count):
        for table in range(state.table_count):
            occupants = sorted(state.seats[slot][table])
            for position, first in enumerate(occupants):
                for second in occupants[position + 1 :]:
                    reasons.append(
                        PairReason(
                            slot=slot,
                            participant_a=first,
                            participant_b=second,
                            total_score=model.score(first, second),
                            components=model.explain(first, second),
                        )
                    )

    return tuple(reasons)
