"""Motorun giriş noktası — Adım 1'den 6'ya (şartname 9.7).

```
Adım 1  skor matrisi              scoring.build_synergy_model
Adım 2  sabit atamalar            greedy.place_fixed_assignments
Adım 3  açgözlü başlangıç         greedy.fill_greedily
Adım 4  yerel arama               local_search.optimise
Adım 5  adalet düzeltmesi         fairness.repair_fairness
Adım 6  gerekçe üretimi           reasons.build_reasons
```

Sıra şartnamedeki sıradır. Adım 5 kalite eşiğini esneterek kuyrukta kalanları
toplar; ondan sonra tekrar yerel arama çalıştırılmaz, çünkü 9.7 böyle bir adım
tarif etmiyor ve arama Adım 5'in yerleştirdiklerini geri sökebilirdi.

Motor buraya kadar hiçbir yerde veritabanı, HTTP veya uygulama katmanı görmez
(5.1). Girdi sade veri yapıları, çıktı sade veri yapıları.
"""

import random
import time
from dataclasses import dataclass

from engine.fairness import FairnessReport, repair_fairness
from engine.greedy import build_initial_plan
from engine.local_search import SearchReport, optimise
from engine.minimal_change import build_plan_from_previous
from engine.reasons import build_reasons
from engine.scoring import build_synergy_model
from engine.state import PlanState
from engine.types import EngineInput, EngineOutput, EngineSummary


@dataclass(frozen=True, slots=True)
class RunTrace:
    """Adımların ne kadar sürdüğü ve ne yaptığı — ayar yaparken bakılır.

    Ürün akışının parçası değil; `run_matching` bunu döndürmez.
    """

    scoring_ms: int
    greedy_ms: int
    search_ms: int
    fairness_ms: int
    reasons_ms: int
    search: SearchReport
    fairness: FairnessReport


def run_matching(engine_input: EngineInput) -> EngineOutput:
    """Eşleştirmeyi çalıştırır ve planı döndürür."""
    output, _ = run_matching_with_trace(engine_input)
    return output


def run_matching_with_trace(
    engine_input: EngineInput,
) -> tuple[EngineOutput, RunTrace]:
    """`run_matching` ile aynı, ek olarak adım adım ölçüm döndürür."""
    engine_input.validate()
    started = time.perf_counter()

    step_started = time.perf_counter()
    model = build_synergy_model(engine_input)
    scoring_ms = _elapsed_ms(step_started)

    step_started = time.perf_counter()
    if engine_input.previous_plan is None:
        state = build_initial_plan(engine_input, model)
    else:
        # 9.8 minimum değişim modu: Adım 3 atlanır, önceki plan başlangıç olur.
        state = build_plan_from_previous(engine_input, model)
    greedy_ms = _elapsed_ms(step_started)

    # Tohum ayarlardan gelir: aynı girdi + aynı tohum = birebir aynı çıktı (5.3).
    rng = random.Random(engine_input.settings.seed)

    step_started = time.perf_counter()
    search = optimise(state, rng)
    search_ms = _elapsed_ms(step_started)

    step_started = time.perf_counter()
    fairness = repair_fairness(state)
    # Adalet düzeltmesi tek kişilik masa bırakmaz ama plan her hâlükârda
    # denetlenir: asgari grup kuralı kesin (9.5).
    state.drop_single_occupant_tables()
    fairness_ms = _elapsed_ms(step_started)

    step_started = time.perf_counter()
    reasons = build_reasons(state, model)
    reasons_ms = _elapsed_ms(step_started)

    output = EngineOutput(
        assignments=state.assignments(),
        reasons=reasons,
        summary=build_summary(state, _elapsed_ms(started)),
    )
    trace = RunTrace(
        scoring_ms=scoring_ms,
        greedy_ms=greedy_ms,
        search_ms=search_ms,
        fairness_ms=fairness_ms,
        reasons_ms=reasons_ms,
        search=search,
        fairness=fairness,
    )
    return output, trace


def build_summary(state: PlanState, runtime_ms: int) -> EngineSummary:
    """Özet (9.2).

    "Görüşme" birimi turdur: `total_meetings` toplam oturma sayısı,
    `min_meetings_per_person` en az turda oturan kişinin tur sayısı.

    **Gelmeyenler asgari tur hesabına girmiyor** (M7). Girseydi check-in
    sonrası her planda bu sayı sıfır olurdu — gelmemiş birinin sıfır turu
    motorun başarısızlığı değil ve panelin en önemli sayısı hiçbir şey
    anlatmaz olurdu.
    """
    table_scores = state.used_table_scores()
    present = state.rounds[~state.absent]
    return EngineSummary(
        total_meetings=int(state.rounds.sum()) if state.participant_count else 0,
        min_meetings_per_person=int(present.min()) if present.size else 0,
        participants_below_target=state.participants_below_target(),
        unmatched_participants=state.unmatched_participants(),
        satisfied_requests=state.satisfied_requests(),
        total_requests=len(state.input.requests),
        average_table_score=(sum(table_scores) / len(table_scores) if table_scores else 0.0),
        moved_participants=len(state.moved_participants()),
        runtime_ms=runtime_ms,
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
