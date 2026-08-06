"""Motorun girdi ve çıktı sözleşmesi (şartname 9.2).

Hepsi sade, donmuş veri yapıları. Motor veritabanı kimliği bilmez; kendi içinde
`0..N-1` tam sayı indeks kullanır ve dönüşüm dış katmanda yapılır. Sebep 9.2'de:
motor hızlı kalsın.

Bu modül `app` tarafındaki enum'ları bilerek tekrar tanımlar. Motor uygulama
katmanını import edemez (5.1); ortak bir tip paylaşmak o sınırı delerdi. İki
tarafı eşleştirmek Aşama 7'de dönüşüm katmanının işi.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from engine.weights import DEFAULT_WEIGHTS, SynergyWeights


class TableKind(StrEnum):
    SEATED = "seated"
    STANDING = "standing"


# --- Girdi ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Participant:
    """Eşleştirmeye giren kişi.

    Etiketler, sektör ve şehir tam sayı kimliklerle taşınır — motor metin
    karşılaştırması yapmaz. Şirket kimliği kritik: aynı şirketten iki kişi aynı
    masaya oturamaz (9.5) ve bu karşılaştırma serbest metinle değil kimlikle
    yapılır (Bölüm 6).
    """

    index: int
    company: int
    offered_tags: frozenset[int] = frozenset()
    sought_tags: frozenset[int] = frozenset()
    sector: int | None = None
    city: int | None = None


@dataclass(frozen=True, slots=True)
class TableSpec:
    """Masa.

    `capacity` kesin üst sınırdır: oturmalı masada sandalye sayısı, ayaklı masada
    organizatörün girdiği üst sınır (9.5).

    `target_min` yalnızca ayaklı masalarda anlamlıdır ve **hedeftir, kural
    değildir** — motor ona ulaşmaya çalışır ama kalite pahasına zorlamaz. Kesin
    olan tek alt sınır "asgari grup" kuralıdır: kullanılan masada en az iki kişi.
    """

    index: int
    kind: TableKind
    capacity: int
    target_min: int | None = None


@dataclass(frozen=True, slots=True)
class MeetingRequestPair:
    """Katılımcının "bu kişiyle görüşmek istiyorum" bildirimi (M9)."""

    requester: int
    target: int


@dataclass(frozen=True, slots=True)
class FixedAssignment:
    """Çapa kişi veya organizatörün kilitlediği atama.

    Motor bunu hiç oynatmaz (9.5, Adım 2).
    """

    slot: int
    table: int
    participant: int


@dataclass(frozen=True, slots=True)
class EngineSettings:
    """Çalıştırma ayarları (9.2).

    Varsayılanlar `.env` dosyasındaki `MATCHING_*` değerleriyle aynı; gerçek
    değerler dış katmandan geçirilir.
    """

    # 9.6 adalet kuralı: her katılımcı en az bu kadar **turda** masada oturmalı.
    # Birimin tur olduğuna dikkat: 9.6'daki başarısızlık hikâyesi slot sayıyor.
    min_meetings_per_person: int = 4

    # 9.5 esnek kural: bu skorun altındaki ikili tercih edilmez. Mutlak yasak
    # değildir — adalet düzeltmesi (Adım 5) gerekirse eşiği esnetir.
    quality_threshold: float = 0.35

    # Eşiğin altında kalan masanın amaç fonksiyonundaki cezası, eksik kalan puan
    # başına. 9.5 kalite eşiğini "skorla yönetilen esnek kural" olarak tarif
    # ediyor — kesin yasak değil, ama tercih edilmeyen.
    #
    # Bu terim olmadan amaç fonksiyonu boş masa ile kötü masayı aynı görüyordu:
    # ikisi de 0 puan. Yerel arama da bu yüzden iki uyumsuz kişiyi oturtmayı
    # bedelsiz sanıyordu. Oysa 9.5: "Boş sandalye, kötü eşleşmeden iyidir."
    threshold_penalty: float = 3.0

    # 5.3: aynı girdi + aynı tohum = birebir aynı çıktı.
    seed: int = 42

    # Adım 4'ün deneme bütçesi.
    max_iterations: int = 100_000

    # 9.8: minimum değişim modunda yeri değişen her kişi için ceza. Yüksek
    # tutulur ki motor gerekmedikçe kimseyi kıpırdatmasın.
    move_penalty: float = 5.0

    # Amaç fonksiyonunda adalet teriminin ağırlığı (9.6).
    #
    #   amaç = adalet_ağırlığı × Σ min(oturulan_tur, hedef) + Σ masa_skoru
    #
    # `min(x, hedef)` tavanı sayesinde hedefin altındaki birini bir tur daha
    # oturtmak puan kazandırır, hedefi zaten tutturmuş birini oturtmak
    # kazandırmaz. Arama böylece en kötü durumdakine yönelir.
    #
    # Değer masa skorlarına göre yüksek: adalet kesin kural, kalite ondan sonra
    # gelir. Herkes hedefi tutturunca terim sabitlenir ve yalnızca kalite
    # optimize edilmeye devam eder.
    fairness_weight: float = 2.0

    weights: SynergyWeights = field(default_factory=lambda: DEFAULT_WEIGHTS)


@dataclass(frozen=True, slots=True)
class EngineInput:
    """Motora verilen her şey."""

    participants: tuple[Participant, ...]
    tables: tuple[TableSpec, ...]
    slot_count: int
    requests: tuple[MeetingRequestPair, ...] = ()
    fixed_assignments: tuple[FixedAssignment, ...] = ()

    # 9.8 minimum değişim modu: doluysa Adım 3 atlanır, bu plan başlangıç olur.
    previous_plan: tuple["Assignment", ...] | None = None

    # 9.8: başlamış veya bitmiş slotlara dokunulmaz.
    frozen_slots: frozenset[int] = frozenset()

    # Check-in'de gelmediği işaretlenenler (9.8, M10). Bu kişiler hiçbir masaya
    # oturtulmaz.
    #
    # Katılımcı listesinden silinmiyorlar, çünkü motor indeks tabanlı çalışıyor:
    # listeden çıkarmak indeksleri kaydırır ve `previous_plan` içindeki
    # referanslar başka kişilere işaret ederdi.
    absent_participants: frozenset[int] = frozenset()

    settings: EngineSettings = field(default_factory=EngineSettings)

    def validate(self) -> None:
        """Sözleşmeyi bozan girdiyi erken yakalar.

        Motor sessizce yanlış sonuç üretmektense açılmamalı: indeks kayması
        eşleştirmeyi bozar ama hata vermez, aylar sonra fark edilir.
        """
        for position, participant in enumerate(self.participants):
            if participant.index != position:
                raise ValueError(
                    f"Katılımcı indeksleri 0'dan başlayarak sıralı olmalı: "
                    f"{position}. sırada {participant.index} var."
                )
        for position, table in enumerate(self.tables):
            if table.index != position:
                raise ValueError(
                    f"Masa indeksleri 0'dan başlayarak sıralı olmalı: "
                    f"{position}. sırada {table.index} var."
                )
        if self.slot_count < 1:
            raise ValueError("Slot sayısı en az 1 olmalı.")
        for table in self.tables:
            if table.capacity < 1:
                raise ValueError(f"Masa {table.index} için kapasite en az 1 olmalı.")

        participant_count = len(self.participants)
        table_count = len(self.tables)
        for fixed in self.fixed_assignments:
            if not 0 <= fixed.slot < self.slot_count:
                raise ValueError(f"Sabit atamada geçersiz slot: {fixed.slot}")
            if not 0 <= fixed.table < table_count:
                raise ValueError(f"Sabit atamada geçersiz masa: {fixed.table}")
            if not 0 <= fixed.participant < participant_count:
                raise ValueError(f"Sabit atamada geçersiz katılımcı: {fixed.participant}")

        for slot in self.frozen_slots:
            if not 0 <= slot < self.slot_count:
                raise ValueError(f"Dondurulmuş slot aralık dışında: {slot}")
        for participant in self.absent_participants:
            if not 0 <= participant < participant_count:
                raise ValueError(f"Gelmeyen katılımcı aralık dışında: {participant}")

        if self.frozen_slots and self.previous_plan is None:
            raise ValueError("Slot dondurmak için önceki plan gerekir (şartname 9.8).")


# --- Çıktı ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Assignment:
    """Bir kişinin bir slottaki yeri.

    Kişi bir slotta hiçbir masaya atanmamışsa o slot için satır oluşmaz
    (Bölüm 6).
    """

    slot: int
    table: int
    participant: int


@dataclass(frozen=True, slots=True)
class PairReason:
    """Aynı masada oturan bir ikilinin skor kırılımı (Adım 6).

    `components` hangi bileşenden kaç puan geldiğini söyler; katılımcıya
    gösterilecek Türkçe cümle bundan üretilir. **Sayı katılımcıya
    gösterilmez** (M8, Bölüm 13) — `total_score` organizatör tarafı ve hata
    ayıklama içindir.
    """

    slot: int
    participant_a: int
    participant_b: int
    total_score: float
    components: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class EngineSummary:
    """Çalıştırma özeti (9.2).

    "Görüşme" birimi **turdur**: kişinin masada oturduğu slot sayısı.
    """

    total_meetings: int
    min_meetings_per_person: int
    participants_below_target: tuple[int, ...]
    unmatched_participants: tuple[int, ...]
    satisfied_requests: int
    total_requests: int
    average_table_score: float
    moved_participants: int
    runtime_ms: int


@dataclass(frozen=True, slots=True)
class EngineOutput:
    assignments: tuple[Assignment, ...]
    reasons: tuple[PairReason, ...]
    summary: EngineSummary
