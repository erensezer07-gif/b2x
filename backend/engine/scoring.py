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

from collections.abc import Callable
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

# Arz-talep puanının **yalnızca kategori örtüşmesi sayesinde** kazanılan kısmı.
# Diğerleri gibi ağırlıklandırılmış bir katkıdır; `SUPPLY_DEMAND` ile toplamı
# arz-talep bileşeninin tamamını verir. Ayrı tutuluyor çünkü katılımcıya
# gösterilecek cümle değişiyor (M8): "Sen X sunuyorsun, o X arıyor" ile
# "İkiniz de Y alanındasınız" aynı şey değil.
CATEGORY = "category"


def _membership_matrices(
    participants: tuple[Participant, ...],
    offered_of: Callable[[Participant], frozenset[int]],
    sought_of: Callable[[Participant], frozenset[int]],
) -> tuple[np.ndarray, np.ndarray]:
    """Küme üyeliklerini N×K boolean matrislere çevirir.

    Hem etiketler hem kategoriler için kullanılıyor; ikisi de aynı biçimde
    "kim neyi sunuyor / arıyor" tablosu.

    Kimlikler sıralanarak sütuna yerleştirilir — küme gezinme sırası çalışmadan
    çalışmaya değişmesin diye (5.3 determinizm).
    """
    keys = sorted(
        {key for person in participants for key in (offered_of(person) | sought_of(person))}
    )
    column_of = {key: column for column, key in enumerate(keys)}

    offered = np.zeros((len(participants), len(keys)), dtype=np.float64)
    sought = np.zeros((len(participants), len(keys)), dtype=np.float64)
    for person in participants:
        for key in offered_of(person):
            offered[person.index, column_of[key]] = 1.0
        for key in sought_of(person):
            sought[person.index, column_of[key]] = 1.0
    return offered, sought


def _saturated(counts: np.ndarray, saturation: float) -> np.ndarray:
    """Kesişim sayısını [0, 1] oranına çevirir; doyumun üstü ek puan getirmez."""
    if saturation <= 0:
        return np.zeros_like(counts)
    return np.minimum(counts, saturation) / saturation


def _supply_demand_ratio(
    exact: np.ndarray, category: np.ndarray, weights: SynergyWeights
) -> np.ndarray:
    """Tek yönün arz-talep oranı: tam etiket ve kategori birlikte.

    `max`, toplam değil — tam eşleşme kategoriyi gölgeler (9.3). Toplasaydık
    etiketi tutan ikili bir de kategoriden puan alır ve doyum anlamını
    yitirirdi.
    """
    exact_ratio = _saturated(exact, float(weights.supply_demand_saturation))
    if weights.category_credit <= 0.0:
        return exact_ratio
    category_ratio = _saturated(category, float(weights.category_saturation))
    return np.maximum(exact_ratio, weights.category_credit * category_ratio)


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
        forward_category = len(a.offered_categories & b.sought_categories)
        backward_category = len(b.offered_categories & a.sought_categories)

        # Aynı hesap iki kez: biri kategori kredisiyle, biri kategorisiz.
        # Farkları "kategori sayesinde kazanılan puan" oluyor ve ayrı bir
        # kalem olarak raporlanıyor. İkisinin toplamı arz-talep bileşeninin
        # tamamına eşit — kırılımın toplamı skoru vermeli.
        supply_demand = _combine_directions(
            _pair_supply_demand_ratio(forward, forward_category, w),
            _pair_supply_demand_ratio(backward, backward_category, w),
            w,
        )
        exact_only = _combine_directions(
            _pair_supply_demand_ratio(forward, 0, w),
            _pair_supply_demand_ratio(backward, 0, w),
            w,
        )
        from_category = max(supply_demand - exact_only, 0.0)

        # Sektör bonusu **tam** etiket eşleşmesi arıyor, kategori yetmiyor.
        # 9.3 "biri sunup diğeri arıyorsa değerli" diyor; kategori düzeyindeki
        # örtüşme bunun zayıf hâli ve zaten arz-talep bileşeninde kısmi puan
        # alıyor. İkisini birden vermek zayıf bir sinyali iki kez saymak olurdu.
        complementary = forward > 0 or backward > 0
        same_sector = a.sector is not None and a.sector == b.sector
        sector = 1.0 if (same_sector and complementary) else 0.0

        same_city = a.city is not None and a.city == b.city
        city = 1.0 if same_city else 0.0

        total_weight = w.base_weight_total
        contributions = {
            SUPPLY_DEMAND: w.supply_demand * exact_only / total_weight,
            CATEGORY: w.supply_demand * from_category / total_weight,
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


def _combine_directions(forward: float, backward: float, weights: SynergyWeights) -> float:
    """İki yönün oranını arz-talep bileşenine indirger (9.3).

    `min(ileri, geri)` yalnızca iki yön de doluyken sıfırdan farklı; çift yönlü
    eşleşme bu sayede tek yönlüden belirgin şekilde öne çıkıyor.
    """
    bonus = weights.mutual_supply_demand_bonus
    return min((forward + backward) / 2.0 + bonus * min(forward, backward), 1.0)


def _pair_supply_demand_ratio(exact: int, category: int, weights: SynergyWeights) -> float:
    """`_supply_demand_ratio`'nun tek ikili için skaler karşılığı.

    İki hesabın ayrışması sessiz bir hata olurdu: matris skoru verir, `explain()`
    gerekçeyi verir; ayrışırlarsa katılımcıya skoruyla uyuşmayan bir gerekçe
    gösterilir. Bir test ikisinin aynı sonucu ürettiğini kilitliyor.
    """
    saturation = weights.supply_demand_saturation
    exact_ratio = min(exact, saturation) / saturation if saturation > 0 else 0.0
    if weights.category_credit <= 0.0:
        return exact_ratio

    category_saturation = weights.category_saturation
    category_ratio = (
        min(category, category_saturation) / category_saturation if category_saturation > 0 else 0.0
    )
    return max(exact_ratio, weights.category_credit * category_ratio)


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

    offered, sought = _membership_matrices(
        participants,
        lambda person: person.offered_tags,
        lambda person: person.sought_tags,
    )
    offered_category, sought_category = _membership_matrices(
        participants,
        lambda person: person.offered_categories,
        lambda person: person.sought_categories,
    )

    # Arz-talep: ileri[a, b] = a'nın sunduğu ile b'nin aradığının kesişim sayısı.
    forward = offered @ sought.T
    backward = forward.T

    forward_category = offered_category @ sought_category.T
    backward_category = forward_category.T

    forward_ratio = _supply_demand_ratio(forward, forward_category, weights)
    backward_ratio = _supply_demand_ratio(backward, backward_category, weights)

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
