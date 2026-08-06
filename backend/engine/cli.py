"""Motoru terminalden çalıştırır (şartname 5.1, Aşama 2).

*"Sentetik katılımcı üretip motoru terminalden çalıştırabilirsin. Uygulamayı
açmadan yüzlerce senaryo denenebilir."*

Kullanım:

    python -m engine.cli
    python -m engine.cli --katilimci 200 --slot 8 --masa 50 --sandalye 6
    python -m engine.cli --deneme 200000 --esik 0.30

Rapor yalnızca motorun **dışa açılan sözleşmesini** kullanır (`run_matching`
çıktısı). Böylece sözleşmenin bir planı anlatmaya yetip yetmediği de sınanmış
oluyor — Aşama 7'de uygulama katmanı aynı verilerle çalışacak.
"""

import argparse
from collections import Counter
from dataclasses import replace

import numpy as np

from engine.rules import find_violations
from engine.runner import RunTrace, run_matching_with_trace
from engine.scoring import build_synergy_model
from engine.synthetic import ScenarioSpec, build_scenario
from engine.types import EngineInput, EngineOutput, EngineSettings
from engine.weights import DEFAULT_WEIGHTS

PERCENTILES = (10, 25, 50, 75, 90, 99)
RULE_REPORT_LIMIT = 20


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="engine.cli",
        description="B2X eşleştirme motorunu sentetik veriyle çalıştırır.",
    )
    parser.add_argument("--katilimci", type=int, default=200, help="katılımcı sayısı")
    parser.add_argument("--slot", type=int, default=8, help="slot (tur) sayısı")
    parser.add_argument("--masa", type=int, default=50, help="masa sayısı")
    parser.add_argument("--sandalye", type=int, default=6, help="masa başına sandalye")
    parser.add_argument("--sirket", type=int, default=80, help="şirket sayısı")
    parser.add_argument("--sektor", type=int, default=12, help="sektör sayısı")
    parser.add_argument("--sehir", type=int, default=8, help="şehir sayısı")
    parser.add_argument("--etiket", type=int, default=40, help="etiket havuzu genişliği")
    parser.add_argument("--alan", type=int, default=5, help="etiket havuzundaki ilgi alanı sayısı")
    parser.add_argument("--secim", type=int, default=4, help="kişi başına sunulan/aranan etiket")
    parser.add_argument("--kategori", type=int, default=6, help="etiket kategorisi sayısı")
    parser.add_argument(
        "--kategori-puani",
        type=float,
        default=None,
        help="kategori düzeyinde kısmi puan katsayısı (0 = kapalı)",
    )
    parser.add_argument("--talep", type=int, default=150, help="görüşme talebi sayısı")
    parser.add_argument(
        "--uyum", type=float, default=1.0, help="0.0 kimse kimseye uymaz, 1.0 eşleşme bol"
    )
    parser.add_argument("--esik", type=float, default=0.35, help="kalite eşiği")
    parser.add_argument("--asgari-tur", type=int, default=4, help="kişi başı asgari tur")
    parser.add_argument("--deneme", type=int, default=100_000, help="yerel arama deneme sayısı")
    parser.add_argument("--tohum", type=int, default=42, help="rastgelelik tohumu")
    parser.add_argument("--ayakli", action="store_true", help="ayaklı masa kullan")
    return parser


def _distribution(values: np.ndarray, digits: int = 3) -> str:
    if values.size == 0:
        return "veri yok"
    percentiles = np.percentile(values, PERCENTILES)
    parts = [
        f"%{percentile}={value:.{digits}f}"
        for percentile, value in zip(PERCENTILES, percentiles, strict=True)
    ]
    return (
        f"en düşük={values.min():.{digits}f}  "
        + "  ".join(parts)
        + f"  en yüksek={values.max():.{digits}f}"
    )


def _counter_line(counts: Counter[int]) -> str:
    """Küçük tam sayı dağılımlarını "değer→adet" biçiminde özetler."""
    if not counts:
        return "veri yok"
    return "  ".join(f"{value}→{counts[value]}" for value in sorted(counts))


def _table_scores(output: EngineOutput) -> np.ndarray:
    """Masa skorlarını çıktıdan türetir: masadaki en zayıf ikili bağ (9.4)."""
    table_of: dict[tuple[int, int], int] = {
        (row.slot, row.participant): row.table for row in output.assignments
    }
    weakest: dict[tuple[int, int], float] = {}
    for reason in output.reasons:
        table = table_of[(reason.slot, reason.participant_a)]
        key = (reason.slot, table)
        weakest[key] = min(weakest.get(key, 1.0), reason.total_score)
    return np.array(sorted(weakest.values()))


