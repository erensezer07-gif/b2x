"""Motorun uçtan uca davranışı — Adım 1'den 6'ya (şartname 9.7, 9.10).

Açgözlü aşamanın kesin kural testleri `test_engine_greedy.py` içinde. Buradaki
testler yerel arama, adalet düzeltmesi ve gerekçe üretimi eklendikten sonra
planın hâlâ geçerli olduğunu ve şartnamenin kalite vaatlerini tuttuğunu
doğruluyor.

Testlerde deneme bütçesi bilerek küçük: amaç aramanın *yönünü* sınamak, en iyi
planı bulmasını beklemek değil.
"""

import random
from collections import Counter

import pytest

from engine.greedy import build_initial_plan
from engine.local_search import optimise
from engine.rules import find_violations
from engine.runner import run_matching, run_matching_with_trace
from engine.scoring import build_synergy_model
from engine.synthetic import ScenarioSpec, build_scenario, with_single_outsider_sector
from engine.types import EngineInput, EngineOutput, EngineSettings, FixedAssignment

SMALL_BUDGET = 4_000


def scenario(spec: ScenarioSpec | None = None, **settings_overrides) -> EngineInput:
    settings = EngineSettings(max_iterations=SMALL_BUDGET, **settings_overrides)
    return build_scenario(spec or ScenarioSpec(), settings=settings)


def assert_valid(engine_input: EngineInput, output: EngineOutput) -> None:
    violations = find_violations(engine_input, output.assignments)
    assert not violations, "Kesin kural ihlali:\n" + "\n".join(
        str(violation) for violation in violations
    )


# --- Kesin kurallar, tam boru hattı sonrası --------------------------------


def test_full_run_breaks_no_hard_rule() -> None:
    engine_input = scenario()
    assert_valid(engine_input, run_matching(engine_input))


def test_full_run_with_many_slots_breaks_no_hard_rule() -> None:
    """Slot arttıkça "tekrar yok" kuralı asıl baskıyı kurar."""
    engine_input = scenario(ScenarioSpec(participant_count=80, slot_count=8, table_count=16))
    assert_valid(engine_input, run_matching(engine_input))


def test_fixed_assignments_survive_the_whole_pipeline() -> None:
    """Yerel arama sabit atamaları oynatamaz (9.5)."""
    base = build_scenario(ScenarioSpec(participant_count=40, table_count=8))
    first = base.participants[0]
    second = next(p for p in base.participants if p.company != first.company)

    engine_input = EngineInput(
        participants=base.participants,
        tables=base.tables,
        slot_count=base.slot_count,
        fixed_assignments=(
            FixedAssignment(slot=0, table=2, participant=first.index),
            FixedAssignment(slot=0, table=2, participant=second.index),
        ),
        settings=EngineSettings(max_iterations=SMALL_BUDGET),
    )

    output = run_matching(engine_input)
    assert_valid(engine_input, output)

    seats = {(row.slot, row.participant): row.table for row in output.assignments if row.slot == 0}
    assert seats[(0, first.index)] == 2
    assert seats[(0, second.index)] == 2


# --- Adım 4: yerel arama iyileştiriyor mu ----------------------------------


def test_local_search_improves_the_objective() -> None:
    engine_input = scenario(ScenarioSpec(participant_count=60, slot_count=5))
    _, trace = run_matching_with_trace(engine_input)

    assert trace.search.applied > 0, "hiç geçerli hamle üretilememiş"
    assert trace.search.objective_after >= trace.search.objective_before


def test_local_search_never_leaves_a_single_occupant_table() -> None:
    """Arama sonrası plan, temizliğe gerek kalmadan geçerli olmalı.

    Aksi hâlde arama insanları boş masalara yalnız park edip adalet skorunu
    şişiriyor, sondaki temizlik de onları silince kişiler hedefin altına
    düşüyordu. Amaç fonksiyonu bunu göremez: tek kişilik masa "kullanılmıyor"
    sayılır, cezası yoktur.
    """
    engine_input = scenario(ScenarioSpec(participant_count=80, slot_count=6, table_count=25))
    model = build_synergy_model(engine_input)
    state = build_initial_plan(engine_input, model)
    optimise(state, random.Random(engine_input.settings.seed))

    singles = [
        (slot, table)
        for slot in range(state.slot_count)
        for table in range(state.table_count)
        if len(state.seats[slot][table]) == 1
    ]
    assert not singles, f"tek kişilik masa bırakılmış: {singles[:5]}"


def test_cleanup_does_not_push_anyone_below_target() -> None:
    """Özet ile Adım 5 raporu aynı planı anlatmalı.

    Temizlik kimseyi masadan çıkarmıyorsa iki sayı da aynı olur.
    """
    engine_input = scenario(ScenarioSpec(participant_count=80, slot_count=6, table_count=20))
    output, trace = run_matching_with_trace(engine_input)
    assert len(output.summary.participants_below_target) == trace.fairness.below_target_after


def test_local_search_fills_tables_beyond_greedy() -> None:
    """Açgözlü aşama çoğunlukla ikişer kişilik masa bırakır; arama büyütmeli."""
    engine_input = scenario(ScenarioSpec(participant_count=80, slot_count=5, table_count=20))
    output = run_matching(engine_input)

    sizes = Counter(Counter((r.slot, r.table) for r in output.assignments).values())
    assert sum(count for size, count in sizes.items() if size >= 4) > 0


