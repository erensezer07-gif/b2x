"""Veritabanı ↔ motor dönüşümü (şartname 5.1, 9.2).

Motor sınırının uygulama tarafındaki karşılığı burası. Motor veritabanı
bilmez; `0..N-1` tam sayı indeksle çalışır ve kimlikleri hiç görmez. İki
yöndeki çeviri tek yerde toplandı ki indeks kayması diye bir sorun olmasın —
9.2 bu riski açıkça uyarıyor: kayma eşleştirmeyi bozar ama hata vermez.

## Kimlik → indeks

Katılımcılar **başvuru kimliğine göre sıralanır** ve o sırayla indekslenir.
Sıralama şart: motor deterministik (5.3) ama girdisi deterministik değilse
aynı veriden farklı planlar çıkar. Aynı gerekçeyle masalar numaraya göre
sıralanıyor.

## Metin → tam sayı

Motor metin karşılaştırmaz. Şirket, sektör ve etiket zaten kimlik; **şehir
serbest metin** olduğu için burada normalleştirilip numaralandırılıyor. Aynı
normalleştirme kalıbı `app/services/company.py`'de.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    Assignment,
    Event,
    Layout,
    MatchReason,
    MeetingRequest,
    MeetingRequestStatus,
    Plan,
    Profile,
    ProfileTag,
    Registration,
    RegistrationStatus,
    Table,
    TableKind,
    TagDirection,
    User,
)
from app.services.company import normalize_company_name
from app.services.profile import evaluate_profile
from engine.types import EngineInput, EngineOutput, EngineSettings, MeetingRequestPair, TableSpec
from engine.types import Participant as EngineParticipant
from engine.types import TableKind as EngineTableKind


@dataclass(frozen=True, slots=True)
class MatchingContext:
    """Motora giden girdi ve indeksleri kimliklere geri çeviren haritalar.

    Motor çıktısı indeks konuşuyor; satırları yazabilmek için geri dönüş
    lazım. İkisi birlikte üretiliyor ki ayrışmasınlar.
    """

    engine_input: EngineInput
    registration_ids: tuple[int, ...]
    table_ids: tuple[int, ...]

    def registration_of(self, index: int) -> int:
        return self.registration_ids[index]

    def table_of(self, index: int) -> int:
        return self.table_ids[index]


def _city_key(city: str | None) -> str | None:
    """Şehri karşılaştırılabilir hale getirir.

    Profilde serbest metin: "İzmir", "izmir", "Izmir" aynı şehir. Şirket
    adındaki normalleştirmenin aynısı yeterli — orada da amaç aynı yazımların
    tek kimliğe inmesi.
    """
    if city is None:
        return None
    normalized = normalize_company_name(city)
    return normalized or None


def _engine_kind(kind: TableKind) -> EngineTableKind:
    """Uygulama enum'unu motorunkine çevirir.

    İki ayrı enum bilerek var: motor uygulama katmanını import edemez (5.1).
    Ortak bir tip paylaşmak o sınırı delerdi.
    """
    return EngineTableKind.SEATED if kind is TableKind.SEATED else EngineTableKind.STANDING


async def _load_accepted_registrations(session: AsyncSession, event_id: int) -> list[Registration]:
    """Kabul edilmiş başvurular, profilleriyle birlikte.

    Yalnızca **kabul edilenler** eşleştirmeye giriyor: bekleyen bir başvuru
    henüz katılımcı değil (Bölüm 4 sözlüğü).
    """
    result = await session.execute(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == RegistrationStatus.ACCEPTED,
        )
        .options(
            selectinload(Registration.user)
            .selectinload(User.profile)
            # Etiketin kategorisi 9.3'ün kısmi puanı için gerekli; aynı sorguda
            # geliyor, yoksa katılımcı başına bir sorgu daha olurdu.
            .options(selectinload(Profile.tags).selectinload(ProfileTag.tag))
        )
        .order_by(Registration.id)
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


async def _load_requests(
    session: AsyncSession, event_id: int, position_of: dict[int, int]
) -> tuple[MeetingRequestPair, ...]:
    """Aktif görüşme talepleri (M9).

    Talep sistemi Aşama 10'da açılıyor; şu an tablo boş kalıyor ama dönüşüm
    hazır. Tarafı kabul edilmemiş talep atlanıyor: motorun indeks evreninde
    yeri yok.
    """
    result = await session.execute(
        select(MeetingRequest).where(
            MeetingRequest.event_id == event_id,
            MeetingRequest.status == MeetingRequestStatus.ACTIVE,
        )
    )
    pairs = []
    for request in result.scalars():
        requester = position_of.get(request.requester_registration_id)
        target = position_of.get(request.target_registration_id)
        if requester is not None and target is not None:
            pairs.append(MeetingRequestPair(requester=requester, target=target))
    return tuple(pairs)


def _tag_ids(profile: Profile | None, direction: TagDirection) -> frozenset[int]:
    if profile is None:
        return frozenset()
    return frozenset(link.tag_id for link in profile.tags if link.direction is direction)


def _category_ids(profile: Profile | None, direction: TagDirection) -> frozenset[int]:
    """Etiketlerin kategorileri (9.3 kısmi puan).

    Motor türetemez: etiket→kategori haritası veritabanında. Burada
    çıkarılıyor.
    """
    if profile is None:
        return frozenset()
    return frozenset(
        link.tag.category_id for link in profile.tags if link.direction is direction and link.tag
    )


async def build_engine_input(
    session: AsyncSession, event: Event, *, seed: int | None = None
) -> MatchingContext:
    """Etkinliğin verisini motorun girdisine çevirir."""
    settings = get_settings()
    registrations = await _load_accepted_registrations(session, event.id)
    tables = await _load_tables(session, event.id)

    position_of = {item.id: index for index, item in enumerate(registrations)}

    # Şirket kimliği zorunlu (motor `int` istiyor). Şirketi girilmemiş kişi
    # kimseyle çakışmasın diye negatif ve benzersiz bir değer alıyor: iki
    # şirketsiz kişi "aynı şirketten" sayılmamalı.
    cities: dict[str, int] = {}
    participants = []
    for index, registration in enumerate(registrations):
        profile = registration.user.profile
        city_key = _city_key(profile.city if profile else None)
        if city_key is not None and city_key not in cities:
            cities[city_key] = len(cities)

        participants.append(
            EngineParticipant(
                index=index,
                company=(
                    profile.company_id
                    if profile is not None and profile.company_id is not None
                    else -(index + 1)
                ),
                offered_tags=_tag_ids(profile, TagDirection.OFFERED),
                sought_tags=_tag_ids(profile, TagDirection.SOUGHT),
                offered_categories=_category_ids(profile, TagDirection.OFFERED),
                sought_categories=_category_ids(profile, TagDirection.SOUGHT),
                sector=profile.sector_id if profile is not None else None,
                city=cities[city_key] if city_key is not None else None,
            )
        )

    table_specs = tuple(
        TableSpec(
            index=index,
            kind=_engine_kind(table.kind),
            capacity=table.seat_count or table.max_people or 0,
            target_min=table.min_people,
        )
        for index, table in enumerate(tables)
    )

    engine_input = EngineInput(
        participants=tuple(participants),
        tables=table_specs,
        slot_count=event.slot_count,
        requests=await _load_requests(session, event.id, position_of),
        settings=EngineSettings(
            min_meetings_per_person=settings.matching_min_meetings_per_person,
            quality_threshold=settings.matching_quality_threshold,
            max_iterations=settings.matching_max_iterations,
            move_penalty=settings.matching_move_penalty,
            seed=seed if seed is not None else settings.matching_default_seed,
        ),
    )
    engine_input.validate()

    return MatchingContext(
        engine_input=engine_input,
        registration_ids=tuple(item.id for item in registrations),
        table_ids=tuple(item.id for item in tables),
    )


def build_rows(
    plan: Plan, context: MatchingContext, output: EngineOutput
) -> tuple[list[Assignment], list[MatchReason]]:
    """Motor çıktısını veritabanı satırlarına çevirir.

    Slot numaraları **1'den** başlıyor: motor 0 tabanlı indeks kullanıyor ama
    katılımcı "Tur 1" görüyor ve şema `slot_number > 0` şart koşuyor.
    """
    assignments = [
        Assignment(
            plan_id=plan.id,
            slot_number=item.slot + 1,
            table_id=context.table_of(item.table),
            registration_id=context.registration_of(item.participant),
        )
        for item in output.assignments
    ]

    reasons = []
    for reason in output.reasons:
        first = context.registration_of(reason.participant_a)
        second = context.registration_of(reason.participant_b)
        # Şema ikiliyi kanonik sırada istiyor; aksi hâlde aynı çift iki kez
        # yazılabilirdi.
        low, high = (first, second) if first < second else (second, first)
        reasons.append(
            MatchReason(
                plan_id=plan.id,
                slot_number=reason.slot + 1,
                registration_a_id=low,
                registration_b_id=high,
                total_score=reason.total_score,
                breakdown=dict(reason.components),
            )
        )

    return assignments, reasons


@dataclass(frozen=True, slots=True)
class MatchingCheck:
    """Çalıştırma öncesi kontrol listesi (M6).

    *"Sorun varsa organizatör uyarılır ama çalıştırma engellenmez."* Bu yüzden
    hiçbir alan "engelle" demiyor; `warnings` yalnızca anahtar taşıyor, Türkçe
    cümleyi arayüz kuruyor.
    """

    accepted_count: int
    table_count: int
    seating_capacity: int
    request_count: int
    incomplete_profile_count: int
    slot_count: int
    requests_open: bool
    warnings: tuple[str, ...]

    @property
    def can_run(self) -> bool:
        """Motor çalışabilir mi — en az iki kişi ve bir masa gerekiyor."""
        return self.accepted_count >= 2 and self.table_count >= 1


# Kontrol listesindeki uyarı anahtarları. Türkçesi arayüzde.
NO_PARTICIPANTS = "no_participants"
NO_TABLES = "no_tables"
CAPACITY_BELOW_PARTICIPANTS = "capacity_below_participants"
INCOMPLETE_PROFILES = "incomplete_profiles"
REQUESTS_STILL_OPEN = "requests_still_open"


async def build_matching_check(session: AsyncSession, event: Event) -> MatchingCheck:
    """M6'nın istediği kontrol listesi."""
    registrations = await _load_accepted_registrations(session, event.id)
    tables = await _load_tables(session, event.id)
    position_of = {item.id: index for index, item in enumerate(registrations)}
    requests = await _load_requests(session, event.id, position_of)

    seating_capacity = sum(table.seat_count or table.max_people or 0 for table in tables)
    incomplete = sum(
        1
        for registration in registrations
        if registration.user.profile is None
        or not evaluate_profile(registration.user.profile).can_apply
    )

    # Talep sistemi kapanmadan çalıştırılırsa sonradan gelecek talepler bu
    # plana yansımaz (M6). Kapanış zamanı verilmemişse sistem hiç kapanmamış
    # sayılıyor.
    requests_open = event.requests_close_at is None or datetime.now(UTC) <= event.requests_close_at

    warnings = []
    if not registrations:
        warnings.append(NO_PARTICIPANTS)
    if not tables:
        warnings.append(NO_TABLES)
    if registrations and seating_capacity < len(registrations):
        warnings.append(CAPACITY_BELOW_PARTICIPANTS)
    if incomplete:
        warnings.append(INCOMPLETE_PROFILES)
    if requests_open:
        warnings.append(REQUESTS_STILL_OPEN)

    return MatchingCheck(
        accepted_count=len(registrations),
        table_count=len(tables),
        seating_capacity=seating_capacity,
        request_count=len(requests),
        incomplete_profile_count=incomplete,
        slot_count=event.slot_count,
        requests_open=requests_open,
        warnings=tuple(warnings),
    )
