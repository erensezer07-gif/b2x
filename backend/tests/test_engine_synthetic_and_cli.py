"""Sentetik üretici karşılıklı talep ve CLI skor dağılımı testleri."""

from engine.cli import main
from engine.synthetic import ScenarioSpec, build_scenario


def test_synthetic_mutual_request_ratio() -> None:
    # Karşılıklı talep oranı %40 (100 talebin ~40 tanesi karşılıklı çift)
    spec = ScenarioSpec(
        participant_count=40,
        request_count=100,
        mutual_request_ratio=0.40,
        seed=123,
    )
    engine_input = build_scenario(spec)
    reqs = engine_input.requests

    assert len(reqs) == 100

    req_set = {(r.requester, r.target) for r in reqs}
    mutual_pairs = {(a, b) for (a, b) in req_set if (b, a) in req_set}

    # Her karşılıklı ikili 2 talep içerir (a->b ve b->a)
    # 40 hedeflenen karşılıklı talep -> en az 40 karşılıklı talep yönü
    assert len(mutual_pairs) >= 40


def test_synthetic_zero_mutual_request_ratio() -> None:
    spec = ScenarioSpec(
        participant_count=40,
        request_count=50,
        mutual_request_ratio=0.0,
        seed=123,
    )
    engine_input = build_scenario(spec)
    assert len(engine_input.requests) == 50


def test_cli_score_distribution_flag(capsys) -> None:
    code = main(["--katilimci", "40", "--sadece-dagilim"])
    assert code == 0

    captured = capsys.readouterr()
    assert "İKİLİ SİNERJİ SKORU DAĞILIM RAPORU" in captured.out
    assert "YÜZDELİK DAĞILIMI (PERCENTILES)" in captured.out
    assert "KALİTE EŞİĞİ SİMÜLASYONU" in captured.out
    assert "%70" in captured.out


def test_cli_with_mutual_request_ratio(capsys) -> None:
    code = main([
        "--katilimci", "50",
        "--talep", "60",
        "--karsilikli-talep-orani", "0.30",
        "--sadece-dagilim",
    ])
    assert code == 0

    captured = capsys.readouterr()
    assert "İKİLİ SİNERJİ SKORU DAĞILIM RAPORU" in captured.out
    assert "60 görüşme talebi" in captured.out
