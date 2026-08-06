"""Plan önizleme ve elle düzeltme (şartname M7, Bölüm 10).

Kabul kriterleri: *"Organizatör her slotu görebiliyor. İki kişi takas
edildiğinde kural ihlali anında uyarı olarak çıkıyor. En az görüşme alan
kişinin sayısı özet panelde görünüyor."* · *"Bir etkinlikte aynı anda birden
fazla plan yayında olamıyor."*

Testlerin kurduğu düzen bilinçli: **iki sandalyeli masalar.** Böylece dolu masa
her zaman tam dolu (kapasite uyarısı bir hamleyle kuruluyor), bir kişi
çıkarılınca masa tek kişilik kalıyor ve boş masa hep elde. Ölçek küçük ama
M7'nin saydığı bütün kontroller tetikleniyor.

Uyarıların doğruluğu ayrıca **bağımsız bir gözle** sınanıyor: her takastan
sonra plan `engine/rules.py` içindeki `find_violations`'tan geçiriliyor ve
orada bulunan her ihlal türünün uçtan da uyarı olarak döndüğü doğrulanıyor.
"""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Event, Plan, PlanStatus, Profile, Registration, User
from app.services.matching import build_engine_input
from app.services.plan_editing import (
    LONELY_TABLE,
    OVER_CAPACITY,
    QUALITY_DROPPED,
    REPEAT_PAIR,
    SAME_COMPANY,
    SeatedPerson,
    TableQuality,
    quality_of,
    table_score,
)
from engine.rules import (
    CAPACITY,
    COMPANY_SEPARATION,
    MINIMUM_GROUP,
    NO_REPEAT,
    find_violations,
)
from engine.types import Assignment as EngineAssignment
from tests.test_matching_api import run_plan, seed_event
from tests.test_registration_api import open_event, sign_up, use

# Motorun kural adı → ucun uyarı anahtarı. İkisi ayrı yazıldı (biri metin
# üretiyor, diğeri arayüzün işleyeceği yapı); bu harita ikisini karşılaştırmak
# için var.
RULE_TO_KEY = {
    CAPACITY: OVER_CAPACITY,
    MINIMUM_GROUP: LONELY_TABLE,
    COMPANY_SEPARATION: SAME_COMPANY,
    NO_REPEAT: REPEAT_PAIR,
}


async def seed_plan(
    client: AsyncClient,
    session: AsyncSession,
    emails: Callable[[], str],
    *,
    participants: int = 6,
    tables: int = 4,
    seats: int = 2,
    slots: int = 3,
) -> tuple[dict, dict]:
    """Hesabı bitmiş bir plan üretir; (etkinlik, plan) döner."""
    _organiser, event = await seed_event(
        client, emails, participants=participants, tables=tables, seats=seats, slots=slots
    )
    plan = await run_plan(client, session, event["id"])
    return event, plan


async def read_slot(client: AsyncClient, event: dict, plan: dict, slot: int = 1) -> dict:
    response = await client.get(f"/events/{event['id']}/plans/{plan['id']}/slots/{slot}")
    assert response.status_code == 200, response.text
    return response.json()


