// Görüşme talepleri — arayüz testleri (şartname M9, Bölüm 10).
//
// Kabul kriteri: *"Talep hakkı sınırı çalışıyor... Talep edilen kişi kimin
// talep ettiğini göremiyor."*
//
// Üçüncüsü burada da kilitleniyor: sunucu "bana kim talep gönderdi" bilgisini
// hiç göndermiyor, model de öyle bir alan tanımıyor.

import 'package:b2x/core/theme/app_theme.dart';
import 'package:b2x/features/events/models.dart';
import 'package:b2x/features/events/plan_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _personJson({
  int registrationId = 11,
  String? name = 'Ayşe Yılmaz',
  String? title = 'Kurucu',
  String? company = 'Yılmaz Ticaret',
  String? sector = 'Lojistik',
  int? myRequestId,
}) {
  return {
    'registration_id': registrationId,
    'full_name': name,
    'title': title,
    'company': company,
    'sector': sector,
    'photo_url': null,
    'my_request_id': myRequestId,
  };
}

ParticipantList _list({
  List<Map<String, dynamic>> people = const [],
  int quota = 3,
  int used = 0,
  bool open = true,
}) {
  return ParticipantList.fromJson({
    'participants': people,
    'request_quota': quota,
    'requests_used': used,
    'requests_remaining': quota - used,
    'requests_open': open,
  });
}

Map<String, dynamic> _unmetJson({
  String requester = 'Ayşe Yılmaz',
  String target = 'Mehmet Demir',
  bool mutual = true,
  int? slot = 3,
}) {
  return {
    'requester_registration_id': 1,
    'target_registration_id': 2,
    'requester_name': requester,
    'target_name': target,
    'mutual': mutual,
    'fixable_slot': slot,
  };
}

