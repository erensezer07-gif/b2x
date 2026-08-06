// Program hesabı — sunucudaki `backend/tests/test_schedule.py` ile **aynı
// senaryolar**.
//
// Aynı formül iki dilde yazıldığı için ayrışma riski var. Bu dosya o riski
// kapatıyor: iki taraf da aynı girdiye aynı cevabı vermeli.

import 'package:b2x/features/events/schedule.dart';
import 'package:flutter_test/flutter_test.dart';

DateTime at(int hour, [int minute = 0]) =>
    DateTime(2026, 9, 15, hour, minute);

void main() {
  group('program hesabı', () {
    test('şartnamenin örneği: 10:00, 30 dakika slot, 10 dakika mola', () {
      final schedule = buildSchedule(
        startsAt: at(10),
        slotDurationMinutes: 30,
        breakDurationMinutes: 10,
        slotCount: 3,
      );

      expect(
        schedule.slots.map((s) => (s.startsAt, s.endsAt)).toList(),
        [
          (at(10, 0), at(10, 30)),
          (at(10, 40), at(11, 10)),
          (at(11, 20), at(11, 50)),
        ],
      );
    });

    test('slot numaraları 1\'den başlar', () {
      final schedule = buildSchedule(
        startsAt: at(9),
        slotDurationMinutes: 20,
        breakDurationMinutes: 5,
        slotCount: 4,
      );
      expect(schedule.slots.map((s) => s.number), [1, 2, 3, 4]);
    });

    test('son slottan sonra mola yok', () {
      final schedule = buildSchedule(
        startsAt: at(10),
        slotDurationMinutes: 30,
        breakDurationMinutes: 10,
        slotCount: 2,
      );

      expect(schedule.endsAt, at(11, 10));
      // 30 + 10 + 30 = 70; sondaki molayla 80 olurdu.
      expect(schedule.totalMinutes, 70);
    });

    test('tek slotta hiç mola yok', () {
      final schedule = buildSchedule(
        startsAt: at(14),
        slotDurationMinutes: 45,
        breakDurationMinutes: 15,
        slotCount: 1,
      );

      expect(schedule.startsAt, at(14));
      expect(schedule.endsAt, at(14, 45));
      expect(schedule.totalMinutes, 45);
    });

    test('sıfır molada slotlar arka arkaya', () {
      final schedule = buildSchedule(
        startsAt: at(10),
        slotDurationMinutes: 30,
        breakDurationMinutes: 0,
        slotCount: 3,
      );

      expect(schedule.slots.map((s) => s.startsAt), [at(10), at(10, 30), at(11)]);
      expect(schedule.endsAt, at(11, 30));
    });

    test('program gece yarısını aşabilir', () {
      final schedule = buildSchedule(
        startsAt: at(23),
        slotDurationMinutes: 30,
        breakDurationMinutes: 10,
        slotCount: 4,
      );

      // 23:00, 23:40, 00:20, 01:00 — sonuncusu 01:30'da biter.
      expect(schedule.slots.map((s) => s.startsAt.hour), [23, 23, 0, 1]);
      expect(schedule.endsAt, DateTime(2026, 9, 16, 1, 30));
      expect(schedule.totalMinutes, 150);
    });

    test('şartname ölçeği: 8 tur bir iş gününe sığar', () {
      final schedule = buildSchedule(
        startsAt: at(10),
        slotDurationMinutes: 30,
        breakDurationMinutes: 10,
        slotCount: 8,
      );

      expect(schedule.slots.length, 8);
      // 8×30 + 7×10 = 310 dakika
      expect(schedule.totalMinutes, 310);
      expect(schedule.endsAt, at(15, 10));
    });

    test('geçersiz girdi reddedilir', () {
      expect(
        () => buildSchedule(
          startsAt: at(10),
          slotDurationMinutes: 30,
          breakDurationMinutes: 10,
          slotCount: 0,
        ),
        throwsArgumentError,
      );
      expect(
        () => buildSchedule(
          startsAt: at(10),
          slotDurationMinutes: 0,
          breakDurationMinutes: 10,
          slotCount: 4,
        ),
        throwsArgumentError,
      );
      expect(
        () => buildSchedule(
          startsAt: at(10),
          slotDurationMinutes: 30,
          breakDurationMinutes: -1,
          slotCount: 4,
        ),
        throwsArgumentError,
      );
    });
  });

  group('biçimlendirme', () {
    test('süre okunur yazılır', () {
      expect(formatDuration(45), '45 dk');
      expect(formatDuration(60), '1 sa');
      expect(formatDuration(310), '5 sa 10 dk');
    });

    test('saat iki haneli yazılır', () {
      expect(formatTime(at(9, 5)), '09:05');
      expect(formatTime(at(14, 30)), '14:30');
    });
  });
}