async def swap(client: AsyncClient, event: dict, plan: dict, **body) -> dict:
    response = await client.post(f"/events/{event['id']}/plans/{plan['id']}/swap", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def occupied(slot: dict) -> list[dict]:
    return [table for table in slot["tables"] if table["occupants"]]


def empty(slot: dict) -> list[dict]:
    return [table for table in slot["tables"] if not table["occupants"]]


def seat_of(slot: dict, assignment_id: int) -> int:
    """Bir atamanın hangi masada olduğu."""
    for table in slot["tables"]:
        for person in table["occupants"]:
            if person["assignment_id"] == assignment_id:
                return table["table_id"]
    raise AssertionError(f"{assignment_id} numaralı atama bu turda yok.")


def keys(result: dict) -> set[str]:
    return {warning["key"] for warning in result["warnings"]}


async def engine_violations(session: AsyncSession, event_id: int, plan_id: int) -> set[str]:
    """Planı motorun bağımsız denetleyicisinden geçirir; ihlal türlerini döner."""
    stored = await session.get(Event, event_id)
    context = await build_engine_input(session, stored)
    rows = (
        await session.execute(select(Assignment).where(Assignment.plan_id == plan_id))
    ).scalars()

    engine_rows = []
    for row in rows:
        participant = context.index_of_registration(row.registration_id)
        table = context.index_of_table(row.table_id)
        if participant is None or table is None:
            continue
        engine_rows.append(
            EngineAssignment(slot=row.slot_number - 1, table=table, participant=participant)
        )

    return {
        violation.rule for violation in find_violations(context.engine_input, tuple(engine_rows))
    }


def assert_second_eye_agrees(violations: set[str], result: dict) -> None:
    """Motorun bulduğu her ihlal türü uçtan da uyarı olarak dönmeli."""
    reported = keys(result)
    for rule in violations:
        expected = RULE_TO_KEY.get(rule)
        assert expected is not None, f"Bilinmeyen kural: {rule}"
        assert expected in reported, f"{rule} ihlali var ama {expected} uyarısı dönmedi."


# --- Masa skoru ve kalite seviyeleri -----------------------------------------


def person(registration_id: int) -> SeatedPerson:
    return SeatedPerson(
        assignment_id=registration_id,
        registration_id=registration_id,
        full_name=f"Kişi {registration_id}",
        company=None,
        is_pinned=False,
    )


def links(**pairs: float) -> dict[tuple[int, int], float]:
    """`links(ab=0.9)` → {(1, 2): 0.9}. Harfler kimliğe çevriliyor: a=1, b=2..."""
    return {(ord(name[0]) - 96, ord(name[1]) - 96): score for name, score in pairs.items()}


def test_table_score_on_a_pair_is_the_pair_itself() -> None:
    """İki kişilik masada eski ölçütle birebir aynı olmalı."""
    assert table_score([person(1), person(2)], links(ab=0.62)) == 0.62


def test_table_score_asks_whether_anyone_is_left_out() -> None:
    """*"En yalnız kişinin en iyi bağı."* (M7)

    Üç kişilik masa: a–b çok iyi, ikisi de c ile zayıf. En zayıf ikili 0.10
    ama asıl soru c'nin durumu — onun da en iyi bağı 0.10, yani masa zayıf.
    """
    table = [person(1), person(2), person(3)]
    assert table_score(table, links(ab=0.90, ac=0.10, bc=0.10)) == 0.10


def test_table_score_does_not_collapse_with_table_size() -> None:
    """Herkes birisiyle iyi anlaşıyorsa masa iyi — herkesle değil.

    Altı kişilik masada üç iyi ikili var, kalan on iki bağ zayıf. En zayıf
    ikiliye bakan ölçüt 0.05 derdi ve masa "zayıf" görünürdü; kimse ortada
    kalmadığı hâlde. Ölçümde altı sandalyeli masaların hiçbiri "iyi"
    alamıyordu, sebebi buydu.
    """
    table = [person(index) for index in range(1, 7)]
    scores = dict.fromkeys(
        ((first, second) for first in range(1, 7) for second in range(first + 1, 7)),
        0.05,
    )
    scores[(1, 2)] = 0.80
    scores[(3, 4)] = 0.75
    scores[(5, 6)] = 0.70

    assert table_score(table, scores) == 0.70
    assert quality_of(table_score(table, scores), 6, 0.35) is TableQuality.GOOD


def test_a_missing_pair_counts_as_the_worst() -> None:
    """Takas sonrası satır yazılmamış ikili sessizce yüksek sayılmamalı."""
    assert table_score([person(1), person(2)], {}) == 0.0


def test_quality_levels_are_absolute() -> None:
    """*"Sayı değil, üç seviye."* Sınırlar eşiğe bağlı ve **mutlak**.

    Kötü bir planda "iyi" masa çıkmamalı: aynı renk her zaman aynı şeyi
    anlatıyor. Göreli olsaydı organizatör kötü bir planı iyi sanırdı.
    """
    threshold = 0.35

    assert quality_of(0.0, 0, threshold) is TableQuality.EMPTY
    # Tek kişilik masanın skoru yok; renk "boş" kalıyor.
    assert quality_of(0.9, 1, threshold) is TableQuality.EMPTY

    assert quality_of(0.34, 2, threshold) is TableQuality.WEAK
    assert quality_of(0.35, 2, threshold) is TableQuality.FAIR
    assert quality_of(0.52, 2, threshold) is TableQuality.FAIR
    assert quality_of(0.525, 2, threshold) is TableQuality.GOOD


# --- Slot görünümü ---------------------------------------------------------------


async def test_slot_view_lists_tables_occupants_and_quality(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Seçili slot için tüm masalar ve kimlerin oturduğu listelenir."* (M7)"""
    event, plan = await seed_plan(client, session, unique_email)

    slot = await read_slot(client, event, plan)

    assert slot["slot_number"] == 1
    assert len(slot["tables"]) == 4
    assert [table["number"] for table in slot["tables"]] == [1, 2, 3, 4]

    for table in slot["tables"]:
        assert table["capacity"] == 2
        assert table["quality"] in {item.value for item in TableQuality}
        for person in table["occupants"]:
            # M7: masa kartında *"ad, şirket"*.
            assert person["full_name"]
            assert person["company"]
            assert person["is_pinned"] is False

    seated = sum(len(table["occupants"]) for table in slot["tables"])
    assert seated == 6


async def test_slot_view_includes_empty_tables(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Boş masa da dönüyor: organizatör boş sandalyeye taşıyabilmeli."""
    event, plan = await seed_plan(client, session, unique_email)

    slot = await read_slot(client, event, plan)

    free = empty(slot)
    assert free, "Dört masaya altı kişi oturunca bir masa boş kalmalıydı."
    assert all(table["quality"] == TableQuality.EMPTY.value for table in free)


async def test_every_slot_is_reachable(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Organizatör her slotu görebiliyor."* (Bölüm 10)"""
    event, plan = await seed_plan(client, session, unique_email, slots=3)

    for number in (1, 2, 3):
        slot = await read_slot(client, event, plan, number)
        assert slot["slot_number"] == number
        assert occupied(slot)


async def test_a_slot_outside_the_event_is_404(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    event, plan = await seed_plan(client, session, unique_email, slots=3)

    response = await client.get(f"/events/{event['id']}/plans/{plan['id']}/slots/9")
    assert response.status_code == 404
    assert "3 tur" in response.json()["detail"]


# --- Takas -------------------------------------------------------------------------


async def test_swap_exchanges_two_people(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Bir kişiye dokunulur, sonra ikinci kişiye dokunulur, yerleri değişir."*"""
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    first_table, second_table = occupied(slot)[:2]
    first = first_table["occupants"][0]
    second = second_table["occupants"][0]

    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=first["assignment_id"],
        target_assignment_id=second["assignment_id"],
    )

    after = result["slot"]
    assert seat_of(after, first["assignment_id"]) == second_table["table_id"]
    assert seat_of(after, second["assignment_id"]) == first_table["table_id"]
    # Kimse kaybolmadı.
    assert sum(len(table["occupants"]) for table in after["tables"]) == 6


async def test_moving_to_an_empty_table_works(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """İkinci kişi yerine hedef masa verilirse kişi oraya taşınıyor."""
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    traveller = occupied(slot)[0]["occupants"][0]
    destination = empty(slot)[0]

    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=traveller["assignment_id"],
        target_table_id=destination["table_id"],
    )

    assert seat_of(result["slot"], traveller["assignment_id"]) == destination["table_id"]


async def test_the_swap_survives_a_reload(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Takas kalıcı: uç yanıtı ile yeniden okunan görünüm aynı olmalı."""
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    first_table, second_table = occupied(slot)[:2]
    moving = first_table["occupants"][0]

    await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=moving["assignment_id"],
        target_assignment_id=second_table["occupants"][0]["assignment_id"],
    )

    reloaded = await read_slot(client, event, plan)
    assert seat_of(reloaded, moving["assignment_id"]) == second_table["table_id"]


async def test_other_slots_are_untouched(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Takas tek turu ilgilendiriyor; diğer turlar olduğu gibi kalmalı."""
    event, plan = await seed_plan(client, session, unique_email)
    before = await read_slot(client, event, plan, 2)
    slot = await read_slot(client, event, plan, 1)

    first_table, second_table = occupied(slot)[:2]
    await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=first_table["occupants"][0]["assignment_id"],
        target_assignment_id=second_table["occupants"][0]["assignment_id"],
    )

    assert await read_slot(client, event, plan, 2) == before


async def test_swap_needs_exactly_one_target(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """İkisi birden ya da hiçbiri geçersiz — istek gövdesi kendini doğruluyor."""
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)
    person = occupied(slot)[0]["occupants"][0]
    url = f"/events/{event['id']}/plans/{plan['id']}/swap"

    neither = await client.post(
        url, json={"slot_number": 1, "assignment_id": person["assignment_id"]}
    )
    assert neither.status_code == 422

    both = await client.post(
        url,
        json={
            "slot_number": 1,
            "assignment_id": person["assignment_id"],
            "target_assignment_id": person["assignment_id"],
            "target_table_id": empty(slot)[0]["table_id"],
        },
    )
    assert both.status_code == 422


async def test_swapping_someone_from_another_slot_is_refused(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    event, plan = await seed_plan(client, session, unique_email)
    other = await read_slot(client, event, plan, 2)
    stranger = occupied(other)[0]["occupants"][0]

    response = await client.post(
        f"/events/{event['id']}/plans/{plan['id']}/swap",
        json={
            "slot_number": 1,
            "assignment_id": stranger["assignment_id"],
            "target_table_id": empty(other)[0]["table_id"],
        },
    )
    assert response.status_code == 409
    assert "bu turda bulunamadı" in response.json()["detail"]


# --- Uyarılar (M7) ------------------------------------------------------------------


async def test_over_capacity_is_a_warning_not_a_block(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Organizatör uyarıya rağmen devam edebilir."*

    İki sandalyeli dolu bir masaya üçüncü kişi taşınıyor. Takas oluyor, uyarı
    dönüyor.
    """
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    source, target = occupied(slot)[:2]
    assert len(target["occupants"]) == target["capacity"], "Hedef masa dolu olmalıydı."
    traveller = source["occupants"][0]

    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=traveller["assignment_id"],
        target_table_id=target["table_id"],
    )

    assert OVER_CAPACITY in keys(result)
    # Takas gerçekten oldu — engellenmedi.
    assert seat_of(result["slot"], traveller["assignment_id"]) == target["table_id"]
    assert_second_eye_agrees(await engine_violations(session, event["id"], plan["id"]), result)


async def test_a_table_left_with_one_person_is_a_warning(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Tek kişi kalan masa var mı."* (M7)

    İki kişilik bir masadan biri boş masaya taşınınca iki masa da tek kişilik
    kalıyor; ikisi için de uyarı çıkmalı.
    """
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    source = occupied(slot)[0]
    destination = empty(slot)[0]

    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=source["occupants"][0]["assignment_id"],
        target_table_id=destination["table_id"],
    )

    lonely = {
        warning["table_number"] for warning in result["warnings"] if warning["key"] == LONELY_TABLE
    }
    assert lonely == {source["number"], destination["number"]}
    assert_second_eye_agrees(await engine_violations(session, event["id"], plan["id"]), result)


async def test_same_company_at_one_table_is_a_warning(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Aynı şirketten iki kişi aynı masada mı."* (M7)

    Kesin kural (9.5) olduğu için motor bunu asla üretmez; ancak organizatör
    elle yapabilir. Test iki katılımcıyı aynı şirkete taşıyıp yan yana
    oturtuyor.
    """
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    source, target = occupied(slot)[:2]
    traveller = source["occupants"][0]
    resident = target["occupants"][0]
    await put_in_same_company(session, traveller["registration_id"], resident["registration_id"])

    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=traveller["assignment_id"],
        target_assignment_id=target["occupants"][1]["assignment_id"],
    )

    company_warnings = [w for w in result["warnings"] if w["key"] == SAME_COMPANY]
    assert company_warnings, keys(result)
    assert company_warnings[0]["table_number"] == target["number"]
    assert set(company_warnings[0]["people"]) == {
        traveller["full_name"],
        resident["full_name"],
    }
    assert_second_eye_agrees(await engine_violations(session, event["id"], plan["id"]), result)


async def put_in_same_company(
    session: AsyncSession, first_registration: int, second_registration: int
) -> None:
    """İki başvurucunun profilini aynı şirkete bağlar.

    Uçtan yapılamıyor: profil sahibinin jetonu gerekir, `seed_event` onları
    saklamıyor. Kural şirket **kimliğine** baktığı için satırı değiştirmek
    yeterli.
    """
    profiles = {}
    for registration_id in (first_registration, second_registration):
        result = await session.execute(
            select(Profile)
            .join(User, User.id == Profile.user_id)
            .join(Registration, Registration.user_id == User.id)
            .where(Registration.id == registration_id)
        )
        profiles[registration_id] = result.scalar_one()

    profiles[second_registration].company_id = profiles[first_registration].company_id
    await session.commit()


async def test_a_pair_meeting_twice_is_a_warning(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Bu ikili başka bir slotta zaten eşleşiyor mu."* (M7)

    2. turda aynı masada oturan bir ikili, 1. turda da yan yana getiriliyor.
    """
    event, plan = await seed_plan(client, session, unique_email)
    second_slot = await read_slot(client, event, plan, 2)
    first_slot = await read_slot(client, event, plan, 1)

    pair = occupied(second_slot)[0]["occupants"]
    assert len(pair) == 2
    left, right = (person["registration_id"] for person in pair)

    # 1. turda `right`'ın masası ve masadaşı. İkili 2. turda buluştuğuna göre
    # 1. turda ayrı oturuyorlar (motor tekrar üretmez), yani masadaş `left`
    # olamaz.
    host_table = next(
        table
        for table in first_slot["tables"]
        if any(person["registration_id"] == right for person in table["occupants"])
    )
    neighbour = next(
        person for person in host_table["occupants"] if person["registration_id"] != right
    )
    visitor = next(
        person
        for table in first_slot["tables"]
        for person in table["occupants"]
        if person["registration_id"] == left
    )

    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=visitor["assignment_id"],
        target_assignment_id=neighbour["assignment_id"],
    )

    # Karşı taraftaki masada da tekrar oluşabilir (yer değiştiren komşu başka
    # birinin eski masadaşı olabilir); aranan uyarı isimle bulunuyor.
    names = {person["full_name"] for person in pair}
    repeats = [
        warning
        for warning in result["warnings"]
        if warning["key"] == REPEAT_PAIR and set(warning["people"]) == names
    ]
    assert repeats, keys(result)
    assert repeats[0]["slot_number"] == 2
    assert repeats[0]["table_number"] == host_table["number"]
    assert_second_eye_agrees(await engine_violations(session, event["id"], plan["id"]), result)


async def test_quality_warning_matches_the_table_grade(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Masa kalitesi nasıl değişti."* (M7)

    Uyarı ile rozet aynı hesaptan geliyor: uyarı çıkan her masa "zayıf"
    görünmeli. İkisi ayrışırsa organizatör yeşil bir masa için kırmızı uyarı
    görürdü.
    """
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    source, target = occupied(slot)[:2]
    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=source["occupants"][0]["assignment_id"],
        target_assignment_id=target["occupants"][0]["assignment_id"],
    )

    weak = {table["number"] for table in result["slot"]["tables"] if table["quality"] == "weak"}
    warned = {w["table_number"] for w in result["warnings"] if w["key"] == QUALITY_DROPPED}
    assert warned <= weak

    # Dokunulan masalardan zayıf olanların hepsi uyarılmış olmalı.
    touched = {source["number"], target["number"]}
    assert touched & weak <= warned


async def test_a_clean_swap_reports_nothing(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Uyarı listesi gürültü olmamalı: kural ihlali yoksa boş dönmeli.

    Aynı iki kişi geri takas ediliyor; plan motorun bıraktığı hâle dönüyor.
    """
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    source, target = occupied(slot)[:2]
    first = source["occupants"][0]["assignment_id"]
    second = target["occupants"][0]["assignment_id"]

    await swap(client, event, plan, slot_number=1, assignment_id=first, target_assignment_id=second)
    back = await swap(
        client, event, plan, slot_number=1, assignment_id=first, target_assignment_id=second
    )

    assert not await engine_violations(session, event["id"], plan["id"])
    assert keys(back) <= {QUALITY_DROPPED}


# --- Sabitleme ------------------------------------------------------------------------


async def test_pinning_and_releasing(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)
    person = occupied(slot)[0]["occupants"][0]
    url = f"/events/{event['id']}/plans/{plan['id']}/assignments/{person['assignment_id']}"

    pinned = await client.patch(url, json={"is_pinned": True})
    assert pinned.status_code == 200
    assert pinned.json()["slot_number"] == 1
    assert _person(pinned.json(), person["assignment_id"])["is_pinned"] is True

    released = await client.patch(url, json={"is_pinned": False})
    assert released.status_code == 200
    assert _person(released.json(), person["assignment_id"])["is_pinned"] is False


def _person(slot: dict, assignment_id: int) -> dict:
    for table in slot["tables"]:
        for occupant in table["occupants"]:
            if occupant["assignment_id"] == assignment_id:
                return occupant
    raise AssertionError(f"{assignment_id} numaralı atama bu turda yok.")


async def test_a_pinned_assignment_cannot_be_swapped(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Sabitlemenin anlamı bu: uyarı değil, ret."""
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)

    source, target = occupied(slot)[:2]
    locked = source["occupants"][0]
    free = target["occupants"][0]

    await client.patch(
        f"/events/{event['id']}/plans/{plan['id']}/assignments/{locked['assignment_id']}",
        json={"is_pinned": True},
    )

    url = f"/events/{event['id']}/plans/{plan['id']}/swap"
    moving = await client.post(
        url,
        json={
            "slot_number": 1,
            "assignment_id": locked["assignment_id"],
            "target_table_id": empty(slot)[0]["table_id"],
        },
    )
    assert moving.status_code == 409
    assert "sabitlenmiş" in moving.json()["detail"]

    # Karşı taraf sabitliyse de reddediliyor.
    incoming = await client.post(
        url,
        json={
            "slot_number": 1,
            "assignment_id": free["assignment_id"],
            "target_assignment_id": locked["assignment_id"],
        },
    )
    assert incoming.status_code == 409

    # Plan gerçekten değişmedi.
    assert (
        seat_of(await read_slot(client, event, plan), locked["assignment_id"])
        == (source["table_id"])
    )


async def test_pinning_an_unknown_assignment_is_404(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    event, plan = await seed_plan(client, session, unique_email)

    response = await client.patch(
        f"/events/{event['id']}/plans/{plan['id']}/assignments/999999",
        json={"is_pinned": True},
    )
    assert response.status_code == 404


# --- Yayınlama ---------------------------------------------------------------------------


async def test_publishing_marks_the_plan(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    event, plan = await seed_plan(client, session, unique_email)

    response = await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")

    assert response.status_code == 200, response.text
    published = response.json()
    assert published["status"] == PlanStatus.PUBLISHED.value
    assert published["published_at"] is not None


async def test_a_new_version_archives_the_previous_one(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Bir etkinlikte aynı anda birden fazla plan yayında olamıyor. Yeni
    versiyon yayınlandığında önceki arşive geçiyor."* (Bölüm 10)"""
    event, first = await seed_plan(client, session, unique_email)
    await client.post(f"/events/{event['id']}/plans/{first['id']}/publish")

    second = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{second['id']}/publish")

    listing = (await client.get(f"/events/{event['id']}/plans")).json()
    by_version = {item["version"]: item["status"] for item in listing}
    assert by_version == {2: PlanStatus.PUBLISHED.value, 1: PlanStatus.ARCHIVED.value}

    # Koşullu benzersiz indeks (Aşama 1) da aynı şeyi söylüyor.
    published = await session.execute(
        select(Plan).where(Plan.event_id == event["id"], Plan.status == PlanStatus.PUBLISHED)
    )
    assert len(published.scalars().all()) == 1


async def test_publishing_twice_is_harmless(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Aynı planı iki kez yayınlamak kendini arşive atmamalı."""
    event, plan = await seed_plan(client, session, unique_email)
    url = f"/events/{event['id']}/plans/{plan['id']}/publish"

    await client.post(url)
    again = await client.post(url)

    assert again.status_code == 200
    assert again.json()["status"] == PlanStatus.PUBLISHED.value


async def test_an_unfinished_plan_cannot_be_published(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    """Hesabı bitmemiş plan yayınlanamaz; `0004`'teki CHECK de engelliyor."""
    _organiser, event = await seed_event(client, unique_email, participants=6, tables=3)
    started = await client.post(f"/events/{event['id']}/plans", json={})
    plan_id = started.json()["id"]

    response = await client.post(f"/events/{event['id']}/plans/{plan_id}/publish")

    assert response.status_code == 409
    assert "bitmemiş" in response.json()["detail"]


async def test_editing_stays_possible_after_publishing(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Yayındaki plan kilitlenmiyor; düzeltme katılımcıya anında yansıyor.

    Spec 469 büyük değişiklikler için yeni versiyon öneriyor, ama tek bir
    düzeltme için yeniden yayın zorunlu değil.
    """
    event, plan = await seed_plan(client, session, unique_email)
    await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")

    slot = await read_slot(client, event, plan)
    source, target = occupied(slot)[:2]
    result = await swap(
        client,
        event,
        plan,
        slot_number=1,
        assignment_id=source["occupants"][0]["assignment_id"],
        target_assignment_id=target["occupants"][0]["assignment_id"],
    )

    assert seat_of(result["slot"], source["occupants"][0]["assignment_id"]) == (target["table_id"])


# --- Özet paneli (M7) --------------------------------------------------------------------


async def test_summary_carries_the_numbers_the_panel_shows(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"En az görüşme alan kişinin sayısı özet panelde görünüyor."* (Bölüm 10)"""
    _event, plan = await seed_plan(client, session, unique_email)

    assert plan["total_meetings"] > 0
    assert plan["min_meetings_per_person"] is not None
    assert plan["participant_count"] == 6
    assert plan["unmatched"] == []
    # Talep sistemi Aşama 10'da açılıyor.
    assert plan["satisfied_requests"] == 0
    assert plan["total_requests"] == 0


async def test_summary_names_people_who_were_never_seated(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Hiç eşleşmemiş kişi var mı, varsa kimler."* (M7)

    Tek masalı, iki sandalyeli bir salona altı kişi giriyor; dördü hiç
    oturamıyor. Organizatör isimleri görüp elle yerleştirebilmeli.
    """
    _event, plan = await seed_plan(client, session, unique_email, tables=1, seats=2, slots=1)

    assert len(plan["unmatched"]) == 4
    assert all(name.startswith("Katılımcı") for name in plan["unmatched"])
    assert plan["participant_count"] == 2


# --- Görünürlük ---------------------------------------------------------------------------


@pytest.mark.parametrize("published", [False, True])
async def test_another_organiser_cannot_touch_the_plan(
    client: AsyncClient,
    unique_email: Callable[[], str],
    session: AsyncSession,
    published: bool,
) -> None:
    """Bölüm 7: başkasının planına erişilemez — yayında olsa bile.

    Katılımcının kendi yerini görmesi Aşama 9'un ayrı uçlarıyla olacak; bu
    uçlar organizatöre özel.
    """
    event, plan = await seed_plan(client, session, unique_email)
    slot = await read_slot(client, event, plan)
    person = occupied(slot)[0]["occupants"][0]
    if published:
        await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")

    use(client, await sign_up(client, unique_email()))
    base = f"/events/{event['id']}/plans/{plan['id']}"

    assert (await client.get(f"{base}/slots/1")).status_code == 404
    assert (
        await client.post(
            f"{base}/swap",
            json={
                "slot_number": 1,
                "assignment_id": person["assignment_id"],
                "target_table_id": empty(slot)[0]["table_id"],
            },
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"{base}/assignments/{person['assignment_id']}", json={"is_pinned": True}
        )
    ).status_code == 404
    assert (await client.post(f"{base}/publish")).status_code == 404


async def test_a_plan_from_another_event_is_404(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Bir etkinliğin kimliğiyle başka etkinliğin planı istenemez.

    Organizatör ikisinin de sahibi; yine de plan o etkinliğe ait değil.
    """
    organiser, event = await seed_event(client, unique_email, participants=6, tables=2, seats=2)
    plan = await run_plan(client, session, event["id"])

    use(client, organiser)
    other = await open_event(client, name="İkinci Etkinlik")

    response = await client.get(f"/events/{other['id']}/plans/{plan['id']}/slots/1")
    assert response.status_code == 404
    assert response.json()["detail"] == "Plan bulunamadı."


async def test_editing_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events/1/plans/1/slots/1")).status_code == 401
    assert (await client.post("/events/1/plans/1/publish")).status_code == 401
    assert (
        await client.patch("/events/1/plans/1/assignments/1", json={"is_pinned": True})
    ).status_code == 401