PlanSummary _plan({List<Map<String, dynamic>> unmet = const []}) {
  return PlanSummary.fromJson({
    'id': 3,
    'version': 1,
    'status': 'draft',
    'job_status': 'done',
    'job_error': null,
    'created_at': '2026-08-06T14:30:00Z',
    'published_at': null,
    'seed': 42,
    'total_meetings': 40,
    'min_meetings_per_person': 4,
    'average_table_score': 0.5,
    'runtime_ms': 100,
    'assignment_count': 40,
    'participant_count': 24,
    'unmatched': <String>[],
    'satisfied_requests': 12,
    'total_requests': 40,
    'unmet_requests': unmet,
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
  group('katılımcı listesi modeli', () {
    test('sunucu yanıtı eksiksiz okunuyor', () {
      final list = _list(people: [_personJson()], quota: 3, used: 1);

      expect(list.participants, hasLength(1));
      expect(list.requestQuota, 3);
      expect(list.requestsRemaining, 2);
      expect(list.requestsOpen, isTrue);
      expect(list.exhausted, isFalse);
    });

    test('satır dört alanı taşıyor, tam profili değil', () {
      // M9: *"Listede ad, unvan, şirket, sektör görünür."* Tam profil
      // yalnızca aynı masaya düşenler için (Bölüm 7).
      final person = ParticipantRow.fromJson(_personJson());

      expect(person.fullName, 'Ayşe Yılmaz');
      expect(person.title, 'Kurucu');
      expect(person.company, 'Yılmaz Ticaret');
      expect(person.sector, 'Lojistik');
    });

    test('gelen talep diye bir alan yok', () {
      // Bölüm 10: *"Talep edilen kişi kimin talep ettiğini göremiyor."*
      // Sunucu göndermiyor; model de tanımıyor.
      final person = ParticipantRow.fromJson(_personJson(myRequestId: 7));

      expect(person.myRequestId, 7);
      expect(person.requested, isTrue);
      // Karşı tarafın bana talep gönderip göndermediğini okumanın yolu yok.
      expect(_personJson().containsKey('requested_me'), isFalse);
      expect(_personJson().containsKey('incoming_request'), isFalse);
    });

    test('hak dolduğunda anlaşılıyor', () {
      final full = _list(quota: 3, used: 3);

      expect(full.exhausted, isTrue);
      expect(full.requestsRemaining, 0);
    });
  });

  group('kalan hak cümlesi', () {
    test('hak varken sayıyla yazılıyor', () {
      expect(_list(quota: 3, used: 1).quotaSentence, '3 talep hakkından 2 tanesi kaldı.');
    });

    test('hak dolduğunda ne yapılacağı söyleniyor', () {
      // Çıkmaz sokak bırakmıyor: geri çekmek hakkı iade ediyor.
      expect(
        _list(quota: 3, used: 3).quotaSentence,
        contains('Birini geri çekersen'),
      );
    });

    test('hak sıfırsa talep hiç gönderilemiyor', () {
      expect(_list(quota: 0).quotaSentence, contains('gönderilemiyor'));
    });
  });

  group('karşılanmayan talepler', () {
    test('karşılıklı ile tek taraflı ayrılıyor', () {
      final plan = _plan(
        unmet: [
          _unmetJson(mutual: true),
          _unmetJson(requester: 'Zeynep Kaya', target: 'Emre Koç', mutual: false),
        ],
      );

      expect(plan.unmetMutual, hasLength(1));
      expect(plan.unmetOneWay, hasLength(1));
    });

    test('karşılıklıda çift yönlü ok, tek taraflıda tek yönlü', () {
      expect(
        UnmetRequest.fromJson(_unmetJson(mutual: true)).pair,
        'Ayşe Yılmaz ↔ Mehmet Demir',
      );
      expect(
        UnmetRequest.fromJson(_unmetJson(mutual: false)).pair,
        'Ayşe Yılmaz → Mehmet Demir',
      );
    });

    testWidgets('karşılıklı olanlar vurgulu ve tura gidilebiliyor', (tester) async {
      int? opened;
      await _pump(
        tester,
        PlanSummaryPanel(
          plan: _plan(unmet: [_unmetJson(mutual: true, slot: 3)]),
          onOpenSlot: (slot) => opened = slot,
        ),
      );

      expect(find.text('Karşılanmayan 1 karşılıklı talep'), findsOneWidget);
      expect(find.textContaining('İkisi de birbirini istemiş'), findsOneWidget);
      expect(find.text('Ayşe Yılmaz ↔ Mehmet Demir'), findsOneWidget);

      await tester.tap(find.text('3. Tur'));
      expect(opened, 3);
    });

    testWidgets('tek taraflılar kapalı listede ve uyarısıyla', (tester) async {
      await _pump(
        tester,
        PlanSummaryPanel(
          plan: _plan(unmet: [_unmetJson(mutual: false)]),
          onOpenSlot: (_) {},
        ),
      );

      expect(find.text('Karşılanmayan 1 tek taraflı talep'), findsOneWidget);
      expect(find.textContaining('Zorlanması önerilmez'), findsOneWidget);
      // M9: karşılıklı olmayanlar için "düzeltilmesi gereken kusur" denmiyor.
      expect(find.textContaining('İkisi de birbirini istemiş'), findsNothing);
    });

    testWidgets('düzeltilecek tur yoksa söyleniyor', (tester) async {
      // İkisi hiçbir turda birlikte oturmuyor: takasla düzeltilecek yer yok.
      await _pump(
        tester,
        PlanSummaryPanel(
          plan: _plan(unmet: [_unmetJson(mutual: true, slot: null)]),
          onOpenSlot: (_) {},
        ),
      );

      expect(find.text('Düzeltilecek tur yok'), findsOneWidget);
    });

    testWidgets('karşılanmayan yoksa bölüm hiç çıkmıyor', (tester) async {
      await _pump(tester, PlanSummaryPanel(plan: _plan()));

      expect(find.textContaining('Karşılanmayan'), findsNothing);
    });

    testWidgets('karşılanan talep sayacı yerinde duruyor', (tester) async {
      await _pump(tester, PlanSummaryPanel(plan: _plan()));

      expect(find.text('Karşılanan talep'), findsOneWidget);
      expect(find.text('12/40'), findsOneWidget);
    });
  });
}