# --- Adım 5: adalet --------------------------------------------------------


def test_fairness_step_reduces_the_backlog() -> None:
    engine_input = scenario(ScenarioSpec(participant_count=80, slot_count=6, table_count=20))
    _, trace = run_matching_with_trace(engine_input)

    assert trace.fairness.below_target_after <= trace.fairness.below_target_before


def test_minority_sector_is_not_abandoned() -> None:
    """9.6'daki başarısızlık hikâyesinin uç hâli: bir kişi hariç herkes aynı
    sektörde. O kişi boş masada oturuyor kalmamalı."""
    base = build_scenario(
        ScenarioSpec(participant_count=60, slot_count=5, table_count=15),
        settings=EngineSettings(max_iterations=SMALL_BUDGET),
    )
    engine_input = with_single_outsider_sector(base)

    output = run_matching(engine_input)
    assert_valid(engine_input, output)

    rounds = Counter(row.participant for row in output.assignments)
    assert rounds[0] > 0, "azınlıktaki kişi hiç oturmamış"


def test_summary_reports_who_is_still_below_target() -> None:
    """Hedef tutturulamıyorsa sessizce geçilmez, raporlanır (9.6)."""
    # Kapasite bilerek yetersiz: 3 masa × 2 sandalye, 40 kişi.
    engine_input = scenario(
        ScenarioSpec(participant_count=40, slot_count=2, table_count=3, seats_per_table=2)
    )
    output = run_matching(engine_input)

    assert_valid(engine_input, output)
    assert len(output.summary.participants_below_target) > 0
    assert output.summary.min_meetings_per_person < 4


# --- Adım 6: gerekçeler ----------------------------------------------------


def test_every_seated_pair_has_exactly_one_reason() -> None:
    engine_input = scenario(ScenarioSpec(participant_count=50, slot_count=4))
    output = run_matching(engine_input)

    expected_pairs = 0
    by_table: dict[tuple[int, int], int] = Counter(
        (row.slot, row.table) for row in output.assignments
    )
    for size in by_table.values():
        expected_pairs += size * (size - 1) // 2

    assert len(output.reasons) == expected_pairs


def test_reasons_use_canonical_pair_order() -> None:
    """Veritabanında `registration_a_id < registration_b_id` kısıtı var."""
    output = run_matching(scenario(ScenarioSpec(participant_count=40, slot_count=3)))
    for reason in output.reasons:
        assert reason.participant_a < reason.participant_b


def test_reasons_carry_the_component_breakdown() -> None:
    output = run_matching(scenario(ScenarioSpec(participant_count=40, slot_count=3)))
    assert output.reasons, "hiç gerekçe üretilmemiş"

    for reason in output.reasons[:50]:
        assert reason.components, "kırılım boş"
        assert 0.0 <= reason.total_score <= 1.0


# --- Özet ------------------------------------------------------------------


def test_summary_matches_the_assignments() -> None:
    engine_input = scenario(ScenarioSpec(participant_count=60, slot_count=4))
    output = run_matching(engine_input)
    summary = output.summary

    rounds = Counter(row.participant for row in output.assignments)
    assert summary.total_meetings == len(output.assignments)
    assert summary.min_meetings_per_person == min(
        rounds.get(index, 0) for index in range(len(engine_input.participants))
    )
    unmatched = {index for index in range(len(engine_input.participants)) if index not in rounds}
    assert set(summary.unmatched_participants) == unmatched
    assert summary.total_requests == len(engine_input.requests)
    assert summary.runtime_ms >= 0


# --- Determinizm (şartname 5.3) --------------------------------------------


def test_same_seed_produces_identical_output() -> None:
    spec = ScenarioSpec(participant_count=60, slot_count=5)

    first = run_matching(scenario(spec))
    second = run_matching(scenario(spec))

    assert first.assignments == second.assignments
    assert [r.total_score for r in first.reasons] == [r.total_score for r in second.reasons]
    assert first.summary.total_meetings == second.summary.total_meetings


def test_different_seed_produces_a_different_plan() -> None:
    spec = ScenarioSpec(participant_count=60, slot_count=5)
    first = run_matching(scenario(spec, seed=1))
    second = run_matching(scenario(spec, seed=2))
    assert first.assignments != second.assignments


# --- Uç durumlar -----------------------------------------------------------


def test_no_participants_does_not_crash() -> None:
    engine_input = EngineInput(
        participants=(),
        tables=build_scenario(ScenarioSpec()).tables,
        slot_count=3,
        settings=EngineSettings(max_iterations=SMALL_BUDGET),
    )
    output = run_matching(engine_input)
    assert output.assignments == ()
    assert output.reasons == ()


def test_single_company_stays_empty_but_valid() -> None:
    engine_input = scenario(ScenarioSpec(participant_count=30, company_count=1))
    output = run_matching(engine_input)
    assert_valid(engine_input, output)
    assert output.assignments == ()


def test_invalid_input_is_rejected_early() -> None:
    base = build_scenario(ScenarioSpec(participant_count=10))
    broken = EngineInput(
        participants=base.participants[1:],  # indeksler artık 0'dan başlamıyor
        tables=base.tables,
        slot_count=2,
    )
    with pytest.raises(ValueError, match="indeks"):
        run_matching(broken)
