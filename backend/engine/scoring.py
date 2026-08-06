"""Adım 1 — sinerji skoru ve skor matrisi (şartname 9.3).

Tüm katılımcı ikilileri için skor bir kez hesaplanıp bellekte tutulur; sonrasında
her skor sorgusu tablo okuması olur. Hesap NumPy ile matris çarpımına indirgenir,
200 kişi için saniyenin çok altında biter.

## Skorun biçimi

```
temel = (arz_talep × w_sd + sektör × w_sektör + şehir × w_şehir) / (w_sd + w_sektör + w_şehir)
skor  = kırp(temel + talep_bonusu − benzerlik_cezası, 0, 1)
```

Bileşenlerin gerekçeleri `weights.py` içinde. Skor [0, 1] aralığındadır; kalite
eşiği bu ölçekte okunur.

## Kırılım

`SynergyModel.explain()` tek bir ikili için hangi bileşenden kaç puan geldiğini
döndürür. Adım 6'nın kaynağı budur — matris yalnızca toplamı tuttuğu için kırılım
sonunda, yalnızca aynı masada oturan ikililer için yeniden hesaplanır.

Bileşen anahtarları İngilizce; katılımcıya gösterilecek Türkçe cümleler bunlardan
arayüz katmanında üretilir (M8). Motor cümle kurmaz.
"""

from dataclasses import dataclass

import numpy as np

from engine.types import EngineInput, MeetingRequestPair, Participant
from engine.weights import SynergyWeights

# `match_reasons.breakdown` içine bu anahtarlarla yazılır.
SUPPLY_DEMAND = "supply_demand"
SECTOR = "sector"
CITY = "city"
REQUEST = "request"
SIMILARITY_PENALTY = "similarity_penalty"


def _tag_matrices(
    participants: tuple[Participant, ...],
) -> tuple[np.ndarray, np.ndarray]:
    """Etiket kümelerini N×T boolean matrislere çevirir.

    Etiket kimlikleri sıralanarak sütuna yerleştirilir — küme gezinme sırası
    çalışmadan çalışmaya değişmesin diye (5.3 determinizm).
    """
    tags = sorted(
        {tag for person in participants for tag in (person.offered_tags | person.sought_tags)}
    )
    column_of = {tag: column for column, tag in enumerate(tags)}

    offered = np.zeros((len(participants), len(tags)), dtype=np.float64)
    sought = np.zeros((len(participants), len(tags)), dtype=np.float64)
    for person in participants:
        for tag in person.offered_tags:
            offered[person.index, column_of[tag]] = 1.0
        for tag in person.sought_tags:
            sought[person.index, column_of[tag]] = 1.0
    return offered, sought


def _attribute_vector(values: list[int | None]) -> np.ndarray:
    """`None` olanları eşleşmeyecek bir değere çevirir.

    Sektörü girilmemiş iki kişi "aynı sektörde" sayılmamalı.
    """
    return np.array([-1 if value is None else value for value in values], dtype=np.int64)


def _pairwise_equal(values: np.ndarray) -> np.ndarray:
    """Aynı değere sahip ikilileri işaretler; tanımsız (-1) olanlar hariç."""
    same = values[:, None] == values[None, :]
    known = values >= 0
    return same & known[:, None] & known[None, :]


def _jaccard(matrix: np.ndarray) -> np.ndarray:
    """Satırlar arası Jaccard benzerliği. İki küme de boşsa 0 sayılır."""
    intersection = matrix @ matrix.T
    sizes = matrix.sum(axis=1)
    union = sizes[:, None] + sizes[None, :] - intersection
    return np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)


def _request_matrix(requests: tuple[MeetingRequestPair, ...], participant_count: int) -> np.ndarray:
    matrix = np.zeros((participant_count, participant_count), dtype=bool)
    for request in requests:
        matrix[request.requester, request.target] = True
    return matrix


