"""Kesin kurallar — asla ihlal edilemez (şartname 9.5).

Bu modül kuralları **bitmiş bir plan üzerinde** denetler. Motorun içindeki
`PlanState` aynı kuralları artımlı olarak uygular (bir kişiyi oturtmadan önce
kontrol eder); buradaki denetleyici bağımsız bir ikinci gözdür.

İkisinin ayrı yazılmış olması bilinçli: artımlı uygulamada yapılan bir hata,
aynı koddan türeyen bir denetleyiciyle yakalanamazdı. Testler her üretilen planı
buradan geçirir (9.10'un ilk altı maddesi).
"""

from collections import defaultdict
from dataclasses import dataclass

from engine.types import Assignment, EngineInput

CAPACITY = "kapasite"
MINIMUM_GROUP = "asgari grup"
COMPANY_SEPARATION = "ayni sirket ayrimi"
NO_REPEAT = "tekrar yok"
ONE_SEAT = "tek yer"
FIXED_ASSIGNMENT = "sabit atama"
FROZEN_SLOT = "dondurulmus slot"


@dataclass(frozen=True, slots=True)
class RuleViolation:
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail}"


def find_violations(
    engine_input: EngineInput, assignments: tuple[Assignment, ...]
) -> list[RuleViolation]:
    """Planın çiğnediği kesin kuralları listeler. Boş liste = geçerli plan."""
    violations: list[RuleViolation] = []

    occupants: dict[tuple[int, int], list[int]] = defaultdict(list)
    seat_of_person: dict[tuple[int, int], int] = {}

    for assignment in assignments:
        key = (assignment.slot, assignment.participant)
        if key in seat_of_person:
            violations.append(
                RuleViolation(
                    ONE_SEAT,
                    f"katilimci {assignment.participant}, slot {assignment.slot} icinde "
                    f"hem {seat_of_person[key]} hem {assignment.table} numarali masada",
                )
            )
            continue
        seat_of_person[key] = assignment.table
        occupants[(assignment.slot, assignment.table)].append(assignment.participant)

    violations.extend(_check_capacity(engine_input, occupants))
    violations.extend(_check_minimum_group(occupants))
    violations.extend(_check_company_separation(engine_input, occupants))
    violations.extend(_check_no_repeat(occupants))
    violations.extend(_check_fixed_assignments(engine_input, seat_of_person))
    violations.extend(_check_frozen_slots(engine_input, assignments))

    return violations


def _check_capacity(
    engine_input: EngineInput, occupants: dict[tuple[int, int], list[int]]
) -> list[RuleViolation]:
    """Oturmalı masada sandalye sayısı, ayaklı masada üst sınır aşılamaz."""
    violations = []
    for (slot, table), people in sorted(occupants.items()):
        capacity = engine_input.tables[table].capacity
        if len(people) > capacity:
            violations.append(
                RuleViolation(
                    CAPACITY,
                    f"slot {slot}, masa {table}: {len(people)} kisi / {capacity} kapasite",
                )
            )
    return violations


def _check_minimum_group(
    occupants: dict[tuple[int, int], list[int]],
) -> list[RuleViolation]:
    """Kullanilan masada en az iki kisi olur — ya en az iki kisi, ya bos masa.

    Tek kisilik masa kimseye bir sey vermez: o kisi yarim saat tek basina oturur
    (9.5, Bolum 13).
    """
    violations = []
    for (slot, table), people in sorted(occupants.items()):
        if len(people) == 1:
            violations.append(
                RuleViolation(
                    MINIMUM_GROUP,
                    f"slot {slot}, masa {table}: katilimci {people[0]} tek basina",
                )
            )
    return violations


def _check_company_separation(
    engine_input: EngineInput, occupants: dict[tuple[int, int], list[int]]
) -> list[RuleViolation]:
    """Ayni sirketten iki kisi ayni masaya asla oturamaz."""
    violations = []
    for (slot, table), people in sorted(occupants.items()):
        seen: dict[int, int] = {}
        for person in sorted(people):
            company = engine_input.participants[person].company
            if company in seen:
                violations.append(
                    RuleViolation(
                        COMPANY_SEPARATION,
                        f"slot {slot}, masa {table}: katilimci {seen[company]} ve {person} "
                        f"ayni sirkette ({company})",
                    )
                )
            else:
                seen[company] = person
    return violations


def _check_no_repeat(
    occupants: dict[tuple[int, int], list[int]],
) -> list[RuleViolation]:
    """Iki kisi etkinlik boyunca en fazla bir kez ayni masada oturur."""
    violations = []
    first_meeting: dict[tuple[int, int], int] = {}
    for (slot, _table), people in sorted(occupants.items()):
        ordered = sorted(people)
        for position, first in enumerate(ordered):
            for second in ordered[position + 1 :]:
                pair = (first, second)
                if pair in first_meeting:
                    violations.append(
                        RuleViolation(
                            NO_REPEAT,
                            f"katilimci {first} ve {second} hem slot {first_meeting[pair]} "
                            f"hem slot {slot} icinde ayni masada",
                        )
                    )
                else:
                    first_meeting[pair] = slot
    return violations


def _check_fixed_assignments(
    engine_input: EngineInput, seat_of_person: dict[tuple[int, int], int]
) -> list[RuleViolation]:
    """Capa kisiler ve kilitlenmis atamalar degistirilemez."""
    violations = []
    for fixed in engine_input.fixed_assignments:
        actual = seat_of_person.get((fixed.slot, fixed.participant))
        if actual != fixed.table:
            violations.append(
                RuleViolation(
                    FIXED_ASSIGNMENT,
                    f"katilimci {fixed.participant}, slot {fixed.slot} icinde masa "
                    f"{fixed.table} olmaliydi, {actual} bulundu",
                )
            )
    return violations


def _check_frozen_slots(
    engine_input: EngineInput, assignments: tuple[Assignment, ...]
) -> list[RuleViolation]:
    """Baslamis veya bitmis slotlara dokunulmaz (9.8).

    Dondurulmus slotlarin atamalari onceki plandakiyle birebir ayni kalmali.
    """
    if not engine_input.frozen_slots or engine_input.previous_plan is None:
        return []

    def frozen_rows(rows: tuple[Assignment, ...]) -> set[tuple[int, int, int]]:
        return {
            (row.slot, row.table, row.participant)
            for row in rows
            if row.slot in engine_input.frozen_slots
        }

    before = frozen_rows(engine_input.previous_plan)
    after = frozen_rows(assignments)
    violations = []
    for slot, table, participant in sorted(before - after):
        violations.append(
            RuleViolation(
                FROZEN_SLOT,
                f"donmus atama kayboldu: slot {slot}, masa {table}, katilimci {participant}",
            )
        )
    for slot, table, participant in sorted(after - before):
        violations.append(
            RuleViolation(
                FROZEN_SLOT,
                f"donmus slota atama eklendi: slot {slot}, masa {table}, katilimci {participant}",
            )
        )
    return violations
