"""Sinerji skorunun şartname 9.3'e uyduğunun kanıtı.

Buradaki her test 9.3'teki bir cümlenin karşılığıdır. Ağırlıklar ayarlanacak
(Bölüm 12) ama bu **sıralamalar** ağırlıktan bağımsız olarak korunmalı: çift
yönlü eşleşme tek yönlüden değerlidir, aynı sektör tek başına puan getirmez,
karşılıklı talep tek taraflıdan büyüktür.
"""

from collections.abc import Iterable

import numpy as np
import pytest

from engine.scoring import (
    CATEGORY,
    CITY,
    REQUEST,
    SECTOR,
    SIMILARITY_PENALTY,
    SUPPLY_DEMAND,
    build_synergy_model,
)
from engine.types import (
    EngineInput,
    EngineSettings,
    MeetingRequestPair,
    Participant,
    TableSpec,
)
from engine.types import TableKind as Kind
from engine.weights import DEFAULT_WEIGHTS, SynergyWeights


def build_input(
    participants: list[Participant],
    requests: tuple[MeetingRequestPair, ...] = (),
    weights: SynergyWeights | None = None,
) -> EngineInput:
    """Skorlama testleri için en küçük geçerli girdi."""
    return EngineInput(
        participants=tuple(participants),
        tables=(TableSpec(index=0, kind=Kind.SEATED, capacity=6),),
        slot_count=1,
        requests=requests,
        settings=EngineSettings(weights=weights or DEFAULT_WEIGHTS),
    )


def person(
    index: int,
    *,
    company: int | None = None,
    offers: Iterable[int] = (),
    seeks: Iterable[int] = (),
    offer_categories: Iterable[int] = (),
    seek_categories: Iterable[int] = (),
    sector: int | None = None,
    city: int | None = None,
) -> Participant:
    return Participant(
        index=index,
        company=company if company is not None else index,
        offered_tags=frozenset(offers),
        sought_tags=frozenset(seeks),
        offered_categories=frozenset(offer_categories),
        sought_categories=frozenset(seek_categories),
        sector=sector,
        city=city,
    )


def score_of(
    participants: list[Participant],
    requests: tuple = (),
    weights: SynergyWeights | None = None,
) -> float:
    model = build_synergy_model(build_input(participants, requests, weights))
    return model.score(0, 1)


# --- Kategori düzeyinde kısmi puan (9.3) ------------------------------------


def test_same_category_earns_partial_credit_without_an_exact_tag() -> None:
    """9.3: aynı kategoride buluşan ikili sıfır almamalı.

    "Backend geliştirme" sunan ile "Web yazılımı" arayan farklı etiket seçmiş
    ama aynı işi konuşuyorlar. Etiket havuzu inceldikçe bu durum kural hâline
    geliyor.
    """
    pair = [
        person(0, offers={1}, offer_categories={10}),
        person(1, seeks={2}, seek_categories={10}),
    ]
    unrelated = [
        person(0, offers={1}, offer_categories={10}),
        person(1, seeks={2}, seek_categories={20}),
    ]

    assert score_of(pair) > score_of(unrelated)
    assert score_of(unrelated) == pytest.approx(0.0)


def test_exact_tag_beats_category_only() -> None:
    """Kısmi puan tam eşleşmenin yerine geçmiyor, altında kalıyor."""
    exact = [
        person(0, offers={1}, offer_categories={10}),
        person(1, seeks={1}, seek_categories={10}),
    ]
    category_only = [
        person(0, offers={1}, offer_categories={10}),
        person(1, seeks={2}, seek_categories={10}),
    ]

    assert score_of(exact) > score_of(category_only)


def test_category_does_not_add_on_top_of_an_exact_match() -> None:
    """Terim `max`, toplam değil.

    Toplasaydık etiketi tutan ikili bir de kategoriden puan alır ve doyum
    anlamını yitirirdi.
    """
    with_category = [
        person(0, offers={1, 2, 3}, offer_categories={10}),
        person(1, seeks={1, 2, 3}, seek_categories={10}),
    ]
    without_category = [
        person(0, offers={1, 2, 3}),
        person(1, seeks={1, 2, 3}),
    ]

    assert score_of(with_category) == pytest.approx(score_of(without_category))


