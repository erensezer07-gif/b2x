"""Minimum değişim modu (şartname 9.8) ve 9.10'un kalan testleri.

Check-in sonrası yeniden çalıştırmanın tek amacı var: *"gerekmedikçe kimseyi
kıpırdatma, sadece delik açılan masaları onar."* Motor sıfırdan çalışırsa dün
akşam masasını öğrenmiş olan kişi sabah bambaşka bir yere düşer ve kapıda kaos
çıkar (9.8).
"""

from collections import Counter
from dataclasses import replace

import pytest

from engine.rules import find_violations
from engine.runner import run_matching
from engine.synthetic import ScenarioSpec, build_scenario
from engine.types import EngineInput, EngineOutput, EngineSettings, FixedAssignment

BUDGET = 6_000


def base_scenario(**overrides) -> EngineInput:
    spec = ScenarioSpec(participant_count=100, slot_count=6, table_count=25, **overrides)
    return build_scenario(spec, settings=EngineSettings(max_iterations=BUDGET))


def assert_valid(engine_input: EngineInput, output: EngineOutput) -> None:
    violations = find_violations(engine_input, output.assignments)
    assert not violations, "Kesin kural ihlali:\n" + "\n".join(
        str(violation) for violation in violations
    )


def seats_of(output: EngineOutput) -> dict[tuple[int, int], int]:
    return {(row.slot, row.participant): row.table for row in output.assignments}


def moved_participants(first: EngineOutput, second: EngineOutput) -> set[int]:
    """İki plan arasında herhangi bir turda yeri değişen kişiler."""
    before = seats_of(first)
    after = seats_of(second)
    changed = set()
    for key in before.keys() | after.keys():
        if before.get(key) != after.get(key):
            changed.add(key[1])
    return changed


# --- 9.10 minimum değişim testi --------------------------------------------


def test_removing_ten_people_moves_only_a_few_others() -> None:
    """Yüz kişilik plandan on kişi çıkarıldığında yeri değişen kişi sayısı makul
    bir sınırın altında kalmalı (9.10).

    "Makul" burada: gelmeyenler dışında kalan doksan kişinin çoğu yerinde
    kalmalı. Sıfırdan çalıştırma bu sayıyı doksana yaklaştırırdı.
    """
    original = base_scenario()
    first = run_matching(original)

    absentees = frozenset(range(10))
    rerun = replace(
        original,
        previous_plan=first.assignments,
        absent_participants=absentees,
    )
    second = run_matching(rerun)
    assert_valid(rerun, second)

    disturbed = moved_participants(first, second) - absentees
    assert len(disturbed) < 30, (
        f"gelmeyenler dışında {len(disturbed)} kişinin yeri değişti — "
        f"minimum değişim modu işini yapmıyor"
    )


def test_absentees_are_never_seated() -> None:
    original = base_scenario()
    first = run_matching(original)

    absentees = frozenset({3, 17, 42})
    rerun = replace(original, previous_plan=first.assignments, absent_participants=absentees)
    second = run_matching(rerun)

    seated = {row.participant for row in second.assignments}
    assert not (seated & absentees)


def test_rerun_without_absentees_barely_changes_the_plan() -> None:
    """Kimse eksilmediyse motorun kıpırdatacak bir şeyi yok."""
    original = base_scenario()
    first = run_matching(original)

    rerun = replace(original, previous_plan=first.assignments)
    second = run_matching(rerun)

    assert_valid(rerun, second)
    assert len(moved_participants(first, second)) < 10


def test_absentees_are_not_reported_as_unmatched() -> None:
    """Gelmeyen biri "eşleştirilemedi" sayılmamalı — etkinliğe katılmadı."""
    original = base_scenario()
    first = run_matching(original)

    absentees = frozenset(range(10))
    rerun = replace(original, previous_plan=first.assignments, absent_participants=absentees)
    second = run_matching(rerun)

    assert not (set(second.summary.unmatched_participants) & absentees)
    assert not (set(second.summary.participants_below_target) & absentees)


def test_summary_reports_who_moved() -> None:
    """Organizatöre "kimin yeri değişti" gösterilecek (9.8, M10)."""
    original = base_scenario()
    first = run_matching(original)

    rerun = replace(
        original, previous_plan=first.assignments, absent_participants=frozenset(range(10))
    )
    second = run_matching(rerun)
    assert second.summary.moved_participants > 0


