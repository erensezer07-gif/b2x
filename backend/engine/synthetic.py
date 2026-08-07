"""Sentetik senaryo üreteci (şartname 9.10).

*"Sentetik katılımcı üreten bir yardımcı olur — parametreleriyle senaryo
kurulabilir."*

Motorun izole olmasının asıl kazancı bu: uygulamayı hiç açmadan, veritabanına
hiç dokunmadan yüzlerce senaryo denenebilir (5.1).

Üretim `random.Random(seed)` ile yapılır; aynı tohum aynı senaryoyu verir.
"""

import random
from dataclasses import dataclass, replace

from engine.types import (
    EngineInput,
    EngineSettings,
    MeetingRequestPair,
    Participant,
    TableKind,
    TableSpec,
)


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """Senaryo parametreleri.

    Varsayılanlar küçük ve hızlı bir senaryo kurar; ölçek denemesi için
    değerler dışarıdan verilir.
    """

    participant_count: int = 60
    slot_count: int = 4
    table_count: int = 12
    seats_per_table: int = 6

    company_count: int = 30
    sector_count: int = 8
    city_count: int = 5

    tag_count: int = 40
    # M2 en az üçer etiket istiyor; gerçekte insanlar biraz daha fazla seçiyor.
    offered_per_person: int = 4
    sought_per_person: int = 4

    # Etiket havuzunun kaç ilgi alanına bölündüğü.
    #
    # Gerçek katılımcılar etiketlerini rastgele seçmez, kümelenir: fintech'çi
    # "ödeme altyapısı" sunar ve "bankacılık ortaklığı" arar. Etiketleri düzgün
    # dağıtmak bu yüzden gerçekçi değil — herkesin herkesle örtüşme olasılığını
    # yapay olarak sıfıra yaklaştırır ve motoru olduğundan kötü gösterir.
    #
    # Her kişi bir "sunduğu alan" ve bir "aradığı alan" çeker; etiketleri o
    # alanların dilimlerinden gelir. Alan sayısı azaldıkça eşleşme yoğunlaşır.
    theme_count: int = 5

    # Etiket havuzunun kaç kategoriye bölündüğü.
    #
    # Gerçekte her etiket bir kategoriye ait (9 kategori × 8 etiket) ve motor
    # tam eşleşme bulamadığında kategori düzeyinde kısmi puan veriyor (9.3).
    # Burada kategori etiket kimliğinden türetiliyor: bitişik dilimler.
    #
    # İlgi alanından (theme) ayrı bir kavram: alan kimin neyi seçeceğini
    # belirler, kategori seçilen etiketlerin hangi başlık altında toplandığını.
    category_count: int = 6

    # 0.0 = kimse kimseye uymaz (sunulan ve aranan havuzları tamamen ayrık)
    # 1.0 = havuzlar aynı, eşleşme bol
    compatibility: float = 1.0

    request_count: int = 0
    # Görüşme talepleri içindeki karşılıklı talep oranı (0.0 = tamamen tek yönlü, 1.0 = tümü karşılıklı çiftler)
    mutual_request_ratio: float = 0.0
    standing_tables: bool = False
    seed: int = 42


# Varsayılan senaryo. Donmuş olduğu için paylaşılması güvenli.
DEFAULT_SCENARIO = ScenarioSpec()


def build_scenario(
    spec: ScenarioSpec | None = None, settings: EngineSettings | None = None
) -> EngineInput:
    """Parametrelerden geçerli bir motor girdisi üretir."""
    spec = spec or DEFAULT_SCENARIO
    rng = random.Random(spec.seed)

    participants = _build_participants(spec, rng)
    tables = _build_tables(spec)
    requests = _build_requests(spec, rng)

    engine_input = EngineInput(
        participants=participants,
        tables=tables,
        slot_count=spec.slot_count,
        requests=requests,
        settings=settings or EngineSettings(seed=spec.seed),
    )
    engine_input.validate()
    return engine_input


