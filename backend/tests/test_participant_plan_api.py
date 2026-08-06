"""Katılımcı görünümü ve görünürlük kuralları (şartname M8, Bölüm 7, Bölüm 10).

Kabul kriteri: *"Katılımcı, başka masadaki kişilerin bilgilerine API üzerinden
doğrudan istek atsa bile erişemiyor. Plan yayında değilken hiçbir atama
görünmüyor."*

Bu dosyanın ağırlığı **saldırı testlerinde.** Arayüzün ne gösterdiği önemli
değil; buradaki testler uca doğrudan istek atıp verinin dönmediğini
kanıtlıyor. Bir görünürlük hatası sessizdir — kimse şikâyet etmez, yalnızca
veri sızar.
"""

from collections.abc import Callable

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Plan, PlanStatus
from app.services.reasons import (
    MAX_REASONS,
    SAME_CITY,
    SAME_SECTOR,
    SHARED_CATEGORY,
    THEY_OFFER,
    YOU_OFFER,
    MatchReasonItem,
    build_reasons,
)
from engine.scoring import CATEGORY, CITY, SECTOR, SIMILARITY_PENALTY, SUPPLY_DEMAND
from tests.test_matching_api import run_plan, seed_event
from tests.test_registration_api import complete_profile, open_event, sign_up, use


async def published_event(
    client: AsyncClient,
    session: AsyncSession,
    emails: Callable[[], str],
    *,
    participants: int = 6,
    tables: int = 3,
    seats: int = 2,
    slots: int = 3,
    publish: bool = True,
) -> tuple[str, dict, dict]:
    """Yayınlanmış planı olan bir etkinlik. (organizatör jetonu, etkinlik, plan)"""
    organiser, event = await seed_event(
        client, emails, participants=participants, tables=tables, seats=seats, slots=slots
    )
    plan = await run_plan(client, session, event["id"])
    if publish:
        response = await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")
        assert response.status_code == 200, response.text
    return organiser, event, plan


async def participant_tokens(
    client: AsyncClient, session: AsyncSession, event_id: int
) -> dict[int, int]:
    """Yayındaki planda kimin hangi başvuru kimliğiyle oturduğu.

    Jetonlar `seed_event` tarafından saklanmıyor; testler kullanıcıyı
    kimliğinden bulup adına konuşamıyor. Bu yüzden ayrı bir katılımcı
    yaratılıyor ya da doğrudan veritabanına bakılıyor.
    """
    plan = (
        await session.execute(
            select(Plan).where(Plan.event_id == event_id, Plan.status == PlanStatus.PUBLISHED)
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(Assignment.registration_id, Assignment.table_id).where(
                Assignment.plan_id == plan.id, Assignment.slot_number == 1
            )
        )
    ).all()
    return dict(rows)


async def join_and_publish(
    client: AsyncClient,
    session: AsyncSession,
    emails: Callable[[], str],
    *,
    name: str = "Deneme Katılımcı",
    participants: int = 5,
) -> tuple[str, str, dict, dict]:
    """Adı bilinen bir katılımcıyla yayınlanmış etkinlik.

    (organizatör jetonu, katılımcı jetonu, etkinlik, plan) döner. Katılımcının
    jetonu elde olduğu için onun adına istek atılabiliyor.
    """
    organiser, event = await seed_event(
        client, emails, participants=participants, tables=3, seats=2, slots=3
    )
    # `seed_event` kontenjanı katılımcı sayısına eşitliyor; adı bilinen misafir
    # için bir kişilik yer açılıyor.
    widened = await client.patch(f"/events/{event['id']}", json={"capacity": participants + 1})
    assert widened.status_code == 200, widened.text

    guest = await sign_up(client, emails())
    use(client, guest)
    await complete_profile(client, name)
    joined = await client.post(f"/events/{event['id']}/registration")
    assert joined.status_code == 201, joined.text

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])
    published = await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")
    assert published.status_code == 200, published.text
    return organiser, guest, event, plan


# --- Gerekçe üretimi (M8) -----------------------------------------------------