# --- Dondurulmuş slotlar ---------------------------------------------------


def test_started_slots_are_frozen() -> None:
    """Başlamış slotlara hiç dokunulmaz (9.8)."""
    original = base_scenario()
    first = run_matching(original)

    frozen = frozenset({0, 1})
    rerun = replace(
        original,
        previous_plan=first.assignments,
        frozen_slots=frozen,
        absent_participants=frozenset(range(10)),
    )
    second = run_matching(rerun)
    assert_valid(rerun, second)

    def frozen_rows(output: EngineOutput) -> set[tuple[int, int, int]]:
        return {
            (row.slot, row.table, row.participant)
            for row in output.assignments
            if row.slot in frozen
        }

    assert frozen_rows(first) == frozen_rows(second)


def test_freezing_without_a_previous_plan_is_rejected() -> None:
    engine_input = replace(base_scenario(), frozen_slots=frozenset({0}))
    with pytest.raises(ValueError, match="önceki plan"):
        run_matching(engine_input)


def test_fixed_assignments_still_win_in_minimal_change_mode() -> None:
    original = base_scenario()
    first = run_matching(original)

    anchor = original.participants[50]
    partner = next(p for p in original.participants if p.company != anchor.company)
    rerun = replace(
        original,
        previous_plan=first.assignments,
        fixed_assignments=(
            FixedAssignment(slot=2, table=7, participant=anchor.index),
            FixedAssignment(slot=2, table=7, participant=partner.index),
        ),
    )
    second = run_matching(rerun)

    assert_valid(rerun, second)
    seats = seats_of(second)
    assert seats[(2, anchor.index)] == 7
    assert seats[(2, partner.index)] == 7


# --- 9.10 kalite testleri --------------------------------------------------


def test_most_tables_clear_the_quality_threshold() -> None:
    """Hiçbir masada eşiğin **çok** altında bir ikili olmamalı (9.10).

    Adım 5 kuyrukta kalanlar için eşiği bilerek esnetiyor (9.6), bu yüzden kesin
    bir alt sınır iddia edilemez. Ölçülebilir olan şu: masaların çoğunluğu eşiği
    geçmeli, yoksa skorlama işe yaramıyor demektir.
    """
    engine_input = base_scenario()
    output = run_matching(engine_input)

    table_of = seats_of(output)
    weakest: dict[tuple[int, int], float] = {}
    for reason in output.reasons:
        key = (reason.slot, table_of[(reason.slot, reason.participant_a)])
        weakest[key] = min(weakest.get(key, 1.0), reason.total_score)

    assert weakest, "hiç masa kurulmamış"
    threshold = engine_input.settings.quality_threshold
    clearing = sum(1 for score in weakest.values() if score >= threshold)
    assert clearing / len(weakest) > 0.5


def test_everyone_reaches_the_minimum_rounds() -> None:
    """Adalet kuralı (9.6): herkes asgari tur sayısına ulaşmalı."""
    engine_input = base_scenario()
    output = run_matching(engine_input)
    assert output.summary.participants_below_target == ()


# --- 9.10 kalan zor senaryo ------------------------------------------------


def test_every_table_has_an_anchor() -> None:
    """Tüm masalar çapa kişili (9.10).

    Her masaya birer sabit atama konur; motor kalanları onların etrafına
    yerleştirmeli ve hiçbirini oynatmamalı.
    """
    base = build_scenario(
        ScenarioSpec(participant_count=60, slot_count=3, table_count=10),
        settings=EngineSettings(max_iterations=BUDGET),
    )
    anchors = tuple(FixedAssignment(slot=0, table=table, participant=table) for table in range(10))
    engine_input = replace(base, fixed_assignments=anchors)

    output = run_matching(engine_input)
    assert_valid(engine_input, output)

    seats = seats_of(output)
    for anchor in anchors:
        assert seats[(0, anchor.participant)] == anchor.table


def test_plan_stays_valid_when_almost_everyone_is_absent() -> None:
    original = base_scenario()
    first = run_matching(original)

    rerun = replace(
        original,
        previous_plan=first.assignments,
        absent_participants=frozenset(range(97)),
    )
    second = run_matching(rerun)
    assert_valid(rerun, second)

    # Geriye üç kişi kaldı: en fazla bir masa kurulabilir, tek kişilik masa olamaz.
    sizes = Counter((row.slot, row.table) for row in second.assignments)
    assert all(size >= 2 for size in sizes.values())
