"""Plan önizleme ve elle düzeltme (şartname M7).

Motorun ürettiği plan burada görünür hâle geliyor: organizatör her turu
görüyor, iki kişiyi takas ediyor, atamayı sabitliyor, planı yayınlıyor.

## Neden doğrulama sunucuda

Kurallar şirket kimliğini, masa kapasitesini ve **diğer slotlardaki**
eşleşmeleri gerektiriyor. İstemciye taşımak planın tamamını indirmek olurdu.
Bölüm 0 zaten kuralların sunucuda uygulanmasını istiyor.

## Uyarı, engel değil

M7: *"Organizatör uyarıya rağmen devam edebilir — ama ne yaptığını bilerek
yapar."* Bu yüzden takas hiçbir kontrolde reddedilmiyor; sonuç uyarı listesi
olarak dönüyor. Tek istisna **sabitlenmiş atama** — sabitlemenin anlamı zaten
"buna dokunma".

## Kurallar burada ikinci kez yazılıyor

`engine/rules.py` aynı kuralları denetliyor ama metin üretiyor, yapılandırılmış
uyarı değil. Buradaki kontroller arayüzün ihtiyacı olan biçimde yazıldı.
İkisinin ayrı olması bilinçli: testler her takastan sonra planı
`find_violations`'tan geçiriyor ve burada raporlanmayan bir ihlal kalmadığını
doğruluyor — bağımsız ikinci göz.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    Assignment,
    Event,
    JobStatus,
    Layout,
    MatchReason,
    Plan,
    PlanStatus,
    Profile,
    Registration,
    Table,
    User,
)
from app.services.matching import MatchingContext, build_engine_input
from engine.scoring import build_synergy_model

# Uyarı anahtarları. Türkçe cümleyi arayüz kuruyor (Aşama 6-7'deki kalıp).
SAME_COMPANY = "same_company"
OVER_CAPACITY = "over_capacity"
LONELY_TABLE = "lonely_table"
REPEAT_PAIR = "repeat_pair"
QUALITY_DROPPED = "quality_dropped"


class TableQuality(StrEnum):
    """Masa kalite göstergesi (M7).

    *"Sayı değil, üç seviye: iyi / orta / zayıf."* Sınırlar kalite eşiğine
    bağlı ve **mutlak**: aynı renk her zaman aynı şeyi anlatıyor, kötü bir
    planda "iyi" masa çıkmıyor.
    """

    EMPTY = "empty"
    WEAK = "weak"
    FAIR = "fair"
    GOOD = "good"


# "İyi" sayılmak için eşiğin kaç katı gerekiyor.
GOOD_QUALITY_MULTIPLIER = 1.5


def quality_of(score: float, occupant_count: int, threshold: float) -> TableQuality:
    if occupant_count < 2:
        return TableQuality.EMPTY
    if score < threshold:
        return TableQuality.WEAK
    if score < threshold * GOOD_QUALITY_MULTIPLIER:
        return TableQuality.FAIR
    return TableQuality.GOOD


@dataclass(frozen=True, slots=True)
class SeatedPerson:
    assignment_id: int
    registration_id: int
    full_name: str | None
    company: str | None
    is_pinned: bool


@dataclass(frozen=True, slots=True)
class TableView:
    table_id: int
    number: int
    label: str | None
    capacity: int
    occupants: tuple[SeatedPerson, ...]
    score: float
    quality: TableQuality


@dataclass(frozen=True, slots=True)
class SwapWarning:
    key: str
    # Uyarının kime/neye dair olduğu — arayüz cümleyi bunlarla kuruyor.
    table_number: int | None = None
    people: tuple[str, ...] = ()
    slot_number: int | None = None


# --- Yükleme -----------------------------------------------------------------


async def _load_assignments(session: AsyncSession, plan_id: int) -> list[Assignment]:
    """Planın bütün atamaları, oturanların profilleriyle.

    Tek slot gösterilecek olsa bile hepsi yükleniyor: "bu ikili başka bir
    slotta zaten eşleşiyor mu" kontrolü planın tamamını gerektiriyor (M7).
    """
    result = await session.execute(
        select(Assignment)
        .where(Assignment.plan_id == plan_id)
        .options(
            selectinload(Assignment.registration)
            .selectinload(Registration.user)
            .selectinload(User.profile)
            .selectinload(Profile.company)
        )
        .order_by(Assignment.slot_number, Assignment.table_id, Assignment.id)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars())


async def _load_tables(session: AsyncSession, event_id: int) -> list[Table]:
    result = await session.execute(
        select(Table)
        .join(Layout, Layout.id == Table.layout_id)
        .where(Layout.event_id == event_id)
        .order_by(Table.number)
    )
    return list(result.scalars())


def _capacity_of(table: Table) -> int:
    return table.seat_count or table.max_people or 0


def _person(assignment: Assignment) -> SeatedPerson:
    profile = assignment.registration.user.profile
    return SeatedPerson(
        assignment_id=assignment.id,
        registration_id=assignment.registration_id,
        full_name=profile.full_name if profile else None,
        company=profile.company.name if profile and profile.company else None,
        is_pinned=assignment.is_pinned,
    )


async def _pair_scores(session: AsyncSession, plan_id: int) -> dict[tuple[int, int], float]:
    """Saklanmış ikili skorları: (küçük kimlik, büyük kimlik) → skor.

    `match_reasons` motorun hesabını zaten taşıyor; masa skoru için sinerji
    modelini yeniden kurmaya gerek yok. Takas yeni ikililer üretince o satırlar
    orada yeniden yazılıyor (`recompute_reasons`).
    """
    result = await session.execute(
        select(
            MatchReason.registration_a_id,
            MatchReason.registration_b_id,
            MatchReason.total_score,
        ).where(MatchReason.plan_id == plan_id)
    )
    return {(a, b): score for a, b, score in result.all()}


def table_score(occupants: list[SeatedPerson], scores: dict[tuple[int, int], float]) -> float:
    """Göstergenin dayandığı sayı: **en yalnız kişinin en iyi bağı** (M7).

    Her kişi için o masadaki en iyi bağı bulunuyor, sonuç bunların en düşüğü.
    Cevapladığı soru: *"bu masada kimse ortada kalıyor mu?"*

    **Motorun amaç fonksiyonu değil.** 9.4 masayı en zayıf ikilisiyle ölçüyor
    ve motor onu optimize etmeye devam ediyor. Ama *gösterge* olarak en zayıf
    ikili masa boyuyla birlikte anlamını yitiriyor: iki kişilik masada tek
    ikili var, altı kişilikte on beş — on beş çekilişin en düşüğü kaçınılmaz
    olarak küçük. Ölçümde altı sandalyeli masaların **hiçbiri** "iyi"
    alamıyordu; rozet tek renge düşünce organizatör hangi masayı düzelteceğini
    göremiyordu (ayrıntı `docs/kararlar.md`).

    9.4'ün gerekçesine aykırı değil, ona daha yakın: *"o dördüncü kişi yarım
    saat dışlanmış hisseder."* Kişinin masadan memnun ayrılması için herkesle
    tutması gerekmiyor, **birisiyle** tutması yetiyor.

    İki kişilik masada tek ikilinin skoruna eşit — eski ölçütle birebir aynı.
    """
    if len(occupants) < 2:
        return 0.0

    best_link = dict.fromkeys((person.registration_id for person in occupants), 0.0)
    for position, first in enumerate(occupants):
        for second in occupants[position + 1 :]:
            key = _pair_key(first.registration_id, second.registration_id)
            # Takas sonrası satır yazılmamış bir ikili kalırsa en kötüyü
            # varsayıyoruz; sessizce yüksek göstermek yanıltıcı olurdu.
            score = scores.get(key, 0.0)
            best_link[first.registration_id] = max(best_link[first.registration_id], score)
            best_link[second.registration_id] = max(best_link[second.registration_id], score)

    return min(best_link.values())


def _pair_key(first: int, second: int) -> tuple[int, int]:
    return (first, second) if first < second else (second, first)


# --- Slot görünümü ------------------------------------------------------------


async def build_slot_view(
    session: AsyncSession, event: Event, plan: Plan, slot_number: int
) -> list[TableView]:
    """Bir turun masaları ve oturanları (M7).

    Boş masalar da dönüyor: organizatör birini boş sandalyeye taşıyabilmeli.
    """
    threshold = get_settings().matching_quality_threshold
    tables = await _load_tables(session, event.id)
    assignments = await _load_assignments(session, plan.id)
    scores = await _pair_scores(session, plan.id)

    seated: dict[int, list[SeatedPerson]] = {table.id: [] for table in tables}
    for assignment in assignments:
        if assignment.slot_number == slot_number and assignment.table_id in seated:
            seated[assignment.table_id].append(_person(assignment))

    views = []
    for table in tables:
        occupants = seated[table.id]
        score = table_score(occupants, scores)
        views.append(
            TableView(
                table_id=table.id,
                number=table.number,
                label=table.label,
                capacity=_capacity_of(table),
                occupants=tuple(occupants),
                score=score,
                quality=quality_of(score, len(occupants), threshold),
            )
        )
    return views


# --- Takas ---------------------------------------------------------------------


class SwapRejected(Exception):
    """Takas hiç yapılamadı — uyarı değil, ret.

    Yalnızca sabitlenmiş atama ve tutarsız istek bu yola düşüyor. Kural
    ihlalleri uyarı olarak dönüyor, takası engellemiyor (M7).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def apply_swap(
    session: AsyncSession,
    event: Event,
    plan: Plan,
    *,
    slot_number: int,
    assignment_id: int,
    target_assignment_id: int | None,
    target_table_id: int | None,
) -> tuple[list[TableView], list[SwapWarning]]:
    """İki kişinin yerini değiştirir ya da birini boş yere taşır (M7).

    *"Bir kişiye dokunulur, sonra ikinci kişiye dokunulur, yerleri değişir."*
    Sürükle-bırak yerine takas: mobilde çok daha güvenilir çalışıyor ve aynı
    işi görüyor.
    """
    assignments = await _load_assignments(session, plan.id)
    by_id = {item.id: item for item in assignments}

    first = by_id.get(assignment_id)
    if first is None or first.slot_number != slot_number:
        raise SwapRejected("Taşınacak atama bu turda bulunamadı.")
    if first.is_pinned:
        raise SwapRejected("Bu atama sabitlenmiş; önce sabitlemeyi kaldır.")

    if target_assignment_id is not None:
        second = by_id.get(target_assignment_id)
        if second is None or second.slot_number != slot_number:
            raise SwapRejected("Takas edilecek atama bu turda bulunamadı.")
        if second.is_pinned:
            raise SwapRejected("Karşı atama sabitlenmiş; önce sabitlemeyi kaldır.")
        if second.id == first.id:
            raise SwapRejected("Bir kişi kendisiyle takas edilemez.")

        touched = {first.table_id, second.table_id}
        first.table_id, second.table_id = second.table_id, first.table_id
    else:
        if target_table_id is None:
            raise SwapRejected("Hedef olarak ya bir kişi ya bir masa gerekiyor.")
        tables = {table.id for table in await _load_tables(session, event.id)}
        if target_table_id not in tables:
            raise SwapRejected("Hedef masa bu etkinliğe ait değil.")
        if target_table_id == first.table_id:
            raise SwapRejected("Kişi zaten bu masada.")

        touched = {first.table_id, target_table_id}
        first.table_id = target_table_id

    await session.flush()

    context = await build_engine_input(session, event, seed=plan.seed)
    await _recompute_reasons(session, plan, context, slot_number, touched)
    await session.commit()

    warnings = await _check_after_swap(session, event, plan, slot_number, touched)
    return await build_slot_view(session, event, plan, slot_number), warnings