@dataclass(frozen=True, slots=True)
class SynergyModel:
    """Skor matrisi ve tek ikilinin kırılımını üretebilen model."""

    matrix: np.ndarray
    participants: tuple[Participant, ...]
    requests: frozenset[tuple[int, int]]
    weights: SynergyWeights

    def score(self, first: int, second: int) -> float:
        return float(self.matrix[first, second])

    def explain(self, first: int, second: int) -> dict[str, float]:
        """Bir ikilinin skorunun bileşen kırılımı.

        Değerler **ağırlıklandırılmış katkılardır**, ham bileşen değerleri değil —
        "hangi bileşenden kaç puan geldi" sorusunun cevabı bu.

        Katkıların toplamı skora eşit olmayabilir: nihai skor [0, 1] aralığına
        kırpılır. Toplam için `score()` kullanılmalı.
        """
        a = self.participants[first]
        b = self.participants[second]
        w = self.weights

        forward = len(a.offered_tags & b.sought_tags)
        backward = len(b.offered_tags & a.sought_tags)
        saturation = w.supply_demand_saturation
        forward_ratio = min(forward, saturation) / saturation
        backward_ratio = min(backward, saturation) / saturation
        bonus = w.mutual_supply_demand_bonus
        supply_demand = min(
            (forward_ratio + backward_ratio) / 2.0 + bonus * min(forward_ratio, backward_ratio),
            1.0,
        )

        complementary = forward > 0 or backward > 0
        same_sector = a.sector is not None and a.sector == b.sector
        sector = 1.0 if (same_sector and complementary) else 0.0

        same_city = a.city is not None and a.city == b.city
        city = 1.0 if same_city else 0.0

        total_weight = w.base_weight_total
        contributions = {
            SUPPLY_DEMAND: w.supply_demand * supply_demand / total_weight,
            SECTOR: w.sector * sector / total_weight,
            CITY: w.city * city / total_weight,
        }

        asked = (first, second) in self.requests
        was_asked = (second, first) in self.requests
        if asked and was_asked:
            contributions[REQUEST] = w.request_mutual_bonus
        elif asked or was_asked:
            contributions[REQUEST] = w.request_one_way_bonus
        else:
            contributions[REQUEST] = 0.0

        similarity = min(
            _set_jaccard(a.offered_tags, b.offered_tags),
            _set_jaccard(a.sought_tags, b.sought_tags),
        )
        contributions[SIMILARITY_PENALTY] = -w.similarity_penalty * _penalty_ratio(similarity, w)

        return contributions


def _set_jaccard(first: frozenset[int], second: frozenset[int]) -> float:
    union = first | second
    if not union:
        return 0.0
    return len(first & second) / len(union)


def _penalty_ratio(similarity: float, weights: SynergyWeights) -> float:
    """Ceza yalnızca eşiğin üstünde başlar ve 1.0'a doğru doğrusal artar."""
    threshold = weights.similarity_threshold
    if threshold >= 1.0:
        return 0.0
    return float(np.clip((similarity - threshold) / (1.0 - threshold), 0.0, 1.0))


def build_synergy_model(engine_input: EngineInput) -> SynergyModel:
    """Adım 1: tüm ikililer için sinerji skorunu hesaplar."""
    participants = engine_input.participants
    weights = engine_input.settings.weights
    count = len(participants)

    if count == 0:
        return SynergyModel(
            matrix=np.zeros((0, 0), dtype=np.float64),
            participants=participants,
            requests=frozenset(),
            weights=weights,
        )

    offered, sought = _tag_matrices(participants)

    # Arz-talep: ileri[a, b] = a'nın sunduğu ile b'nin aradığının kesişim sayısı.
    forward = offered @ sought.T
    backward = forward.T

    saturation = float(weights.supply_demand_saturation)
    forward_ratio = np.minimum(forward, saturation) / saturation
    backward_ratio = np.minimum(backward, saturation) / saturation

    # `min` yalnızca iki yön de doluyken sıfırdan farklıdır; çift yönlü eşleşme
    # bu sayede tek yönlüden belirgin şekilde öne çıkar (9.3).
    bonus = weights.mutual_supply_demand_bonus
    supply_demand = np.minimum(
        (forward_ratio + backward_ratio) / 2.0 + bonus * np.minimum(forward_ratio, backward_ratio),
        1.0,
    )

    # Sektör: aynı sektör tek başına puan getirmez. 9.3 "aynı sektör = iyi"
    # basitleştirmesini açıkça yasaklıyor — biri sunup diğeri arıyorsa değerli.
    sectors = _attribute_vector([person.sector for person in participants])
    complementary = (forward > 0) | (backward > 0)
    sector = (_pairwise_equal(sectors) & complementary).astype(np.float64)

    cities = _attribute_vector([person.city for person in participants])
    city = _pairwise_equal(cities).astype(np.float64)

    base = (
        weights.supply_demand * supply_demand + weights.sector * sector + weights.city * city
    ) / weights.base_weight_total

    requested = _request_matrix(engine_input.requests, count)
    mutual_request = requested & requested.T
    one_way_request = (requested | requested.T) & ~mutual_request
    request_bonus = np.where(
        mutual_request,
        weights.request_mutual_bonus,
        np.where(one_way_request, weights.request_one_way_bonus, 0.0),
    )

    # Çeşitlilik cezası: hem sundukları hem aradıkları neredeyse aynı olan ikili.
    # İki benzerliğin küçüğü alınır — yalnızca biri benzerse ceza yok.
    similarity = np.minimum(_jaccard(offered), _jaccard(sought))
    threshold = weights.similarity_threshold
    if threshold < 1.0:
        excess = np.clip((similarity - threshold) / (1.0 - threshold), 0.0, 1.0)
    else:
        excess = np.zeros_like(similarity)
    penalty = weights.similarity_penalty * excess

    matrix = np.clip(base + request_bonus - penalty, 0.0, 1.0)

    # Kimse kendisiyle eşleşmez.
    np.fill_diagonal(matrix, 0.0)

    return SynergyModel(
        matrix=matrix,
        participants=participants,
        requests=frozenset(
            (request.requester, request.target) for request in engine_input.requests
        ),
        weights=weights,
    )
