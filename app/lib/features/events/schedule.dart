/// Program hesaplama — sunucudaki `app/services/schedule.py`'nin karşılığı.
///
/// Şartname M4: *"Girildikçe hesaplanan program anlık gösterilir, bitiş saati
/// görünür. Organizatör 'çok uzun sürüyor' diye anında fark eder."*
///
/// Aynı formül neden iki yerde: her tuş vuruşunda sunucuya gitmek anlık
/// önizleme için anlamsız olurdu. Sunucu yine de tek doğruluk kaynağı —
/// kaydedilen etkinliğin programı oradan geliyor, burası yalnızca önizleme.
///
/// İki tarafın ayrışmaması için **aynı senaryolar iki tarafta da test ediliyor**
/// (`backend/tests/test_schedule.py` ve `test/schedule_test.dart`).
library;

class SlotTiming {
  const SlotTiming({
    required this.number,
    required this.startsAt,
    required this.endsAt,
  });

  factory SlotTiming.fromJson(Map<String, dynamic> json) => SlotTiming(
        number: json['number'] as int,
        startsAt: DateTime.parse(json['starts_at'] as String).toLocal(),
        endsAt: DateTime.parse(json['ends_at'] as String).toLocal(),
      );

  final int number;
  final DateTime startsAt;
  final DateTime endsAt;
}

class Schedule {
  const Schedule(this.slots);

  final List<SlotTiming> slots;

  DateTime get startsAt => slots.first.startsAt;

  /// Son slotun bitişi.
  ///
  /// Son slottan **sonra mola yoktur**: etkinlik son görüşme biter bitmez
  /// biter. Molayı eklemek toplam süreyi bir mola kadar uzun gösterirdi.
  DateTime get endsAt => slots.last.endsAt;

  int get totalMinutes => endsAt.difference(startsAt).inMinutes;
}

/// Slot saatlerini hesaplar.
///
/// Slot numaraları 1'den başlar: katılımcıya "Slot 1" gösteriliyor (M8).
Schedule buildSchedule({
  required DateTime startsAt,
  required int slotDurationMinutes,
  required int breakDurationMinutes,
  required int slotCount,
}) {
  if (slotCount < 1) {
    throw ArgumentError.value(slotCount, 'slotCount', 'En az 1 olmalı');
  }
  if (slotDurationMinutes < 1) {
    throw ArgumentError.value(
      slotDurationMinutes,
      'slotDurationMinutes',
      'En az 1 dakika olmalı',
    );
  }
  if (breakDurationMinutes < 0) {
    throw ArgumentError.value(
      breakDurationMinutes,
      'breakDurationMinutes',
      'Negatif olamaz',
    );
  }

  final step = Duration(minutes: slotDurationMinutes + breakDurationMinutes);
  final duration = Duration(minutes: slotDurationMinutes);

  return Schedule([
    for (var index = 0; index < slotCount; index++)
      SlotTiming(
        number: index + 1,
        startsAt: startsAt.add(step * index),
        endsAt: startsAt.add(step * index).add(duration),
      ),
  ]);
}

/// Dakikayı okunur süreye çevirir: `310` → `5 sa 10 dk`.
String formatDuration(int minutes) {
  final hours = minutes ~/ 60;
  final remaining = minutes % 60;

  if (hours == 0) return '$remaining dk';
  if (remaining == 0) return '$hours sa';
  return '$hours sa $remaining dk';
}

/// Saati `10:00` biçiminde yazar.
String formatTime(DateTime moment) {
  final hour = moment.hour.toString().padLeft(2, '0');
  final minute = moment.minute.toString().padLeft(2, '0');
  return '$hour:$minute';
}
