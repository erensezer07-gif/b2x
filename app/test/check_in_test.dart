// Check-in — arayüz testleri (şartname M10, Bölüm 10).
//
// Kabul kriteri: *"QR okunduğunda katılımcı geldi olarak işaretleniyor.
// Gelmeyenler çıkarılıp plan güncellendiğinde, yeri değişenlerin listesi
// organizatöre gösteriliyor."*

import 'package:b2x/core/theme/app_theme.dart';
import 'package:b2x/features/events/check_in_screen.dart';
import 'package:b2x/features/events/models.dart';
import 'package:b2x/features/events/plan_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _attendeeJson({
  int registrationId = 11,
  String? name = 'Ayşe Yılmaz',
  String? company = 'Yılmaz Ticaret',
  bool present = false,
  String? checkedInAt,
}) {
  return {
    'registration_id': registrationId,
    'full_name': name,
    'title': 'Kurucu',
    'company': company,
    'photo_url': null,
    'present': present,
    'checked_in_at': checkedInAt,
  };
}

Map<String, dynamic> _changeJson({
  String name = 'Ayşe Yılmaz',
  int slot = 2,
  int? before = 3,
  int? after = 5,
}) {
  return {
    'registration_id': 11,
    'name': name,
    'slot_number': slot,
    'before': before,
    'after': after,
  };
}

PlanChanges _changes({
  List<Map<String, dynamic>> rows = const [],
  int? previous = 1,
}) {
  return PlanChanges.fromJson({
    'previous_plan_id': previous,
    'changes': rows,
    'moved_people': {for (final row in rows) row['registration_id']}.length,
  });
}

Future<void> _pump(WidgetTester tester, Widget child) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
}

