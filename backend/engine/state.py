"""Plan durumu: oturma düzeni, karşılaşma geçmişi ve artımlı skor.

Motorun sıcak döngüsü burada. Adım 4 yüz binlerce hamle deneyecek (9.7), bu
yüzden bir kişi taşındığında yalnızca etkilenen masanın skoru yeniden hesaplanır
— plan baştan taranmaz.

## Masa skoru

Şartname 9.4: *"masa skoru, masadaki en zayıf ikili bağın skorudur"* — toplam
değil. Dört kişilik bir masada üçü mükemmel uyumlu, dördüncü herkese alakasızsa
toplama bakan sistem masayı yüksek görür; oysa o dördüncü kişi yarım saat
dışlanmış hisseder.

Kullanılmayan masanın (0 veya 1 kişi) skoru 0'dır. Tek kişilik masa zaten kesin
kurala aykırıdır (9.5).

## Amaç

`objective()` şu değeri döndürür:

```
adalet_ağırlığı × Σ_kişi min(oturulan_tur, hedef)
  + Σ_masa (masa_skoru − eşik_cezası × eşiğin_altında_kalan)
  − taşıma_cezası × yeri_değişen_yerleşim
```

`min(oturulan_tur, hedef)` tavanı, aramayı 9.6'nın istediği gibi en kötü
durumdaki kişiye yöneltir: hedefin altındaki birini oturtmak puan kazandırır,
hedefi tutturmuşu oturtmak kazandırmaz.

Eşik cezası olmadan boş masa ile kötü masa aynı değeri verirdi (ikisi de 0) ve
arama iki uyumsuz kişiyi oturtmayı bedelsiz sanırdı. 9.5: *"Boş sandalye, kötü
eşleşmeden iyidir."*

Taşıma cezası yalnızca minimum değişim modunda (önceki plan verilmişse) devreye
girer (9.8).
"""

import numpy as np

from engine.scoring import SynergyModel
from engine.types import Assignment, EngineInput

# `location` matrisinde "hiçbir masada değil".
UNSEATED = -1