def _build_participants(spec: ScenarioSpec, rng: random.Random) -> tuple[Participant, ...]:
    # Aranan etiketler kaydırılmış bir havuzdan çekilir. Kaydırma sıfırken
    # havuzlar çakışır ve eşleşme mümkün olur; havuz boyu kadar kaydırıldığında
    # hiçbir sunulan etiket hiçbir aranan etiketle örtüşmez (uyum = 0).
    shift = round((1.0 - spec.compatibility) * spec.tag_count)
    theme_count = max(1, spec.theme_count)
    theme_size = max(1, spec.tag_count // theme_count)

    def theme_tags(start: int, theme: int) -> list[int]:
        first = start + theme * theme_size
        return list(range(first, first + theme_size))

    # Kategori etiket kimliğinden türetiliyor: bitişik dilimler. Gerçekte de
    # her etiket tam olarak bir kategoriye ait.
    category_size = max(1, spec.tag_count // max(1, spec.category_count))

    def categories_of(tags: frozenset[int]) -> frozenset[int]:
        return frozenset(tag // category_size for tag in tags)

    people = []
    for index in range(spec.participant_count):
        offer_theme = rng.randrange(theme_count)
        seek_theme = rng.randrange(theme_count)
        offer_pool = theme_tags(0, offer_theme)
        seek_pool = theme_tags(shift, seek_theme)

        offered = frozenset(rng.sample(offer_pool, min(spec.offered_per_person, len(offer_pool))))
        sought = frozenset(rng.sample(seek_pool, min(spec.sought_per_person, len(seek_pool))))

        people.append(
            Participant(
                index=index,
                company=rng.randrange(spec.company_count),
                offered_tags=offered,
                sought_tags=sought,
                offered_categories=categories_of(offered),
                sought_categories=categories_of(sought),
                sector=rng.randrange(spec.sector_count) if spec.sector_count else None,
                city=rng.randrange(spec.city_count) if spec.city_count else None,
            )
        )
    return tuple(people)


def _build_tables(spec: ScenarioSpec) -> tuple[TableSpec, ...]:
    if spec.standing_tables:
        return tuple(
            TableSpec(
                index=index,
                kind=TableKind.STANDING,
                capacity=spec.seats_per_table,
                target_min=max(2, spec.seats_per_table // 2),
            )
            for index in range(spec.table_count)
        )
    return tuple(
        TableSpec(index=index, kind=TableKind.SEATED, capacity=spec.seats_per_table)
        for index in range(spec.table_count)
    )


def _build_requests(spec: ScenarioSpec, rng: random.Random) -> tuple[MeetingRequestPair, ...]:
    if spec.request_count <= 0 or spec.participant_count < 2:
        return ()

    seen: set[tuple[int, int]] = set()
    requests: list[MeetingRequestPair] = []

    # Karşılıklı talepler (A -> B ve B -> A)
    # Her çift 2 talep oluşturduğu için hedef çift sayısı: (request_count * ratio) // 2
    target_mutual_pairs = 0
    if spec.mutual_request_ratio > 0.0:
        ratio = max(0.0, min(1.0, spec.mutual_request_ratio))
        target_mutual_requests = int(round(spec.request_count * ratio))
        target_mutual_pairs = target_mutual_requests // 2

    # 1. Karşılıklı talep ikililerini oluştur
    for _ in range(target_mutual_pairs * 10):
        if len(requests) >= target_mutual_pairs * 2:
            break
        a = rng.randrange(spec.participant_count)
        b = rng.randrange(spec.participant_count)
        if a == b or (a, b) in seen or (b, a) in seen:
            continue
        seen.add((a, b))
        seen.add((b, a))
        requests.append(MeetingRequestPair(requester=a, target=b))
        requests.append(MeetingRequestPair(requester=b, target=a))

    # 2. Kalan talepleri tek yönlü oluştur
    # Sonsuz döngüye düşmemek için deneme sayısı sınırlı: küçük senaryolarda
    # istenen kadar farklı ikili bulunmayabilir.
    for _ in range(spec.request_count * 10):
        if len(requests) >= spec.request_count:
            break
        requester = rng.randrange(spec.participant_count)
        target = rng.randrange(spec.participant_count)
        if requester == target or (requester, target) in seen:
            continue
        seen.add((requester, target))
        requests.append(MeetingRequestPair(requester=requester, target=target))

    return tuple(requests)


def with_single_outsider_sector(engine_input: EngineInput) -> EngineInput:
    """Bir kişi hariç herkesi aynı sektöre koyar (9.10 zor senaryosu).

    Adalet kuralının asıl sınandığı durum: 9.6'daki başarısızlık hikâyesinin
    uç hâli.
    """
    people = list(engine_input.participants)
    for position, person in enumerate(people):
        people[position] = replace(person, sector=0 if position > 0 else 1)
    return replace(engine_input, participants=tuple(people))