async def _recompute_reasons(
    session: AsyncSession,
    plan: Plan,
    context: MatchingContext,
    slot_number: int,
    tables: set[int],
) -> None:
    """Etkilenen masaların gerekçelerini yeniden yazar.

    Takas yeni ikililer üretiyor ve onların skoru `match_reasons`'ta yok.
    Satırlar tazelenmezse masa skoru yanlış çıkar ve Aşama 9'da katılımcıya
    olmayan bir gerekçe gösterilir.

    Sinerji modeli yeniden kuruluyor: 200 kişi için 10 ms, saklamaktan ucuz.
    """
    model = build_synergy_model(context.engine_input)

    current = await session.execute(
        select(Assignment).where(
            Assignment.plan_id == plan.id,
            Assignment.slot_number == slot_number,
            Assignment.table_id.in_(tables),
        )
    )
    occupants: dict[int, list[int]] = {table: [] for table in tables}
    for assignment in current.scalars():
        occupants[assignment.table_id].append(assignment.registration_id)

    affected = [
        _pair_key(first, second)
        for people in occupants.values()
        for position, first in enumerate(sorted(people))
        for second in sorted(people)[position + 1 :]
    ]

    # Önce bu masalara ait eski satırlar siliniyor: takas sonrası artık
    # oturmayan ikililerin gerekçesi kalmamalı.
    await session.execute(
        delete(MatchReason).where(
            MatchReason.plan_id == plan.id,
            MatchReason.slot_number == slot_number,
            MatchReason.registration_a_id.in_(
                {person for people in occupants.values() for person in people}
            ),
        )
    )
    await session.execute(
        delete(MatchReason).where(
            MatchReason.plan_id == plan.id,
            MatchReason.slot_number == slot_number,
            MatchReason.registration_b_id.in_(
                {person for people in occupants.values() for person in people}
            ),
        )
    )

    for low, high in affected:
        first_index = context.index_of_registration(low)
        second_index = context.index_of_registration(high)
        if first_index is None or second_index is None:
            continue
        session.add(
            MatchReason(
                plan_id=plan.id,
                slot_number=slot_number,
                registration_a_id=low,
                registration_b_id=high,
                total_score=model.score(first_index, second_index),
                breakdown=dict(model.explain(first_index, second_index)),
            )
        )
    await session.flush()