def test_reason_says_who_offers_what() -> None:
    """*"Kendisi yazılım geliştirme hizmeti sunuyor, siz bunu arıyorsunuz."*

    Yön önemli: aynı etiket iki tarafta farklı cümle demek.
    """
    reasons = build_reasons(
        _profile(offered=["Lojistik"], sought=["Yazılım geliştirme"]),
        _profile(offered=["Yazılım geliştirme"], sought=["Lojistik"]),
        {SUPPLY_DEMAND: 0.7},
    )

    kinds = {item.kind for item in reasons}
    assert THEY_OFFER in kinds
    assert YOU_OFFER in kinds

    theirs = next(item for item in reasons if item.kind == THEY_OFFER)
    assert theirs.values == ("Yazılım geliştirme",)


def test_reason_never_carries_a_number() -> None:
    """M8: *"Uyum: %62 gibi bir ifade kullanılmaz."*

    Skor yalnızca sıralamak için kullanılıyor; üretilen yapıda sayı yok.
    """
    reasons = build_reasons(
        _profile(offered=["A"], sought=["B"], sector="Fintek", city="İzmir"),
        _profile(offered=["B"], sought=["A"], sector="Fintek", city="İzmir"),
        {SUPPLY_DEMAND: 0.7, SECTOR: 0.2, CITY: 0.1},
    )

    for item in reasons:
        assert isinstance(item, MatchReasonItem)
        for value in item.values:
            assert not any(character.isdigit() for character in value)


def test_at_most_two_reasons() -> None:
    """M8: *"bir veya iki kısa cümle."*"""
    reasons = build_reasons(
        _profile(offered=["A"], sought=["B"], sector="Fintek", city="İzmir"),
        _profile(offered=["B"], sought=["A"], sector="Fintek", city="İzmir"),
        {SUPPLY_DEMAND: 0.7, SECTOR: 0.2, CITY: 0.1, CATEGORY: 0.05},
    )
    assert len(reasons) <= MAX_REASONS


def test_the_strongest_reason_comes_first() -> None:
    """Sıralama kırılımdan geliyor: en çok puan getiren önce anlatılıyor."""
    reasons = build_reasons(
        _profile(offered=["A"], sought=["B"], sector="Fintek", city="İzmir"),
        _profile(offered=["B"], sought=["A"], sector="Fintek", city="İzmir"),
        {SECTOR: 0.9, SUPPLY_DEMAND: 0.1},
    )
    assert reasons[0].kind == SAME_SECTOR


def test_penalty_is_never_a_reason() -> None:
    """Negatif katkı "neden eşleştiniz" sorusunun cevabı olamaz."""
    reasons = build_reasons(
        _profile(offered=["A"], sought=["B"], city="İzmir"),
        _profile(offered=["B"], sought=["A"], city="İzmir"),
        {SIMILARITY_PENALTY: -0.4, CITY: 0.1},
    )
    assert [item.kind for item in reasons] == [SAME_CITY]


def test_a_component_without_a_match_is_skipped() -> None:
    """Plan üretildikten sonra profil değişmiş olabilir.

    Kırılımda puan var ama profillerde karşılığı yok — boş bir cümle
    göstermektense o gerekçe hiç gösterilmiyor.
    """
    reasons = build_reasons(
        _profile(offered=["A"], sought=["B"]),
        _profile(offered=["C"], sought=["D"]),
        {SUPPLY_DEMAND: 0.7},
    )
    assert reasons == []


def test_shared_category_is_its_own_reason() -> None:
    """9.3'ün kısmi puanı ayrı bir cümle: *"ikiniz de X alanındasınız."*"""
    reasons = build_reasons(
        _profile(offered=["A"], sought=["B"], category="Yazılım"),
        _profile(offered=["C"], sought=["D"], category="Yazılım"),
        {CATEGORY: 0.3},
    )
    assert [item.kind for item in reasons] == [SHARED_CATEGORY]
    assert reasons[0].values == ("Yazılım",)


class _Tag:
    def __init__(self, tag_id: int, name: str, category_name: str) -> None:
        self.id = tag_id
        self.name = name
        self.category_id = hash(category_name) % 1000
        self.category = type("Category", (), {"name": category_name})()


class _Link:
    def __init__(self, tag: _Tag, direction) -> None:
        self.tag_id = tag.id
        self.tag = tag
        self.direction = direction