void main() {
  group('giriş kodu modeli', () {
    test('sunucu yanıtı okunuyor', () {
      final code = MyQrCode.fromJson({
        'registration_id': 11,
        'qr_code': 'abc123',
        'checked_in_at': null,
      });

      expect(code.qrCode, 'abc123');
      expect(code.checkedIn, isFalse);
    });

    test('girişi yapılmış katılımcı zamanı taşıyor', () {
      final code = MyQrCode.fromJson({
        'registration_id': 11,
        'qr_code': 'abc123',
        'checked_in_at': '2026-12-01T09:05:00Z',
      });

      expect(code.checkedIn, isTrue);
      expect(code.checkedInAt, isNotNull);
    });
  });

  group('check-in listesi modeli', () {
    test('sayaç okunuyor', () {
      final board = AttendanceBoard.fromJson({
        'attendees': [_attendeeJson(), _attendeeJson(registrationId: 12, present: true)],
        'accepted_count': 10,
        'present_count': 4,
        'expected_count': 6,
      });

      expect(board.attendees, hasLength(2));
      expect(board.presentCount, 4);
      expect(board.expectedCount, 6);
      expect(board.anyoneArrived, isTrue);
    });

    test('kimse gelmediyse yenileme anlamsız', () {
      final board = AttendanceBoard.fromJson({
        'attendees': <Map<String, dynamic>>[],
        'accepted_count': 10,
        'present_count': 0,
        'expected_count': 10,
      });

      expect(board.anyoneArrived, isFalse);
    });

    test('okuma sonucu ikinci kez okunduğunu söylüyor', () {
      final result = ScanResult.fromJson({
        'attendee': _attendeeJson(present: true, checkedInAt: '2026-12-01T09:05:00Z'),
        'accepted_count': 10,
        'present_count': 4,
        'expected_count': 6,
        'already_present': true,
      });

      expect(result.alreadyPresent, isTrue);
      expect(result.attendee.present, isTrue);
      expect(result.board.presentCount, 4);
    });
  });

  group('yeri değişenler', () {
    test('taşınma Türkçe yazılıyor', () {
      expect(
        SeatChange.fromJson(_changeJson(before: 3, after: 5)).description,
        'Masa 3 → Masa 5',
      );
    });

    test('yeni yerleşen ve masadan kalkan ayrı yazılıyor', () {
      expect(
        SeatChange.fromJson(_changeJson(before: null, after: 5)).description,
        contains('yeni yerleşti'),
      );
      expect(
        SeatChange.fromJson(_changeJson(before: 3, after: null)).description,
        contains('masadan kalktı'),
      );
    });

    test('cümleler masa numarasına ek getirmiyor', () {
      // Aşama 8'de tarayıcıda yakalanan tuzak: Türkçede ek sayının okunuşuna
      // göre değişiyor.
      final suffixed = RegExp(r"\d['’]");
      for (var number = 1; number <= 12; number++) {
        for (final row in [
          _changeJson(before: number, after: number + 1),
          _changeJson(before: null, after: number),
          _changeJson(before: number, after: null),
        ]) {
          expect(
            SeatChange.fromJson(row).description,
            isNot(matches(suffixed)),
            reason: 'masa $number',
          );
        }
      }
    });

    testWidgets('liste kim, hangi tur ve nereye taşındığını gösteriyor',
        (tester) async {
      await _pump(
        tester,
        SeatChangesPanel(
          changes: _changes(rows: [_changeJson(slot: 2, before: 3, after: 5)]),
        ),
      );

      expect(find.text('1 kişinin yeri değişti'), findsOneWidget);
      expect(find.text('Ayşe Yılmaz'), findsOneWidget);
      expect(find.text('2. Tur'), findsOneWidget);
      expect(find.text('Masa 3 → Masa 5'), findsOneWidget);
    });

    testWidgets('kimse kıpırdamadıysa öyle söyleniyor', (tester) async {
      // 9.8'in sözü: *"gerekmedikçe kimseyi kıpırdatma."*
      await _pump(tester, SeatChangesPanel(changes: _changes()));

      expect(find.text('Kimsenin yeri değişmedi.'), findsOneWidget);
    });

    test('ilk versiyonun öncesi yok', () {
      final changes = _changes(previous: null);

      expect(changes.previousPlanId, isNull);
      expect(changes.isEmpty, isTrue);
    });
  });

  group('katılımcı kartı', () {
    testWidgets('gelmeyene işaretleme düğmesi çıkıyor', (tester) async {
      var toggled = false;
      await _pump(
        tester,
        AttendeeCard(
          attendee: Attendee.fromJson(_attendeeJson()),
          busy: false,
          onToggle: () => toggled = true,
        ),
      );

      expect(find.text('Geldi işaretle'), findsOneWidget);
      await tester.tap(find.text('Geldi işaretle'));
      expect(toggled, isTrue);
    });

    testWidgets('gelene giriş saati ve geri alma çıkıyor', (tester) async {
      // Geri alınabiliyor: yanlış kişi işaretlenmiş olabilir.
      await _pump(
        tester,
        AttendeeCard(
          attendee: Attendee.fromJson(
            _attendeeJson(present: true, checkedInAt: '2026-12-01T09:05:00Z'),
          ),
          busy: false,
          onToggle: () {},
        ),
      );

      expect(find.text('Geldi'), findsOneWidget);
      expect(find.textContaining('Giriş'), findsOneWidget);
    });

    testWidgets('işlem sürerken düğme kapalı', (tester) async {
      await _pump(
        tester,
        AttendeeCard(
          attendee: Attendee.fromJson(_attendeeJson()),
          busy: true,
          onToggle: () {},
        ),
      );

      final button = tester.widget<OutlinedButton>(find.byType(OutlinedButton));
      expect(button.onPressed, isNull);
    });

    testWidgets('adı girilmemiş kişi de gösteriliyor', (tester) async {
      await _pump(
        tester,
        AttendeeCard(
          attendee: Attendee.fromJson(_attendeeJson(name: null)),
          busy: false,
          onToggle: () {},
        ),
      );

      expect(find.text('Adı girilmemiş'), findsOneWidget);
    });
  });
}
