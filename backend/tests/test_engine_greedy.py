"""Açgözlü başlangıcın kesin kurallara uyduğunun kanıtı (şartname 9.10).

Şartnamenin kesin kural testleri burada, üretilen planlar üzerinde koşuyor:
aynı şirketten iki kişi aynı masada değil, kapasite aşılmıyor, tek kişilik masa
yok, hiçbir ikili iki slotta karşılaşmıyor, kimse aynı slotta iki masada değil,
sabit atamalar korunmuş.

Denetim `engine.rules.find_violations` ile yapılıyor — motorun içindeki artımlı
kontrolden bağımsız, ikinci bir göz.
"""

import pytest

from engine.greedy import build_initial_plan
from engine.rules import find_violations
from engine.scoring import build_synergy_model
from engine.state import PlanState
from engine.synthetic import ScenarioSpec, build_scenario
from engine.types import EngineInput, EngineSettings, FixedAssignment


def run_greedy(engine_input: EngineInput) -> PlanState:
    model = build_synergy_model(engine_input)
    return build_initial_plan(engine_input, model)


def assert_valid(engine_input: EngineInput, state: PlanState) -> None:
    violations = find_violations(engine_input, state.assignments())
    assert not violations, "Kesin kural ihlali:\n" + "\n".join(
        str(violation) for violation in violations
    )


# --- Kesin kural testleri ---------------------------------------------------


def test_typical_scenario_breaks_no_hard_rule() -> None:
    engine_input = build_scenario(ScenarioSpec())
    assert_valid(engine_input, run_greedy(engine_input))


def test_many_slots_still_break_no_hard_rule() -> None:
    """Slot sayısı arttıkça "tekrar yok" kuralı asıl baskıyı kurar."""
    engine_input = build_scenario(ScenarioSpec(slot_count=8, participant_count=80))
    assert_valid(engine_input, run_greedy(engine_input))


def test_fixed_assignments_are_preserved() -> None:
    base = build_scenario(ScenarioSpec(participant_count=40, table_count=8))
    # Farklı şirketlerden iki kişiyi aynı masaya sabitle.
    first = base.participants[0]
    second = next(person for person in base.participants if person.company != first.company)
    engine_input = EngineInput(
        participants=base.participants,
        tables=base.tables,
        slot_count=base.slot_count,
        requests=base.requests,
        fixed_assignments=(
            FixedAssignment(slot=0, table=3, participant=first.index),
            FixedAssignment(slot=0, table=3, participant=second.index),
        ),
        settings=base.settings,
    )

    state = run_greedy(engine_input)
    assert_valid(engine_input, state)

    occupants = state.occupants(0, 3)
    assert first.index in occupants
    assert second.index in occupants


def test_conflicting_fixed_assignments_raise() -> None:
    """Aynı şirketten iki kişi aynı masaya sabitlenirse sessizce düzeltilmez."""
    base = build_scenario(ScenarioSpec(participant_count=20, company_count=1))
    engine_input = EngineInput(
        participants=base.participants,
        tables=base.tables,
        slot_count=base.slot_count,
        fixed_assignments=(
            FixedAssignment(slot=0, table=0, participant=0),
            FixedAssignment(slot=0, table=0, participant=1),
        ),
        settings=base.settings,
    )
    with pytest.raises(ValueError, match="Sabit atama"):
        run_greedy(engine_input)


# --- Zor senaryolar (9.10) --------------------------------------------------


def test_single_company_leaves_everyone_unseated() -> None:
    """Herkes aynı şirketten: şirket ayrımı kuralı hiçbir masaya izin vermez.

    Motor kilitlenmemeli, boş ama geçerli bir plan üretmeli.
    """
    engine_input = build_scenario(ScenarioSpec(participant_count=30, company_count=1))
    state = run_greedy(engine_input)
    assert_valid(engine_input, state)
    assert state.assignments() == ()


def test_more_participants_than_capacity() -> None:
    engine_input = build_scenario(
        ScenarioSpec(participant_count=200, table_count=5, seats_per_table=4)
    )
    state = run_greedy(engine_input)
    assert_valid(engine_input, state)
    # Kapasite 5×4=20; bir slotta bundan fazlası oturamaz.
    for slot in range(engine_input.slot_count):
        seated = sum(len(state.occupants(slot, table)) for table in range(5))
        assert seated <= 20


def test_far_fewer_participants_than_capacity() -> None:
    engine_input = build_scenario(
        ScenarioSpec(participant_count=5, table_count=20, seats_per_table=8)
    )
    assert_valid(engine_input, run_greedy(engine_input))


def test_odd_participant_count() -> None:
    """Tek sayıda katılımcı — artan kişi tek başına masada bırakılmamalı."""
    engine_input = build_scenario(
        ScenarioSpec(participant_count=7, table_count=3, seats_per_table=2, slot_count=1)
    )
    assert_valid(engine_input, run_greedy(engine_input))


def test_nobody_is_compatible() -> None:
    """Sunulan ve aranan etiket havuzları tamamen ayrık.

    Kalite eşiği hiçbir ikiliye izin vermemeli; boş sandalye kötü eşleşmeden
    iyidir (9.5).
    """
    engine_input = build_scenario(
        ScenarioSpec(participant_count=40, compatibility=0.0, sector_count=40, city_count=40)
    )
    state = run_greedy(engine_input)
    assert_valid(engine_input, state)
    assert state.assignments() == ()


def test_everyone_is_highly_compatible() -> None:
    engine_input = build_scenario(
        ScenarioSpec(
            participant_count=60,
            tag_count=4,
            offered_per_person=2,
            sought_per_person=2,
            sector_count=1,
            city_count=1,
        )
    )
    state = run_greedy(engine_input)
    assert_valid(engine_input, state)
    assert state.assignments() != ()


def test_standing_tables_respect_upper_bound() -> None:
    engine_input = build_scenario(ScenarioSpec(standing_tables=True))
    assert_valid(engine_input, run_greedy(engine_input))


def test_requests_do_not_break_hard_rules() -> None:
    engine_input = build_scenario(ScenarioSpec(request_count=40))
    assert_valid(engine_input, run_greedy(engine_input))


# --- Determinizm (şartname 5.3) ---------------------------------------------


def test_same_seed_produces_identical_plan() -> None:
    spec = ScenarioSpec(participant_count=50, slot_count=5)
    first = run_greedy(build_scenario(spec)).assignments()
    second = run_greedy(build_scenario(spec)).assignments()
    assert first == second
    assert first != ()


# --- Kalite eşiği -----------------------------------------------------------


def test_no_seated_pair_falls_below_threshold() -> None:
    """9.10 kalite testi: hiçbir masada eşiğin çok altında bir ikili olmamalı.

    Açgözlü aşamada eşik hiç esnetilmez, dolayısıyla burada kesin eşitsizlik
    beklenebilir. Adım 5 devreye girdiğinde bu test gevşetilecek.
    """
    settings = EngineSettings(quality_threshold=0.4)
    engine_input = build_scenario(ScenarioSpec(participant_count=60), settings=settings)
    state = run_greedy(engine_input)

    for slot in range(state.slot_count):
        for table in range(state.table_count):
            occupants = state.occupants(slot, table)
            for position, first in enumerate(occupants):
                for second in occupants[position + 1 :]:
                    assert state.score[first, second] >= settings.quality_threshold