def test_zero_credit_reproduces_the_previous_behaviour() -> None:
    """Katsayı 0 iken motor kategori öncesiyle birebir aynı davranmalı.

    Değişikliğin geri alınabilir olduğunun kanıtı: ayar tek sayı.
    """
    off = SynergyWeights(category_credit=0.0)
    people = [
        person(0, offers={1}, offer_categories={10}, sector=1, city=1),
        person(1, seeks={2}, seek_categories={10}, sector=1, city=1),
    ]
    without_categories = [
        person(0, offers={1}, sector=1, city=1),
        person(1, seeks={2}, sector=1, city=1),
    ]

    assert score_of(people, weights=off) == pytest.approx(score_of(without_categories, weights=off))


def test_category_credit_never_exceeds_one_exact_match() -> None:
    """Değişmez: kategori örtüşmesi tek bir tam etiket eşleşmesini geçemez.

    Bir tam eşleşme, "aynı iki kategorideyiz"den daha güçlü bir kanıt. Katsayı
    ayarlanırken bu sınır korunmalı.
    """
    w = DEFAULT_WEIGHTS
    one_exact = 1 / w.supply_demand_saturation
    assert w.category_credit <= one_exact + 1e-9


def test_category_alone_does_not_unlock_the_sector_bonus() -> None:
    """Sektör bonusu tam etiket eşleşmesi arıyor.

    Kategori örtüşmesi zaten arz-talep bileşeninde kısmi puan alıyor; sektörü
    de açmak zayıf bir sinyali iki kez saymak olurdu.
    """
    model = build_synergy_model(
        build_input(
            [
                person(0, offers={1}, offer_categories={10}, sector=7),
                person(1, seeks={2}, seek_categories={10}, sector=7),
            ]
        )
    )
    assert model.explain(0, 1)[SECTOR] == pytest.approx(0.0)


def test_category_contribution_is_reported_separately() -> None:
    """Katılımcıya gösterilecek cümle kaynağa göre değişiyor (M8)."""
    category_only = build_synergy_model(
        build_input(
            [
                person(0, offers={1}, offer_categories={10}),
                person(1, seeks={2}, seek_categories={10}),
            ]
        )
    ).explain(0, 1)
    exact = build_synergy_model(
        build_input(
            [
                person(0, offers={1}, offer_categories={10}),
                person(1, seeks={1}, seek_categories={10}),
            ]
        )
    ).explain(0, 1)

    assert category_only[CATEGORY] > 0.0
    assert category_only[SUPPLY_DEMAND] == pytest.approx(0.0)

    assert exact[SUPPLY_DEMAND] > 0.0
    assert exact[CATEGORY] == pytest.approx(0.0)


# --- Arz-talep eşleşmesi ----------------------------------------------------


def test_two_way_match_beats_one_way() -> None:
    """9.3: "Çift yönlü eşleşme tek yönlüden çok daha değerlidir."

    İki durumda da toplam iki etiket örtüşüyor; fark yalnızca yönlerin
    dağılımında.
    """
    one_way = score_of([person(0, offers={1, 2}), person(1, seeks={1, 2})])
    two_way = score_of([person(0, offers={1}, seeks={2}), person(1, offers={2}, seeks={1})])
    assert two_way > one_way


def test_no_overlap_scores_lower_than_one_way() -> None:
    nothing = score_of([person(0, offers={1}), person(1, seeks={9})])
    one_way = score_of([person(0, offers={1}), person(1, seeks={1})])
    assert nothing < one_way


def test_supply_demand_saturates() -> None:
    """Yirmi ortak etiket, üçten yedi kat daha iyi bir görüşme demek değil."""
    three = score_of([person(0, offers={1, 2, 3}), person(1, seeks={1, 2, 3})])
    many = score_of([person(0, offers=set(range(1, 21))), person(1, seeks=set(range(1, 21)))])
    assert many == pytest.approx(three)