def report(
    engine_input: EngineInput, output: EngineOutput, trace: RunTrace, threshold: float
) -> None:
    settings = engine_input.settings
    participant_count = len(engine_input.participants)
    table_count = len(engine_input.tables)
    summary = output.summary

    print("=" * 74)
    print("SENARYO")
    print("=" * 74)
    print(
        f"  {participant_count} katılımcı · {engine_input.slot_count} tur · "
        f"{table_count} masa · {sum(t.capacity for t in engine_input.tables)} sandalye/tur"
    )
    print(f"  {len(engine_input.requests)} görüşme talebi")
    print(
        f"  kalite eşiği {settings.quality_threshold}  ·  "
        f"asgari tur {settings.min_meetings_per_person}"
    )

    # --- Adım 1 ---
    matrix = build_synergy_model(engine_input).matrix
    upper = matrix[np.triu_indices_from(matrix, k=1)]
    passing = int(np.count_nonzero(upper >= threshold)) if upper.size else 0

    print()
    print("=" * 74)
    print("SİNERJİ SKORU  (Adım 1)")
    print("=" * 74)
    print(f"  {upper.size} ikili  ·  {trace.scoring_ms} ms")
    if upper.size:
        print(f"  {_distribution(upper)}")
        print(f"  ortalama={upper.mean():.3f}")
        print(f"  eşiği geçen ikili: {passing} / {upper.size} (%{100 * passing / upper.size:.1f})")

    # --- Adım 2-6 ---
    occupancy = Counter(Counter((row.slot, row.table) for row in output.assignments).values())
    rounds = Counter(Counter(row.participant for row in output.assignments).values())
    rounds[0] = participant_count - sum(rounds.values())
    scores = _table_scores(output)

    print()
    print("=" * 74)
    print("PLAN  (Adım 2-6)")
    print("=" * 74)
    print(f"  {len(output.assignments)} atama  ·  {len(output.reasons)} tanışma")
    print(f"  kullanılan masa: {scores.size} / {engine_input.slot_count * table_count}")
    print(f"  masa doluluğu: {_counter_line(occupancy)}")
    print(f"  masa skoru (en zayıf bağ): {_distribution(scores)}")
    print(f"  ortalama masa skoru: {summary.average_table_score:.3f}")

    print()
    print("  Adım 4 — yerel arama")
    print(
        f"    {trace.search.applied} geçerli hamle / {trace.search.iterations} deneme  ·  "
        f"{trace.search.accepted} kabul  ·  {trace.search.improvements} iyileşme"
    )
    print(
        f"    amaç: {trace.search.objective_before:.1f} → {trace.search.objective_after:.1f}"
        f"  ({trace.search_ms} ms)"
    )
    print()
    print("  Adım 5 — adalet düzeltmesi")
    print(
        f"    {trace.fairness.placements} yerleştirme  ·  hedefin altında "
        f"{trace.fairness.below_target_before} → {trace.fairness.below_target_after} kişi"
        f"  ({trace.fairness_ms} ms)"
    )

    # --- Adalet ---
    print()
    print("=" * 74)
    print("ADALET  (9.6)")
    print("=" * 74)
    print(f"  kişi başı tur dağılımı: {_counter_line(rounds)}")
    print(f"  en az tur alan: {summary.min_meetings_per_person} tur")
    print(f"  hedefin altında: {len(summary.participants_below_target)} / {participant_count} kişi")
    print(f"  hiç oturmamış: {len(summary.unmatched_participants)} kişi")
    print(f"  karşılanan talep: {summary.satisfied_requests} / {summary.total_requests}")
    print(f"  toplam süre: {summary.runtime_ms} ms")

    # --- Kesin kural denetimi ---
    violations = find_violations(engine_input, output.assignments)
    print()
    print("=" * 74)
    print("KESİN KURAL DENETİMİ  (9.5)")
    print("=" * 74)
    if violations:
        for violation in violations[:RULE_REPORT_LIMIT]:
            print(f"  İHLAL — {violation}")
        if len(violations) > RULE_REPORT_LIMIT:
            print(f"  ... ve {len(violations) - RULE_REPORT_LIMIT} ihlal daha")
    else:
        print("  temiz — hiçbir kesin kural çiğnenmedi")
    print()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    spec = ScenarioSpec(
        participant_count=args.katilimci,
        slot_count=args.slot,
        table_count=args.masa,
        seats_per_table=args.sandalye,
        company_count=args.sirket,
        sector_count=args.sektor,
        city_count=args.sehir,
        tag_count=args.etiket,
        theme_count=args.alan,
        category_count=args.kategori,
        offered_per_person=args.secim,
        sought_per_person=args.secim,
        compatibility=args.uyum,
        request_count=args.talep,
        standing_tables=args.ayakli,
        seed=args.tohum,
    )
    weights = DEFAULT_WEIGHTS
    if args.kategori_puani is not None:
        weights = replace(weights, category_credit=args.kategori_puani)

    settings = EngineSettings(
        min_meetings_per_person=args.asgari_tur,
        quality_threshold=args.esik,
        max_iterations=args.deneme,
        seed=args.tohum,
        weights=weights,
    )
    engine_input = build_scenario(spec, settings=settings)

    output, trace = run_matching_with_trace(engine_input)
    report(engine_input, output, trace, args.esik)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