async def _check_after_swap(
    session: AsyncSession,
    event: Event,
    plan: Plan,
    slot_number: int,
    tables: set[int],
) -> list[SwapWarning]:
    """M7'nin saydığı kontroller, takastan **sonra**.

    Yalnızca dokunulan masalara bakılıyor: planın başka bir köşesindeki eski
    bir sorun bu takasın uyarısı gibi görünmemeli.
    """
    threshold = get_settings().matching_quality_threshold
    assignments = await _load_assignments(session, plan.id)
    table_rows = {table.id: table for table in await _load_tables(session, event.id)}
    scores = await _pair_scores(session, plan.id)

    warnings: list[SwapWarning] = []

    # Bu ikili başka bir slotta zaten eşleşiyor mu (9.5 "tekrar yok").
    pairs_elsewhere: dict[tuple[int, int], int] = {}
    by_slot_table: dict[tuple[int, int], list[Assignment]] = {}
    for assignment in assignments:
        by_slot_table.setdefault((assignment.slot_number, assignment.table_id), []).append(
            assignment
        )

    for (slot, _table), people in by_slot_table.items():
        if slot == slot_number:
            continue
        ordered = sorted(item.registration_id for item in people)
        for position, first in enumerate(ordered):
            for second in ordered[position + 1 :]:
                pairs_elsewhere.setdefault((first, second), slot)

    for table_id in sorted(tables):
        table = table_rows.get(table_id)
        if table is None:
            continue
        occupants = [_person(a) for a in by_slot_table.get((slot_number, table_id), [])]
        names = tuple(person.full_name or "Adı girilmemiş" for person in occupants)

        if len(occupants) > _capacity_of(table):
            warnings.append(SwapWarning(OVER_CAPACITY, table_number=table.number, people=names))

        if len(occupants) == 1:
            warnings.append(SwapWarning(LONELY_TABLE, table_number=table.number, people=names))

        seen: dict[str, SeatedPerson] = {}
        for person in occupants:
            if person.company is None:
                continue
            if person.company in seen:
                warnings.append(
                    SwapWarning(
                        SAME_COMPANY,
                        table_number=table.number,
                        people=(
                            seen[person.company].full_name or "Adı girilmemiş",
                            person.full_name or "Adı girilmemiş",
                        ),
                    )
                )
            else:
                seen[person.company] = person

        for position, first in enumerate(occupants):
            for second in occupants[position + 1 :]:
                key = _pair_key(first.registration_id, second.registration_id)
                if key in pairs_elsewhere:
                    warnings.append(
                        SwapWarning(
                            REPEAT_PAIR,
                            table_number=table.number,
                            people=(
                                first.full_name or "Adı girilmemiş",
                                second.full_name or "Adı girilmemiş",
                            ),
                            slot_number=pairs_elsewhere[key],
                        )
                    )

        score = table_score(occupants, scores)
        if len(occupants) >= 2 and score < threshold:
            warnings.append(SwapWarning(QUALITY_DROPPED, table_number=table.number, people=names))

    return warnings


