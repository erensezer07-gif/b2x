"""Check-in modelleri (şartname M10)."""

from datetime import datetime

from pydantic import BaseModel


class MyQrResponse(BaseModel):
    """Katılımcının kendi giriş kodu.

    Kod metin olarak dönüyor, görsel olarak değil: M10 *"internet olmasa bile
    görüntülenebilmeli"* diyor ve sunucudan görsel çekmek bunu bozardı. QR'ı
    istemci çiziyor.
    """

    registration_id: int
    qr_code: str

    # Zaten okutulduysa katılımcı da görsün — kapıda ikinci kez sıraya
    # girmesin.
    checked_in_at: datetime | None


class AttendeeResponse(BaseModel):
    """Check-in listesindeki bir satır.

    *"Okunan kişi 'geldi' olarak işaretlenir, ekranda adı ve fotoğrafı
    belirir."* (M10)
    """

    registration_id: int
    full_name: str | None
    title: str | None
    company: str | None
    photo_url: str | None

    present: bool
    checked_in_at: datetime | None


class AttendanceResponse(BaseModel):
    """Liste ve sayaç.

    *"Sayaç sürekli görünür: kaç kişi geldi, kaç kişi bekleniyor."* Sayaç
    listeyle birlikte geliyor ve **süzgeçten etkilenmiyor**: arama yaparken
    "kaç kişi kaldı" bilgisi kaybolmamalı.
    """

    attendees: list[AttendeeResponse]
    accepted_count: int
    present_count: int
    expected_count: int


class ScanRequest(BaseModel):
    qr_code: str


class MarkAttendanceRequest(BaseModel):
    present: bool


class ScanResponse(BaseModel):
    """Okuma sonucu: kim okundu ve güncel sayaç.

    İkisi birlikte dönüyor ki ekran ikinci bir istek atmasın — kapıda sıra
    beklemiyor.
    """

    attendee: AttendeeResponse
    accepted_count: int
    present_count: int
    expected_count: int

    # Aynı kod ikinci kez okutulduysa. Hata değil (kapıda olur), ama ekran
    # "zaten girmişti" diyebilmeli.
    already_present: bool


class SeatChangeResponse(BaseModel):
    """*"Kimin yeri değişti"* (M10).

    `before` boşsa kişi o turda yeni yerleştirilmiş, `after` boşsa masadan
    çıkmış.
    """

    registration_id: int
    name: str
    slot_number: int
    before: int | None
    after: int | None


class PlanChangesResponse(BaseModel):
    """İki plan arasındaki fark.

    9.8'in sözü burada ölçülüyor: *"gerekmedikçe kimseyi kıpırdatma."*
    `moved_people` kaç **kişinin** (satırın değil) yeri değiştiğini söylüyor.
    """

    previous_plan_id: int | None
    changes: list[SeatChangeResponse]
    moved_people: int