# --- Sektör ilişkisi --------------------------------------------------------


def test_same_sector_alone_adds_nothing() -> None:
    """9.3: "Bunu 'aynı sektör = iyi' diye basitleştirme."

    İkisi de aynı şeyi sunuyor, kimse bir şey aramıyor — aynı sektörde olmaları
    puan getirmemeli.
    """
    same_sector = score_of([person(0, offers={1}, sector=5), person(1, offers={1}, sector=5)])
    different_sector = score_of([person(0, offers={1}, sector=5), person(1, offers={1}, sector=9)])
    assert same_sector == pytest.approx(different_sector)


def test_same_sector_with_complementary_need_scores_higher() -> None:
    """9.3: "aynı sektörde olup biri sunan biri arayan ise çok iyi"."""
    same_sector = score_of([person(0, offers={1}, sector=5), person(1, seeks={1}, sector=5)])
    different_sector = score_of([person(0, offers={1}, sector=5), person(1, seeks={1}, sector=9)])
    assert same_sector > different_sector


def test_missing_sector_is_not_a_match() -> None:
    """Sektörü girilmemiş iki kişi "aynı sektörde" sayılmamalı."""
    both_unknown = score_of([person(0, offers={1}), person(1, seeks={1})])
    both_known = score_of([person(0, offers={1}, sector=3), person(1, seeks={1}, sector=3)])
    assert both_unknown < both_known


# --- Coğrafi yakınlık -------------------------------------------------------


def test_same_city_is_a_small_plus() -> None:
    with_city = score_of([person(0, offers={1}, city=7), person(1, seeks={1}, city=7)])
    without_city = score_of([person(0, offers={1}, city=7), person(1, seeks={1}, city=8)])
    assert with_city > without_city

    # "Küçük bir artı" — sektör katkısından büyük olmamalı.
    with_sector = score_of([person(0, offers={1}, sector=3), person(1, seeks={1}, sector=3)])
    assert with_city - without_city < with_sector - without_city


# --- Talep bonusu -----------------------------------------------------------


def test_mutual_request_beats_one_way_beats_none() -> None:
    """9.3: karşılıklı talep çok büyük artı, tek taraflı orta artı."""
    people = [person(0, offers={1}), person(1, seeks={1})]
    none = score_of(people)
    one_way = score_of(people, (MeetingRequestPair(0, 1),))
    mutual = score_of(people, (MeetingRequestPair(0, 1), MeetingRequestPair(1, 0)))
    assert none < one_way < mutual


def test_request_direction_does_not_matter_for_one_way() -> None:
    people = [person(0, offers={1}), person(1, seeks={1})]
    forward = score_of(people, (MeetingRequestPair(0, 1),))
    backward = score_of(people, (MeetingRequestPair(1, 0),))
    assert forward == pytest.approx(backward)


# --- Çeşitlilik cezası ------------------------------------------------------


def test_identical_profiles_are_penalised() -> None:
    """9.3: aynı şeyi sunup aynı şeyi arayan iki kişi birbirine bir şey katmaz.

    İki ikilinin de arz-talep örtüşmesi aynı güçte (her iki yönde iki etiket);
    tek fark profillerin birbirinin kopyası olması. Ceza görünür olsun diye
    temel skorun sıfırdan büyük olduğu bir kurulum seçildi — sıfır skor zaten
    kırpılır ve ceza kaybolurdu.
    """
    identical = score_of(
        [person(0, offers={1, 2}, seeks={1, 2}), person(1, offers={1, 2}, seeks={1, 2})]
    )
    distinct = score_of(
        [person(0, offers={1, 2}, seeks={3, 4}), person(1, offers={3, 4}, seeks={1, 2})]
    )
    assert identical < distinct


def test_penalty_component_is_negative_for_copies() -> None:
    model = build_synergy_model(
        build_input(
            [
                person(0, offers={1, 2}, seeks={1, 2}),
                person(1, offers={1, 2}, seeks={1, 2}),
            ]
        )
    )
    assert model.explain(0, 1)[SIMILARITY_PENALTY] < 0.0


