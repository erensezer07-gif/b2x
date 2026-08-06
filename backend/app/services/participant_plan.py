"""Katılımcının kendi planı (şartname M8, Bölüm 7).

Bölüm 7'nin görünürlük kuralları burada uygulanıyor ve **hepsi sunucuda**:

> Katılımcı kendi atamalarını görür · kendi masasındaki kişilerin profillerini
> görür · **başka masalarda kimin oturduğunu göremez** · ilgili plan versiyonu
> "yayında" değilse hiçbir atama göremez.
>
> Bu kural API seviyesinde uygulanır. "Arayüzde göstermiyoruz" yeterli değil —
> istek doğrudan atılsa bile veri dönmemeli.

Bu yüzden hiçbir uç `registration_id` parametresi almıyor: kimlik jetondan
geliyor. Başkasının planını istemek diye bir istek biçimi yok.

Masa arkadaşı listesi de sorgudan çıkıyor, süzgeçten değil: önce kişinin
kendi ataması bulunuyor, sonra **yalnızca o masanın** oturanları okunuyor.
Bütün planı çekip fazlasını atmak, bir gün atmayı unutmaya davetiye olurdu.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Assignment,
    Event,
    Layout,
    LayoutArea,
    MatchReason,
    Plan,
    PlanStatus,
    Profile,
    ProfileTag,
    Registration,
    RegistrationStatus,
    Table,
    Tag,
    User,
)
from app.services.reasons import MatchReasonItem, build_reasons
from app.services.schedule import build_schedule


@dataclass(frozen=True, slots=True)
class Tablemate:
    """Aynı masada oturan biri (M8: *"fotoğraf, ad, unvan, şirket"*)."""

    registration_id: int
    profile: Profile | None
    reasons: tuple[MatchReasonItem, ...]


@dataclass(frozen=True, slots=True)
class MySlot:
    """Katılımcının bir turu.

    `table` yoksa o turda oturmuyor — M8: *"Bir slotta eşleşmemişse o slot
    'Bu turda serbestsin' olarak gösterilir. Boş bırakılmaz."*
    """

    slot_number: int
    starts_at: datetime
    ends_at: datetime
    table: Table | None
    tablemates: tuple[Tablemate, ...]


@dataclass(frozen=True, slots=True)
class MyPlan:
    """Katılımcının gördüğü planın tamamı.

    Plan yayında değilse `slots` yine dolu (her tur "serbestsin") değil —
    **boş**. `is_published` yanlışken hiçbir atama okunmuyor bile.
    """

    is_published: bool
    plan_version: int | None
    slots: tuple[MySlot, ...]


async def published_plan(session: AsyncSession, event_id: int) -> Plan | None:
    """Etkinliğin yayındaki planı.

    Koşullu benzersiz indeks (Aşama 1) en fazla bir tane olmasını garanti
    ediyor. Taslak ve arşiv planlar buradan **hiç** dönmüyor: katılımcı
    yalnızca yayındakini görebilir.
    """
    result = await session.execute(
        select(Plan).where(Plan.event_id == event_id, Plan.status == PlanStatus.PUBLISHED)
    )
    return result.scalar_one_or_none()


def _profile_options():
    """Gerekçe ve kart için gereken ilişkiler.

    Etiketin **kategorisi** de yükleniyor: kısmi puan gerekçesi kategori adını
    yazıyor (9.3) ve yüklenmezse kişi başına bir sorgu daha açılırdı.
    """
    return (
        selectinload(Registration.user)
        .selectinload(User.profile)
        .options(
            selectinload(Profile.company),
            selectinload(Profile.sector),
            # Etiketin kategorisine kadar iniliyor. Yüklenmezse `_categories`
            # eşzamansız bir yeniden yükleme tetikler ve `MissingGreenlet`
            # verir — hata yolu değil, doğrudan yanıt yolu kırılır.
            selectinload(Profile.tags).selectinload(ProfileTag.tag).selectinload(Tag.category),
        ),
    )


async def accepted_registration(
    session: AsyncSession, event_id: int, user_id: int
) -> Registration | None:
    """Kullanıcının bu etkinlikteki **kabul edilmiş** başvurusu.

    Bekleyen veya reddedilmiş başvuru sahibi katılımcı değil (Bölüm 4
    sözlüğü); planda yeri yok, plana da bakamaz.

    Profili de yükleniyor: gerekçe üretimi *"siz bunu arıyorsunuz"* diyebilmek
    için bakanın kendi etiketlerine ihtiyaç duyuyor. Yüklenmezse yanıt yolunda
    `MissingGreenlet` çıkar.
    """
    result = await session.execute(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.user_id == user_id,
            Registration.status == RegistrationStatus.ACCEPTED,
        )
        .options(*_profile_options())
    )
    return result.scalar_one_or_none()


async def _my_assignments(
    session: AsyncSession, plan_id: int, registration_id: int
) -> list[Assignment]:
    result = await session.execute(
        select(Assignment)
        .where(Assignment.plan_id == plan_id, Assignment.registration_id == registration_id)
        .options(selectinload(Assignment.table))
        .order_by(Assignment.slot_number)
    )
    return list(result.scalars())


async def _seatmates(
    session: AsyncSession, plan_id: int, seats: list[tuple[int, int]], me: int
) -> dict[tuple[int, int], list[Registration]]:
    """Verilen (tur, masa) çiftlerinin oturanları — kendisi hariç.

    Yalnızca kişinin oturduğu masalar soruluyor. Planın tamamını çekip
    süzmek aynı sonucu verirdi ama bir gün süzgeç unutulursa bütün plan
    dışarı sızardı; sorgu dar tutuluyor.
    """
    if not seats:
        return {}

    conditions = [
        (Assignment.slot_number == slot) & (Assignment.table_id == table) for slot, table in seats
    ]
    combined = conditions[0]
    for condition in conditions[1:]:
        combined = combined | condition

    result = await session.execute(
        select(Assignment)
        .where(Assignment.plan_id == plan_id, Assignment.registration_id != me, combined)
        .options(
            selectinload(Assignment.registration).options(*_profile_options()),
        )
        .order_by(Assignment.slot_number, Assignment.id)
    )

    grouped: dict[tuple[int, int], list[Registration]] = {}
    for assignment in result.scalars():
        key = (assignment.slot_number, assignment.table_id)
        grouped.setdefault(key, []).append(assignment.registration)
    return grouped


async def _breakdowns(
    session: AsyncSession, plan_id: int, me: int
) -> dict[tuple[int, int], dict[str, float]]:
    """(tur, karşı taraf) → skor kırılımı.

    Yalnızca kişinin kendi satırları: `match_reasons` başkalarının
    eşleşmelerini de taşıyor.
    """
    result = await session.execute(
        select(
            MatchReason.slot_number,
            MatchReason.registration_a_id,
            MatchReason.registration_b_id,
            MatchReason.breakdown,
        ).where(
            MatchReason.plan_id == plan_id,
            (MatchReason.registration_a_id == me) | (MatchReason.registration_b_id == me),
        )
    )
    return {
        (slot, second if first == me else first): breakdown
        for slot, first, second, breakdown in result.all()
    }


async def build_my_plan(session: AsyncSession, event: Event, registration: Registration) -> MyPlan:
    """Katılımcının gördüğü plan (M8).

    Yayında plan yoksa boş dönüyor — atamalar okunmuyor bile.
    """
    plan = await published_plan(session, event.id)
    if plan is None:
        return MyPlan(is_published=False, plan_version=None, slots=())

    schedule = build_schedule(
        starts_at=event.starts_at,
        slot_count=event.slot_count,
        slot_duration_minutes=event.slot_duration_minutes,
        break_duration_minutes=event.break_duration_minutes,
    ).slots

    assignments = await _my_assignments(session, plan.id, registration.id)
    by_slot = {item.slot_number: item for item in assignments}
    seatmates = await _seatmates(
        session,
        plan.id,
        [(item.slot_number, item.table_id) for item in assignments],
        registration.id,
    )
    breakdowns = await _breakdowns(session, plan.id, registration.id)
    viewer = registration.user.profile

    slots = []
    for timing in schedule:
        assignment = by_slot.get(timing.number)
        mates: list[Tablemate] = []
        if assignment is not None:
            for other in seatmates.get((assignment.slot_number, assignment.table_id), []):
                profile = other.user.profile
                mates.append(
                    Tablemate(
                        registration_id=other.id,
                        profile=profile,
                        reasons=tuple(
                            build_reasons(
                                viewer,
                                profile,
                                breakdowns.get((timing.number, other.id), {}),
                            )
                        ),
                    )
                )

        slots.append(
            MySlot(
                slot_number=timing.number,
                starts_at=timing.starts_at,
                ends_at=timing.ends_at,
                table=assignment.table if assignment else None,
                tablemates=tuple(mates),
            )
        )

    return MyPlan(is_published=True, plan_version=plan.version, slots=tuple(slots))


async def visible_profile(
    session: AsyncSession, event: Event, viewer: Registration, target_registration_id: int
) -> Profile | None:
    """Masa arkadaşının profili — **yalnızca** masa arkadaşıysa.

    M8: *"sadece aynı masada oturduğu kişilerin profilini görebilir."*
    Yayındaki planın herhangi bir turunda aynı masada oturmak yetiyor;
    hangi tur olduğu önemli değil.

    Masa arkadaşı değilse `None` — uç bunu 404'e çeviriyor. 403 "böyle biri
    var ama göremezsin" bilgisini sızdırırdı.
    """
    plan = await published_plan(session, event.id)
    if plan is None or target_registration_id == viewer.id:
        return None

    mine = select(Assignment.slot_number, Assignment.table_id).where(
        Assignment.plan_id == plan.id, Assignment.registration_id == viewer.id
    )
    seats = [(slot, table) for slot, table in (await session.execute(mine)).all()]
    shared = await _seatmates(session, plan.id, seats, viewer.id)

    for people in shared.values():
        for registration in people:
            if registration.id == target_registration_id:
                return registration.user.profile
    return None


async def load_venue(
    session: AsyncSession, event_id: int
) -> tuple[Layout | None, list[Table], list[LayoutArea]]:
    """Salon krokisi — **kimin nerede oturduğu yok**.

    Masa numaraları ve yerleri sır değil; katılımcı kendi masasını krokide
    bulabilmeli (M8). Sır olan kimin oturduğu ve o bu uçtan hiç dönmüyor.
    """
    layout = (
        await session.execute(select(Layout).where(Layout.event_id == event_id))
    ).scalar_one_or_none()
    if layout is None:
        return None, [], []

    tables = list(
        (
            await session.execute(
                select(Table).where(Table.layout_id == layout.id).order_by(Table.number)
            )
        ).scalars()
    )
    areas = list(
        (
            await session.execute(
                select(LayoutArea).where(LayoutArea.layout_id == layout.id).order_by(LayoutArea.id)
            )
        ).scalars()
    )
    return layout, tables, areas
