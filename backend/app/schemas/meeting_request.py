"""Görüşme talebi modelleri (şartname M9).

**Gelen talep şeması yok.** M9: *"Talep gönderildiği kişiye bildirilmez.
Karşı taraf kimin kendisini istediğini görmez."* Katılımcı yalnızca kendi
gönderdiklerini görüyor; okunacak bir şema olmadığı için sızacak bir alan da
yok.
"""

from pydantic import BaseModel


class ParticipantRowResponse(BaseModel):
    """Katılımcı listesindeki bir satır.

    M9: *"Listede ad, unvan, şirket, sektör görünür."* Tam profil burada yok —
    o yalnızca aynı masaya düşen kişiler için açılıyor (Bölüm 7).
    """

    registration_id: int
    full_name: str | None
    title: str | None
    company: str | None
    sector: str | None
    photo_url: str | None

    # Doluysa **ben** bu kişiye talep göndermişim; geri çekmek için kimlik.
    # Karşı tarafın bana talep gönderip göndermediği burada yok.
    my_request_id: int | None


class ParticipantListResponse(BaseModel):
    """Katılımcı listesi ve talep hakkım.

    Hak listeyle birlikte geliyor: ekran "kaç hakkım kaldı" için ikinci bir
    istek atmasın.
    """

    participants: list[ParticipantRowResponse]

    request_quota: int
    requests_used: int
    requests_remaining: int

    # *"Talepler bir zamanda kapanır."* Kapalıysa arayüz düğmeleri kapatıyor;
    # asıl kapı serviste.
    requests_open: bool


class SendRequestBody(BaseModel):
    target_registration_id: int


class UnmetRequestResponse(BaseModel):
    """Karşılanmayan bir talep — **organizatör** görünümü (M9).

    Karşılanmış talepler hiç dönmüyor: yapılacak bir şey kalmamış.
    """

    requester_registration_id: int
    target_registration_id: int
    requester_name: str
    target_name: str

    # *"Neredeyse kesin eşleşme."* Karşılanmadıysa gerçek bir kusur.
    mutual: bool

    # İki tarafın da oturduğu ama farklı masalara düştüğü ilk tur — takasla
    # düzeltilebilecek yer. Biri hiç oturmuyorsa boş.
    fixable_slot: int | None
