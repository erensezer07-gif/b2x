"""Minimum değişim modu (şartname 9.8).

Check-in sonrası yeniden çalıştırmada kullanılır.

*"Motor sıfırdan çalışırsa herkesin planı değişir. Dün akşam masasını öğrenmiş
olan kişi sabah bambaşka bir yere düşer. Kapıda kaos çıkar."*

Fark: **Adım 3 (açgözlü başlangıç) atlanır.** Önceki plan başlangıç noktası olur;
gelmeyenler çıkarılır, boşluklar oluşur, Adım 4 doğrudan bu plan üzerinde çalışır.

Ve amaç fonksiyonuna ceza terimi eklenir: **yeri değişen her yerleşim için
ceza.** Katsayı yüksek tutulur (`EngineSettings.move_penalty`), böylece motor
"gerekmedikçe kimseyi kıpırdatma, sadece delik açılan masaları onar" davranışı
sergiler. Bu terim `PlanState.objective()` içinde, önceki plan verildiğinde
kendiliğinden devreye girer.

## Dondurulmuş slotlar

Başlamış veya bitmiş slotlar tamamen dondurulur. İçerikleri önceki plandan
olduğu gibi alınır ve hiç değiştirilmez — gelmeyenler bile çıkarılmaz. O turlar
gerçekten yaşandı; kaydı sonradan düzenlemek geçmişi değiştirmek olurdu.

## Asgari grup

Bu modda da geçerli: bir masada tek kişi kaldıysa o kişi masadan çıkarılır
(9.8). Dondurulmuş slotlara dokunulmaz.
"""

from engine.greedy import place_fixed_assignments
from engine.scoring import SynergyModel
from engine.state import UNSEATED, PlanState
from engine.types import EngineInput


def build_plan_from_previous(engine_input: EngineInput, model: SynergyModel) -> PlanState:
    """Önceki planı başlangıç noktası yapar (Adım 2 + 9.8, Adım 3 atlanır)."""
    if engine_input.previous_plan is None:
        raise ValueError("Minimum değişim modu önceki plan olmadan çalıştırılamaz.")

    state = PlanState(engine_input, model)

    # Adım 2 yine ilk sırada: çapa kişiler ve kilitli atamalar önceki plandan
    # bağımsız olarak yerine konur ve dokunulmaz işaretlenir.
    place_fixed_assignments(state)

    _replay_previous_plan(state)
    state.drop_single_occupant_tables()
    return state


def _replay_previous_plan(state: PlanState) -> None:
    """Önceki planı kurar; gelmeyenleri atlar, dondurulmuş slotları aynen alır."""
    assert state.input.previous_plan is not None

    for assignment in sorted(
        state.input.previous_plan,
        key=lambda row: (row.slot, row.table, row.participant),
    ):
        frozen = assignment.slot in state.input.frozen_slots

        if not frozen and state.absent[assignment.participant]:
            # Gelmedi: yeri boşalır, delik Adım 4'te onarılır.
            continue

        if state.location[assignment.slot, assignment.participant] != UNSEATED:
            # Sabit atama bu kişiyi zaten başka bir yere koymuş olabilir;
            # kilitli atama önceki planı ezer (9.5).
            continue

        if frozen:
            # Dondurulmuş slot geçmişin kaydı: kural kontrolü yapılmadan aynen
            # kurulur, sonra hiç değiştirilmez.
            state.seat(assignment.slot, assignment.table, assignment.participant)
            continue

        if state.can_seat(assignment.slot, assignment.table, assignment.participant):
            state.seat(assignment.slot, assignment.table, assignment.participant)