# --- Sabitleme ------------------------------------------------------------------


async def set_pinned(session: AsyncSession, plan: Plan, assignment_id: int, pinned: bool) -> None:
    """*"Sabitlenen atama, motor tekrar çalıştırılsa bile değişmez."* (M7)"""
    result = await session.execute(
        select(Assignment).where(Assignment.id == assignment_id, Assignment.plan_id == plan.id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise SwapRejected("Atama bulunamadı.")
    assignment.is_pinned = pinned
    await session.commit()


# --- Yayınlama -------------------------------------------------------------------


async def publish(session: AsyncSession, event: Event, plan: Plan) -> None:
    """Planı yayına alır, öncekini arşive (M7, 5.2).

    Koşullu benzersiz indeks bir etkinlikte tek yayın planına izin veriyor
    (Aşama 1). Sıra bilinçli: önce eski arşive alınıyor, sonra yenisi
    yayınlanıyor — tersi indeksi ihlal ederdi.
    """
    if plan.job_status is not JobStatus.DONE:
        raise SwapRejected("Hesabı bitmemiş plan yayınlanamaz.")

    previous = await session.execute(
        select(Plan).where(
            Plan.event_id == event.id,
            Plan.status == PlanStatus.PUBLISHED,
            Plan.id != plan.id,
        )
    )
    for archived in previous.scalars():
        archived.status = PlanStatus.ARCHIVED
    await session.flush()

    plan.status = PlanStatus.PUBLISHED
    plan.published_at = datetime.now(UTC)
    await session.commit()