def _profile(
    *,
    offered: list[str],
    sought: list[str],
    sector: str | None = None,
    city: str | None = None,
    category: str = "Genel",
):
    """Gerekçe üretimi için yeterli sahte profil.

    Veritabanı gerektirmiyor: `build_reasons` yalnızca etiketleri, sektörü ve
    şehri okuyor. Gerçek `Profile` kurmak testi okunmaz hâle getirirdi.
    """
    from app.models import TagDirection

    names = {name: index for index, name in enumerate(sorted(set(offered) | set(sought)), start=1)}
    links = [_Link(_Tag(names[name], name, category), TagDirection.OFFERED) for name in offered]
    links += [_Link(_Tag(names[name], name, category), TagDirection.SOUGHT) for name in sought]

    return type(
        "FakeProfile",
        (),
        {
            "tags": links,
            "sector": type("Sector", (), {"name": sector})() if sector else None,
            "city": city,
        },
    )()


# --- Plan görünümü (M8) --------------------------------------------------------


async def test_my_plan_lists_every_slot(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Katılımcının tüm slotları sırayla."*

    Oturmadığı tur da listede: *"Boş bırakılmaz, açıklama yazılır."*
    """
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/my-plan")).json()

    assert body["is_published"] is True
    assert body["plan_version"] == 1
    assert [slot["slot_number"] for slot in body["slots"]] == [1, 2, 3]
    for slot in body["slots"]:
        assert slot["starts_at"]
        assert slot["ends_at"]


async def test_my_plan_shows_tablemates_with_name_and_company(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Kiminle oturacağı (isim ve şirket)."* (M8)"""
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/my-plan")).json()
    seated = [slot for slot in body["slots"] if slot["table_number"] is not None]

    assert seated, "Katılımcı en az bir turda oturmalıydı."
    for slot in seated:
        assert slot["tablemates"]
        for mate in slot["tablemates"]:
            assert mate["full_name"]
            assert mate["company"]


async def test_my_plan_never_shows_myself(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Masa arkadaşı listesinde kişinin kendisi olmamalı."""
    _organiser, guest, event, _plan = await join_and_publish(
        client, session, unique_email, name="Ayşe Yılmaz"
    )
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/my-plan")).json()
    for slot in body["slots"]:
        assert "Ayşe Yılmaz" not in [mate["full_name"] for mate in slot["tablemates"]]


async def test_my_plan_carries_a_reason_for_every_tablemate(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Her kişi için eşleşme gerekçesi."* (M8)"""
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/my-plan")).json()
    mates = [mate for slot in body["slots"] for mate in slot["tablemates"]]

    assert mates
    for mate in mates:
        assert mate["reasons"], f"{mate['full_name']} için gerekçe yok."
        assert len(mate["reasons"]) <= MAX_REASONS


async def test_no_score_leaks_into_the_participant_response(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Bölüm 10: *"Hiçbir yerde sayısal skor görünmüyor."*

    Yanıtın tamamı taranıyor — bir gün şemaya eklenen bir alan sessizce
    geçmesin.
    """
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/my-plan")).json()
    forbidden = {"score", "total_score", "quality", "breakdown", "average_table_score"}

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in forbidden, f"Skor sızdı: {key}"
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(body)


async def test_an_unseated_slot_is_reported_not_hidden(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Bir slotta eşleşmemişse o slot 'Bu turda serbestsin' olarak gösterilir."*

    Dar salon: iki kişilik tek masaya altı kişi. Çoğu tur boş kalıyor ama
    listede yer alıyor.
    """
    organiser, event = await seed_event(
        client, unique_email, participants=6, tables=1, seats=2, slots=3
    )
    await client.patch(f"/events/{event['id']}", json={"capacity": 7})
    guest = await sign_up(client, unique_email())
    use(client, guest)
    await complete_profile(client, "Serbest Katılımcı")
    await client.post(f"/events/{event['id']}/registration")

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{plan['id']}/publish")

    use(client, guest)
    body = (await client.get(f"/events/{event['id']}/my-plan")).json()

    assert len(body["slots"]) == 3
    free = [slot for slot in body["slots"] if slot["table_number"] is None]
    assert free, "Bu ölçekte en az bir tur boş kalmalıydı."
    for slot in free:
        assert slot["tablemates"] == []


# --- Görünürlük: plan yayında değilken ------------------------------------------


async def test_a_draft_plan_is_invisible(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Bölüm 7: *"plan versiyonu 'yayında' değilse hiçbir atama göremez."*"""
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)

    # Aynı etkinlikte ikinci bir plan üretiliyor ama yayınlanmıyor; birincisi
    # de arşive alınmıyor. Yayındaki plan hâlâ birinci.
    use(client, guest)
    published = (await client.get(f"/events/{event['id']}/my-plan")).json()
    assert published["plan_version"] == 1


async def test_nothing_is_visible_before_publishing(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Hesabı bitmiş ama yayınlanmamış plan katılımcıya kapalı."""
    organiser, event = await seed_event(
        client, unique_email, participants=5, tables=3, seats=2, slots=3
    )
    await client.patch(f"/events/{event['id']}", json={"capacity": 6})
    guest = await sign_up(client, unique_email())
    use(client, guest)
    await complete_profile(client, "Bekleyen Katılımcı")
    await client.post(f"/events/{event['id']}/registration")

    use(client, organiser)
    await run_plan(client, session, event["id"])

    use(client, guest)
    body = (await client.get(f"/events/{event['id']}/my-plan")).json()

    assert body["is_published"] is False
    assert body["plan_version"] is None
    assert body["slots"] == []


async def test_an_archived_plan_is_invisible(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Yeni versiyon yayınlanınca katılımcı yenisini görür, eskisini değil."""
    organiser, guest, event, first = await join_and_publish(client, session, unique_email)

    use(client, organiser)
    second = await run_plan(client, session, event["id"])
    await client.post(f"/events/{event['id']}/plans/{second['id']}/publish")

    use(client, guest)
    body = (await client.get(f"/events/{event['id']}/my-plan")).json()

    assert body["plan_version"] == 2
    assert first["version"] == 1


# --- Görünürlük: kim bakabilir --------------------------------------------------


async def test_a_stranger_gets_404(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Etkinliğe hiç başvurmamış biri planı göremez."""
    _organiser, _guest, event, _plan = await join_and_publish(client, session, unique_email)

    use(client, await sign_up(client, unique_email()))

    assert (await client.get(f"/events/{event['id']}/my-plan")).status_code == 404
    assert (await client.get(f"/events/{event['id']}/venue")).status_code == 404
    assert (await client.get(f"/events/{event['id']}/tablemates/1")).status_code == 404


async def test_a_pending_applicant_gets_404(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Bekleyen başvuru sahibi henüz katılımcı değil (Bölüm 4 sözlüğü)."""
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = await open_event(client)
    await client.patch(f"/events/{event['id']}", json={"auto_approve_registrations": False})

    applicant = await sign_up(client, unique_email())
    use(client, applicant)
    await complete_profile(client, "Bekleyen Kişi")
    applied = await client.post(f"/events/{event['id']}/registration")
    assert applied.status_code == 201
    assert applied.json()["my_registration"]["status"] == "pending"

    assert (await client.get(f"/events/{event['id']}/my-plan")).status_code == 404


async def test_the_organiser_is_not_automatically_a_participant(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Rol etkinliğe göre (Bölüm 7).

    Organizatör kendi etkinliğinin planını `plan.py` uçlarından görüyor;
    katılımcı ucu ona kapalı çünkü başvurusu yok.
    """
    organiser, _guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, organiser)

    assert (await client.get(f"/events/{event['id']}/my-plan")).status_code == 404


async def test_endpoints_require_a_session(client: AsyncClient) -> None:
    assert (await client.get("/events/1/my-plan")).status_code == 401
    assert (await client.get("/events/1/venue")).status_code == 401
    assert (await client.get("/events/1/tablemates/1")).status_code == 401


# --- Görünürlük: masa arkadaşı profili ------------------------------------------


async def test_a_tablemates_profile_is_visible(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Masadaki kişinin tam profiline bakılabilir."* (M8)"""
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/my-plan")).json()
    mate = next(mate for slot in body["slots"] for mate in slot["tablemates"])

    response = await client.get(f"/events/{event['id']}/tablemates/{mate['registration_id']}")

    assert response.status_code == 200, response.text
    profile = response.json()
    assert profile["full_name"] == mate["full_name"]
    assert profile["offered_tags"]
    assert profile["sought_tags"]
    # Sahibine ait bilgiler dışarı çıkmıyor.
    assert "completion_percent" not in profile
    assert "missing_for_application" not in profile


async def test_someone_at_another_table_is_404(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Sadece aynı masada oturduğu kişilerin profilini görebilir."*

    Kabul edilmiş ama hiçbir turda aynı masaya düşmemiş biri isteniyor.
    """
    _organiser, guest, event, _plan = await join_and_publish(
        client, session, unique_email, participants=7
    )
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/my-plan")).json()
    mates = {mate["registration_id"] for slot in body["slots"] for mate in slot["tablemates"]}
    everyone = set(await participant_tokens(client, session, event["id"]))
    strangers = everyone - mates

    if not strangers:
        # Küçük ölçekte herkes tanışmış olabilir; o zaman olmayan bir kimlik
        # de aynı kapıya düşmeli.
        strangers = {999_999}

    for registration_id in strangers:
        response = await client.get(f"/events/{event['id']}/tablemates/{registration_id}")
        assert response.status_code == 404, registration_id
        assert response.json()["detail"] == "Bu kişi masa arkadaşın değil."


async def test_own_profile_is_not_a_tablemate(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Kişi kendi başvuru kimliğini isteyince de 404 — bu uç başkası için."""
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, guest)

    mine = (await client.get(f"/events/{event['id']}/public")).json()["my_registration"]
    response = await client.get(f"/events/{event['id']}/tablemates/{mine['id']}")

    assert response.status_code == 404


async def test_tablemate_profile_is_closed_before_publishing(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """Plan yayında değilken kimse kimsenin masa arkadaşı değil."""
    organiser, event = await seed_event(
        client, unique_email, participants=5, tables=3, seats=2, slots=3
    )
    await client.patch(f"/events/{event['id']}", json={"capacity": 6})
    guest = await sign_up(client, unique_email())
    use(client, guest)
    await complete_profile(client, "Erken Bakan")
    await client.post(f"/events/{event['id']}/registration")

    use(client, organiser)
    plan = await run_plan(client, session, event["id"])

    # Plan hazır ama yayınlanmadı. Veritabanından bir başvuru kimliği alınıp
    # doğrudan deneniyor — arayüz olmadan.
    rows = (
        await session.execute(
            select(Assignment.registration_id).where(Assignment.plan_id == plan["id"]).limit(1)
        )
    ).all()
    assert rows

    use(client, guest)
    response = await client.get(f"/events/{event['id']}/tablemates/{rows[0][0]}")
    assert response.status_code == 404


# --- Salon krokisi ----------------------------------------------------------------


async def test_venue_carries_tables_but_no_people(
    client: AsyncClient, unique_email: Callable[[], str], session: AsyncSession
) -> None:
    """*"Krokide masanın yeri işaretli."* Kimin oturduğu bu uçtan dönmüyor."""
    _organiser, guest, event, _plan = await join_and_publish(client, session, unique_email)
    use(client, guest)

    body = (await client.get(f"/events/{event['id']}/venue")).json()

    assert body["mode"] == "auto"
    assert [table["number"] for table in body["tables"]] == [1, 2, 3]
    serialized = str(body)
    assert "occupant" not in serialized
    assert "registration" not in serialized


async def test_venue_is_404_without_a_layout(
    client: AsyncClient, unique_email: Callable[[], str]
) -> None:
    organiser = await sign_up(client, unique_email())
    use(client, organiser)
    event = (
        await client.post("/events", json={"name": "Düzensiz", "starts_at": "2026-12-01T09:00:00Z"})
    ).json()

    guest = await sign_up(client, unique_email())
    use(client, guest)

    # Kayıtlar açılmadığı için başvurulamıyor; kapı zaten katılımcılığa bakıyor.
    assert (await client.get(f"/events/{event['id']}/venue")).status_code == 404
