"""B2X eşleştirme motoru.

Bu paket bilinçli olarak yalnızdır (şartname Bölüm 5.1):

* Girdisi sade veri yapılarıdır, çıktısı sade veri yapılarıdır.
* Veritabanı, HTTP, kullanıcı kimliği, oturum bilmez.
* Yalnızca standart kütüphane ve NumPy kullanır.
* Bağımlılık tek yönlüdür: `app` motoru çağırır, motor `app`'i çağıramaz.

Sebep: eşleştirmenin kalitesi ürünün tamamının değeri. İzole olduğu için sentetik
veriyle terminalden çalıştırılabilir; uygulamayı hiç açmadan yüzlerce senaryo
denenebilir. Motora veritabanı erişimi verilirse bu imkân kaybolur.

Bu sınır iki yerden denetlenir:

* `tests/test_engine_boundary.py` — ihlal varsa testler kırılır.
* `engine/.ruff.toml` — ihlal yazılırken lint uyarı verir.

## Kullanım

```python
from engine import EngineInput, run_matching

output = run_matching(engine_input)
```

Veritabanı kimlikleri ile motorun `0..N-1` indeksleri arasındaki dönüşüm dış
katmanın işidir (9.2) — Aşama 7'de yazılacak.

Terminalden denemek için: `python -m engine.cli --yardim`
"""

from engine.rules import RuleViolation, find_violations
from engine.runner import RunTrace, run_matching, run_matching_with_trace
from engine.scoring import SynergyModel, build_synergy_model
from engine.types import (
    Assignment,
    EngineInput,
    EngineOutput,
    EngineSettings,
    EngineSummary,
    FixedAssignment,
    MeetingRequestPair,
    PairReason,
    Participant,
    TableKind,
    TableSpec,
)
from engine.weights import DEFAULT_WEIGHTS, SynergyWeights

__all__ = [
    "DEFAULT_WEIGHTS",
    "Assignment",
    "EngineInput",
    "EngineOutput",
    "EngineSettings",
    "EngineSummary",
    "FixedAssignment",
    "MeetingRequestPair",
    "PairReason",
    "Participant",
    "RuleViolation",
    "RunTrace",
    "SynergyModel",
    "SynergyWeights",
    "TableKind",
    "TableSpec",
    "build_synergy_model",
    "find_violations",
    "run_matching",
    "run_matching_with_trace",
]