class PlanState:
    """Bir planın değiştirilebilir hâli."""

    def __init__(self, engine_input: EngineInput, model: SynergyModel) -> None:
        self.input = engine_input
        self.model = model
        self.score = model.matrix

        self.participant_count = len(engine_input.participants)
        self.table_count = len(engine_input.tables)
        self.slot_count = engine_input.slot_count

        # seats[slot][table] -> o masada oturanlar
        self.seats: list[list[list[int]]] = [
            [[] for _ in range(self.table_count)] for _ in range(self.slot_count)
        ]

        self.location = np.full((self.slot_count, self.participant_count), UNSEATED, dtype=np.int32)
        self.met = np.zeros((self.participant_count, self.participant_count), dtype=bool)
        self.rounds = np.zeros(self.participant_count, dtype=np.int32)
        self.table_scores = np.zeros((self.slot_count, self.table_count), dtype=np.float64)
        # Kullanılan masa = en az iki kişi. Boş masa ile skoru düşük masayı
        # ayırt edebilmek için gerekli: ikisinin de skoru 0'dır ama yalnızca
        # ikincisi cezalandırılmalı.
        self.used = np.zeros((self.slot_count, self.table_count), dtype=bool)

        self.company = np.array(
            [person.company for person in engine_input.participants], dtype=np.int64
        )
        self.capacity = np.array([table.capacity for table in engine_input.tables], dtype=np.int32)

        # Check-in'de gelmediği işaretlenenler hiçbir masaya oturtulmaz (9.8).
        self.absent = np.zeros(self.participant_count, dtype=bool)
        for participant in engine_input.absent_participants:
            self.absent[participant] = True

        # Sabit atamalar motor tarafından hiç oynatılmaz (9.5, Adım 2).
        self.pinned = np.zeros((self.slot_count, self.participant_count), dtype=bool)
        for fixed in engine_input.fixed_assignments:
            self.pinned[fixed.slot, fixed.participant] = True

        self.previous_location = self._build_previous_location()

    def _build_previous_location(self) -> np.ndarray | None:
        """Minimum değişim modu için önceki planın yerleşimi (9.8)."""
        if self.input.previous_plan is None:
            return None
        previous = np.full((self.slot_count, self.participant_count), UNSEATED, dtype=np.int32)
        for assignment in self.input.previous_plan:
            previous[assignment.slot, assignment.participant] = assignment.table
        return previous

    # --- Sorgular ---------------------------------------------------------

    def occupants(self, slot: int, table: int) -> list[int]:
        return self.seats[slot][table]

    def is_seated(self, slot: int, participant: int) -> bool:
        return bool(self.location[slot, participant] != UNSEATED)

    def is_pinned(self, slot: int, participant: int) -> bool:
        return bool(self.pinned[slot, participant])

    def can_seat(
        self, slot: int, table: int, participant: int, *, respect_frozen: bool = True
    ) -> bool:
        """Kesin kuralların hepsini kontrol eder (9.5).

        Aynı kurallar `rules.find_violations` tarafından bitmiş plan üzerinde
        bağımsız olarak da denetlenir.

        `respect_frozen=False` yalnızca sabit atamaları yerleştirirken kullanılır:
        dondurulmuş bir slotun içeriği de kurulmak zorundadır (9.8).
        """
        if respect_frozen and slot in self.input.frozen_slots:
            return False
        if self.absent[participant]:
            return False
        if self.location[slot, participant] != UNSEATED:
            return False

        occupants = self.seats[slot][table]
        if len(occupants) >= self.capacity[table]:
            return False

        company = self.company[participant]
        for other in occupants:
            if self.company[other] == company:
                return False
            if self.met[participant, other]:
                return False
        return True

    def score_if_seated(self, slot: int, table: int, participant: int) -> float:
        """Kişi bu masaya oturursa masanın skoru ne olur.

        Masa skoru en zayıf bağ olduğu için, adayı değerlendirmenin doğru ölçütü
        "masanın en zayıf bağını en az bozan kim" sorusudur.
        """
        occupants = self.seats[slot][table]
        if not occupants:
            return 0.0
        weakest_new = min(float(self.score[participant, other]) for other in occupants)
        if len(occupants) == 1:
            return weakest_new
        return min(float(self.table_scores[slot, table]), weakest_new)

    # --- Değişiklikler ----------------------------------------------------

    def seat(self, slot: int, table: int, participant: int) -> None:
        occupants = self.seats[slot][table]

        if occupants:
            weakest_new = min(float(self.score[participant, other]) for other in occupants)
            if len(occupants) == 1:
                self.table_scores[slot, table] = weakest_new
            else:
                self.table_scores[slot, table] = min(
                    float(self.table_scores[slot, table]), weakest_new
                )

        for other in occupants:
            self.met[participant, other] = True
            self.met[other, participant] = True

        occupants.append(participant)
        self.location[slot, participant] = table
        self.rounds[participant] += 1
        self.used[slot, table] = len(occupants) >= 2

    def unseat(self, slot: int, table: int, participant: int) -> None:
        occupants = self.seats[slot][table]
        occupants.remove(participant)

        # "Tekrar yok" kuralı sayesinde bir ikili en fazla bir kez karşılaşır,
        # dolayısıyla işareti doğrudan silmek güvenli.
        for other in occupants:
            self.met[participant, other] = False
            self.met[other, participant] = False

        self.location[slot, participant] = UNSEATED
        self.rounds[participant] -= 1
        self._recompute_table_score(slot, table)

    def clear_table(self, slot: int, table: int) -> None:
        for participant in list(self.seats[slot][table]):
            self.unseat(slot, table, participant)

    def _recompute_table_score(self, slot: int, table: int) -> None:
        occupants = self.seats[slot][table]
        self.used[slot, table] = len(occupants) >= 2
        if len(occupants) < 2:
            self.table_scores[slot, table] = 0.0
            return
        weakest = min(
            float(self.score[first, second])
            for position, first in enumerate(occupants)
            for second in occupants[position + 1 :]
        )
        self.table_scores[slot, table] = weakest

    def drop_single_occupant_tables(self) -> None:
        """Tek kişi kalan masaları boşaltır.

        9.5 asgari grup kuralı: ya en az iki kişi, ya boş masa.
        """
        for slot in range(self.slot_count):
            if slot in self.input.frozen_slots:
                continue
            for table in range(self.table_count):
                occupants = self.seats[slot][table]
                if len(occupants) == 1 and not self.pinned[slot, occupants[0]]:
                    self.clear_table(slot, table)

    # --- Değerlendirme ----------------------------------------------------

    def moved_placements(self) -> int:
        """Önceki plana göre yeri değişen (kişi, slot) sayısı.

        Amaç fonksiyonunda kullanılır: slot bazında saymak yerel aramaya daha
        ince bir eğim verir.
        """
        if self.previous_location is None:
            return 0
        return int(np.count_nonzero(self.location != self.previous_location))

    def moved_participants(self) -> tuple[int, ...]:
        """Herhangi bir slotta yeri değişmiş kişiler — organizatöre gösterilir (9.8).

        Gelmeyenler sayılmaz: onların masadan kalkması bir "yer değişikliği"
        değil, check-in'in doğrudan sonucu. Sayılsaydı 9.8'in ölçüsü
        (*"kaç kişi kıpırdadı"*) tam da gelmeyen kalabalığıyla şişerdi.
        """
        if self.previous_location is None:
            return ()
        changed = np.any(self.location != self.previous_location, axis=0) & ~self.absent
        return tuple(int(index) for index in np.flatnonzero(changed))

    def objective(self) -> float:
        settings = self.input.settings
        capped_rounds = np.minimum(self.rounds, settings.min_meetings_per_person)
        fairness = float(capped_rounds.sum())

        # Kalite eşiğinin altında kalan kullanılan masalar cezalandırılır (9.5).
        # `used` maskesi olmadan boş masalar da eksik sayılırdı.
        shortfall = np.maximum(settings.quality_threshold - self.table_scores, 0.0)
        penalty = settings.threshold_penalty * float(shortfall[self.used].sum())

        quality = float(self.table_scores.sum()) - penalty
        value = settings.fairness_weight * fairness + quality
        if self.previous_location is not None:
            value -= settings.move_penalty * self.moved_placements()
        return value

    def used_table_scores(self) -> list[float]:
        """Yalnızca kullanılan masaların skorları.

        Boş masalar ortalamayı aşağı çekmemeli: boş sandalye kötü eşleşmeden
        iyidir (9.5), bir başarısızlık göstergesi değil.
        """
        return [
            float(self.table_scores[slot, table])
            for slot in range(self.slot_count)
            for table in range(self.table_count)
            if len(self.seats[slot][table]) >= 2
        ]

    def unmatched_participants(self) -> tuple[int, ...]:
        """Hiçbir slotta masaya oturmamış kişiler.

        Gelmeyenler sayılmaz: onlar eşleştirilemedikleri için değil, etkinliğe
        katılmadıkları için masada değiller.
        """
        return tuple(int(index) for index in np.flatnonzero((self.rounds == 0) & ~self.absent))

    def participants_below_target(self) -> tuple[int, ...]:
        target = self.input.settings.min_meetings_per_person
        return tuple(int(index) for index in np.flatnonzero((self.rounds < target) & ~self.absent))

    def satisfied_requests(self) -> int:
        """Aynı masada oturmayı başaran talep sayısı (M9)."""
        return sum(
            1 for request in self.input.requests if self.met[request.requester, request.target]
        )

    # --- Çıktı ------------------------------------------------------------

    def assignments(self) -> tuple[Assignment, ...]:
        """Atamalar sabit bir sırada — determinizm çıktıda da görünmeli (5.3)."""
        rows = [
            Assignment(slot=slot, table=table, participant=participant)
            for slot in range(self.slot_count)
            for table in range(self.table_count)
            for participant in sorted(self.seats[slot][table])
        ]
        return tuple(rows)

    def load_assignments(self, assignments: tuple[Assignment, ...]) -> None:
        """Verilen atamaları durumun üzerine kurar.

        Minimum değişim modunda önceki planı başlangıç noktası yapmak için
        (9.8) ve yerel aramada en iyi plana geri dönmek için kullanılır.
        """
        for slot in range(self.slot_count):
            for table in range(self.table_count):
                self.clear_table(slot, table)
        for assignment in assignments:
            self.seat(assignment.slot, assignment.table, assignment.participant)

    def snapshot(self) -> np.ndarray:
        """Planın ucuz bir kopyası.

        Yerel arama yüz binlerce hamle dener ve en iyi plana geri dönebilmelidir.
        `assignments()` her seferinde binlerce nesne üretirdi; yerleşim matrisi
        birkaç kilobayt ve kopyalaması bedelsiz.
        """
        return self.location.copy()

    def restore(self, snapshot: np.ndarray) -> None:
        """`snapshot()` ile alınmış plana geri döner."""
        for slot in range(self.slot_count):
            for table in range(self.table_count):
                self.clear_table(slot, table)

        # Sıra sabit: aynı anlık görüntü her zaman aynı iç duruma açılmalı (5.3).
        for slot in range(self.slot_count):
            for participant in range(self.participant_count):
                table = int(snapshot[slot, participant])
                if table != UNSEATED:
                    self.seat(slot, table, participant)