def test_penalty_needs_both_sides_to_be_similar() -> None:
    """Yalnızca sundukları aynıysa ceza uygulanmaz — aradıkları farklıysa
    birbirlerine hâlâ yarayabilirler."""
    model = build_synergy_model(
        build_input(
            [
                person(0, offers={1, 2}, seeks={3}),
                person(1, offers={1, 2}, seeks={9}),
            ]
        )
    )
    assert model.explain(0, 1)[SIMILARITY_PENALTY] == pytest.approx(0.0)


# --- Matrisin bütünlüğü -----------------------------------------------------


def test_matrix_is_symmetric() -> None:
    people = [
        person(0, offers={1}, seeks={2}, sector=1, city=1),
        person(1, offers={2}, seeks={1}, sector=1, city=2),
        person(2, offers={3}, seeks={4}, sector=2, city=1),
    ]
    model = build_synergy_model(build_input(people, (MeetingRequestPair(0, 2),)))
    assert np.allclose(model.matrix, model.matrix.T)


def test_nobody_pairs_with_themselves() -> None:
    people = [person(0, offers={1}, seeks={1}), person(1, offers={1}, seeks={1})]
    model = build_synergy_model(build_input(people))
    assert np.all(np.diag(model.matrix) == 0.0)


def test_scores_stay_within_unit_range() -> None:
    """Kalite eşiği [0, 1] ölçeğinde okunuyor; skor bu aralıktan taşmamalı."""
    people = [
        person(0, offers={1, 2, 3}, seeks={4, 5, 6}, sector=1, city=1),
        person(1, offers={4, 5, 6}, seeks={1, 2, 3}, sector=1, city=1),
    ]
    model = build_synergy_model(
        build_input(people, (MeetingRequestPair(0, 1), MeetingRequestPair(1, 0)))
    )
    assert model.matrix.min() >= 0.0
    assert model.matrix.max() <= 1.0


def test_explain_matches_the_matrix() -> None:
    """Kırılım ile matris ayrışırsa katılımcıya yanlış gerekçe gösterilir.

    Bu test ikisinin tek bir formülden geldiğini garanti eder.
    """
    people = [
        person(0, offers={1, 2}, seeks={3}, sector=1, city=1),
        person(1, offers={3}, seeks={1}, sector=1, city=1),
        person(2, offers={9}, seeks={8}, sector=2, city=3),
        person(3, offers={1, 2}, seeks={3}, sector=1, city=1),
    ]
    model = build_synergy_model(build_input(people, (MeetingRequestPair(0, 2),)))

    for first in range(len(people)):
        for second in range(len(people)):
            if first == second:
                continue
            contributions = model.explain(first, second)
            expected = float(np.clip(sum(contributions.values()), 0.0, 1.0))
            assert model.score(first, second) == pytest.approx(expected), (
                f"{first}-{second} ikilisinde kırılım ile matris ayrışıyor"
            )


def test_explain_reports_every_component() -> None:
    model = build_synergy_model(build_input([person(0, offers={1}), person(1, seeks={1})]))
    contributions = model.explain(0, 1)
    assert set(contributions) == {
        SUPPLY_DEMAND,
        CATEGORY,
        SECTOR,
        CITY,
        REQUEST,
        SIMILARITY_PENALTY,
    }


def test_empty_participant_list_does_not_crash() -> None:
    model = build_synergy_model(
        EngineInput(
            participants=(),
            tables=(TableSpec(index=0, kind=Kind.SEATED, capacity=4),),
            slot_count=1,
        )
    )
    assert model.matrix.shape == (0, 0)


def test_participants_without_tags_do_not_crash() -> None:
    """Profil sihirbazı yarım bırakılmış olabilir (M2)."""
    model = build_synergy_model(build_input([person(0), person(1)]))
    assert model.score(0, 1) == pytest.approx(0.0)
