// Plan önizleme ve elle düzeltme — arayüz testleri (şartname M7, Bölüm 10).
//
// Kabul kriteri: *"Organizatör her slotu görebiliyor. İki kişi takas
// edildiğinde kural ihlali anında uyarı olarak çıkıyor. En az görüşme alan
// kişinin sayısı özet panelde görünüyor."*
//
// İki şey ayrıca kilitleniyor:
//
// * **Uyarı çevirisi.** Sunucu İngilizce anahtar gönderiyor; çeviri koparsa
//   organizatör "Beklenmeyen bir durum var" yazan bir liste görür.
// * **Dokun-dokun takas.** Hangi dokunuşun ne yaptığı ekranın kendi mantığı;
//   sunucu bunu bilmiyor.

import 'package:b2x/core/theme/app_theme.dart';
import 'package:b2x/features/events/models.dart';
import 'package:b2x/features/events/plan_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _personJson({
  required int assignmentId,
  String? name = 'Ayşe Yılmaz',
  String? company = 'Örnek A.Ş.',
  bool pinned = false,
}) {
  return {
    'assignment_id': assignmentId,
    'registration_id': assignmentId * 10,
    'full_name': name,
    'company': company,
    'is_pinned': pinned,
  };
}

Map<String, dynamic> _tableJson({
  required int id,
  required int number,
  String? label,
  int capacity = 6,
  String quality = 'good',
  num score = 0.8,
  List<Map<String, dynamic>> occupants = const [],
}) {
  return {
    'table_id': id,
    'number': number,
    'label': label,
    'capacity': capacity,
    'occupants': occupants,
    'quality': quality,
    'score': score,
  };
}

SeatedPerson _person({
  int assignmentId = 1,
  String? name = 'Ayşe Yılmaz',
  bool pinned = false,
}) {
  return SeatedPerson.fromJson(
    _personJson(assignmentId: assignmentId, name: name, pinned: pinned),
  );
}

SeatedTable _table({
  int id = 1,
  int number = 1,
  int capacity = 6,
  String quality = 'good',
  List<SeatedPerson> occupants = const [],
}) {
  return SeatedTable.fromJson(
    _tableJson(
      id: id,
      number: number,
      capacity: capacity,
      quality: quality,
      occupants: [
        for (final person in occupants)
          _personJson(
            assignmentId: person.assignmentId,
            name: person.fullName,
            pinned: person.isPinned,
          ),
      ],
    ),
  );
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
  group('slot görünümü modeli', () {
    test('sunucu yanıtı eksiksiz okunuyor', () {
      final slot = SlotView.fromJson({
        'slot_number': 2,
        'tables': [
          _tableJson(
            id: 7,
            number: 1,
            label: 'Pencere kenarı',
            capacity: 4,
            occupants: [
              _personJson(assignmentId: 11, name: 'Ayşe Yılmaz'),
              _personJson(assignmentId: 12, name: 'Mehmet Demir', pinned: true),
            ],
          ),
          _tableJson(id: 8, number: 2, quality: 'empty', score: 0),
        ],
      });

      expect(slot.slotNumber, 2);
      expect(slot.seatedCount, 2);

      final first = slot.tables.first;
      expect(first.title, 'Pencere kenarı');
      expect(first.capacity, 4);
      expect(first.isFull, isFalse);
      expect(first.occupants[1].isPinned, isTrue);

      // Boş masa da geliyor: organizatör boş sandalyeye taşıyabilmeli.
      expect(slot.tables[1].isEmpty, isTrue);
      expect(slot.tables[1].title, 'Masa 2');
    });

    test('dolu masa kendini biliyor', () {
      final full = _table(
        capacity: 2,
        occupants: [_person(assignmentId: 1), _person(assignmentId: 2)],
      );
      expect(full.isFull, isTrue);
    });

    test('adı girilmemiş kişi de gösterilebiliyor', () {
      // Profil tamamlanmadan kontenjan elle onaylanmış olabilir.
      final person = SeatedPerson.fromJson(
        _personJson(assignmentId: 1, name: null, company: null),
      );
      expect(person.displayName, 'Adı girilmemiş');
    });

    test('tanınmayan kalite arayüzü çökertmiyor', () {
      expect(TableQuality.fromKey('gelecekte_eklenen'), TableQuality.empty);
    });

    test('her kalite seviyesinin Türkçe bir etiketi var', () {
      for (final quality in TableQuality.values) {
        expect(quality.label, isNotEmpty);
      }
    });

    test('tam sayı gelen skor okunuyor', () {
      // JSON'da 0.0 yerine 0 gelebilir; `as double` bunu çökertirdi.
      expect(SeatedTable.fromJson(_tableJson(id: 1, number: 1, score: 0)).score, 0.0);
    });
  });

  group('takas uyarıları', () {
    SwapWarning warning(
      String key, {
      int? table = 3,
      List<String> people = const ['Ayşe Yılmaz', 'Mehmet Demir'],
      int? slot,
    }) {
      return SwapWarning.fromJson({
        'key': key,
        'table_number': table,
        'people': people,
        'slot_number': slot,
      });
    }

    test('her uyarı Türkçe bir cümleye çevriliyor', () {
      final messages = [
        warning('same_company').message,
        warning('over_capacity').message,
        warning('lonely_table', people: ['Ayşe Yılmaz']).message,
        warning('repeat_pair', slot: 4).message,
        warning('quality_dropped').message,
      ];

      expect(messages[0], contains('aynı şirketten'));
      expect(messages[1], contains('kapasitenin üzerinde'));
      expect(messages[2], contains('tek kişi kaldı'));
      expect(messages[3], contains('4. turda'));
      expect(messages[4], contains('eşleşme kalitesi'));

      // Hiçbiri İngilizce anahtar sızdırmamalı (Bölüm 0).
      for (final message in messages) {
        expect(message, isNot(contains('_')));
      }
    });

    test('cümleler masa numarasına ek getirmiyor', () {
      // Türkçede ek sayının okunuşuna göre değişiyor: "1'in" ama "2'nin",
      // "4'te", "6'da". Tarayıcıda "Masa 2'ın" ve "Masa 4'da" çıktı; cümleler
      // ek gerektirmeyecek şekilde yeniden kuruldu. Bu test o kararı tutuyor.
      final suffixed = RegExp(r"\d['’]");
      for (final key in [
        'same_company',
        'over_capacity',
        'lonely_table',
        'repeat_pair',
        'quality_dropped',
        'gelecekte_eklenen',
      ]) {
        for (var number = 1; number <= 12; number++) {
          final message = warning(key, table: number, slot: number).message;
          expect(message, isNot(matches(suffixed)), reason: '$key / masa $number');
        }
      }
    });

    test('uyarı masayı ve kişileri cümlenin içine alıyor', () {
      final message = warning('same_company', table: 5).message;
      expect(message, contains('Masa 5'));
      expect(message, contains('Ayşe Yılmaz'));
      expect(message, contains('Mehmet Demir'));
    });

    test('tanınmayan anahtar arayüzü çökertmiyor', () {
      expect(warning('gelecekte_eklenen').message, isNotEmpty);
    });

    test('takas sonucu görünüm ve uyarıları birlikte taşıyor', () {
      // Uçtan ikisi birlikte dönüyor ki istemci ikinci bir istek atmasın.
      final result = SwapResult.fromJson({
        'slot': {
          'slot_number': 1,
          'tables': [_tableJson(id: 1, number: 1)],
        },
        'warnings': [
          {
            'key': 'lonely_table',
            'table_number': 1,
            'people': ['Ayşe Yılmaz'],
            'slot_number': null,
          },
        ],
      });

      expect(result.slot.slotNumber, 1);
      expect(result.warnings.single.message, contains('tek kişi kaldı'));
    });
  });

  group('tur seçici', () {
    testWidgets('her tur için bir seçenek çıkıyor', (tester) async {
      await _pump(
        tester,
        SlotSelector(slotCount: 5, selected: 1, onSelect: (_) {}),
      );

      for (var number = 1; number <= 5; number++) {
        expect(find.text('$number. Tur'), findsOneWidget);
      }
    });

    testWidgets('seçilen tur bildiriliyor', (tester) async {
      int? chosen;
      await _pump(
        tester,
        SlotSelector(slotCount: 3, selected: 1, onSelect: (n) => chosen = n),
      );

      await tester.tap(find.text('3. Tur'));
      expect(chosen, 3);
    });

    testWidgets('takas sürerken tur değiştirilemiyor', (tester) async {
      await _pump(
        tester,
        const SlotSelector(slotCount: 3, selected: 1, onSelect: null),
      );

      final chip = tester.widget<ChoiceChip>(find.byType(ChoiceChip).first);
      expect(chip.onSelected, isNull);
    });
  });

  group('masa kartı', () {
    testWidgets('ad, şirket, doluluk ve kalite gösteriliyor', (tester) async {
      await _pump(
        tester,
        TableCard(
          table: _table(
            number: 4,
            capacity: 6,
            quality: 'fair',
            occupants: [_person(assignmentId: 1, name: 'Ayşe Yılmaz')],
          ),
          selectedAssignmentId: null,
          onTapTable: null,
          onTapPerson: (_) {},
          onTogglePin: (_) {},
        ),
      );

      expect(find.text('Masa 4'), findsOneWidget);
      expect(find.text('Ayşe Yılmaz'), findsOneWidget);
      expect(find.text('Örnek A.Ş.'), findsOneWidget);
      expect(find.text('1/6'), findsOneWidget);
      // *"Sayı değil, üç seviye."* Skor ekranda yok.
      expect(find.text('Orta'), findsOneWidget);
      expect(find.textContaining('0.8'), findsNothing);
    });

    testWidgets('kişiye dokunma bildiriliyor', (tester) async {
      SeatedPerson? tapped;
      await _pump(
        tester,
        TableCard(
          table: _table(occupants: [_person(assignmentId: 9)]),
          selectedAssignmentId: null,
          onTapTable: null,
          onTapPerson: (person) => tapped = person,
          onTogglePin: (_) {},
        ),
      );

      await tester.tap(find.text('Ayşe Yılmaz'));
      expect(tapped?.assignmentId, 9);
    });

    testWidgets('seçili kişi işaretli görünüyor', (tester) async {
      await _pump(
        tester,
        TableCard(
          table: _table(occupants: [_person(assignmentId: 9)]),
          selectedAssignmentId: 9,
          onTapTable: null,
          onTapPerson: (_) {},
          onTogglePin: (_) {},
        ),
      );

      expect(find.byIcon(Icons.radio_button_checked), findsOneWidget);
    });

    testWidgets('sabitleme düğmesi durumu gösteriyor ve bildiriliyor',
        (tester) async {
      SeatedPerson? toggled;
      await _pump(
        tester,
        TableCard(
          table: _table(
            occupants: [_person(assignmentId: 9, pinned: true)],
          ),
          selectedAssignmentId: null,
          onTapTable: null,
          onTapPerson: (_) {},
          onTogglePin: (person) => toggled = person,
        ),
      );

      expect(find.byIcon(Icons.push_pin), findsOneWidget);
      await tester.tap(find.byIcon(Icons.push_pin));
      expect(toggled?.assignmentId, 9);
    });

    testWidgets('boş masaya taşıma ancak elde kişi varken açılıyor',
        (tester) async {
      await _pump(
        tester,
        TableCard(
          table: _table(number: 2),
          selectedAssignmentId: null,
          onTapTable: null,
          onTapPerson: (_) {},
          onTogglePin: (_) {},
        ),
      );

      expect(find.text('Bu masa boş.'), findsOneWidget);
      expect(find.textContaining('dokun'), findsNothing);
    });

    testWidgets('elde kişi varken boş masa hedef oluyor', (tester) async {
      var tapped = false;
      await _pump(
        tester,
        TableCard(
          table: _table(number: 2),
          selectedAssignmentId: 9,
          onTapTable: () => tapped = true,
          onTapPerson: (_) {},
          onTogglePin: (_) {},
        ),
      );

      await tester.tap(find.textContaining('Boş — buraya taşımak için dokun'));
      expect(tapped, isTrue);
    });

    testWidgets('dolu masada "buraya taşı" satırı çıkmıyor', (tester) async {
      await _pump(
        tester,
        TableCard(
          table: _table(
            capacity: 1,
            occupants: [_person(assignmentId: 1)],
          ),
          selectedAssignmentId: 9,
          onTapTable: () {},
          onTapPerson: (_) {},
          onTogglePin: (_) {},
        ),
      );

      expect(find.text('Buraya taşı'), findsNothing);
    });

    testWidgets('kapasite aşımı sayının kendisinden okunuyor', (tester) async {
      await _pump(
        tester,
        TableCard(
          table: _table(
            capacity: 2,
            quality: 'weak',
            occupants: [
              _person(assignmentId: 1),
              _person(assignmentId: 2),
              _person(assignmentId: 3),
            ],
          ),
          selectedAssignmentId: null,
          onTapTable: null,
          onTapPerson: (_) {},
          onTogglePin: (_) {},
        ),
      );

      expect(find.text('3/2'), findsOneWidget);
    });
  });

  group('şeritler', () {
    testWidgets('takas ipucu seçili kişiyi söylüyor', (tester) async {
      await _pump(
        tester,
        SwapHint(selected: 'Ayşe Yılmaz', onCancel: () {}),
      );

      expect(find.textContaining('Ayşe Yılmaz seçildi'), findsOneWidget);
      expect(find.text('Vazgeç'), findsOneWidget);
    });

    testWidgets('seçim yokken ne yapılacağı yazıyor', (tester) async {
      await _pump(tester, SwapHint(selected: null, onCancel: () {}));

      expect(find.textContaining('önce bir kişiye dokun'), findsOneWidget);
      expect(find.text('Vazgeç'), findsNothing);
    });

    testWidgets('uyarı şeridi takasın yapıldığını söylüyor', (tester) async {
      // M7: *"Organizatör uyarıya rağmen devam edebilir."* Şerit takası geri
      // almıyor, ne olduğunu söylüyor.
      await _pump(
        tester,
        SwapWarningBanner(
          warnings: [
            SwapWarning.fromJson({
              'key': 'same_company',
              'table_number': 3,
              'people': ['Ayşe Yılmaz', 'Mehmet Demir'],
              'slot_number': null,
            }),
          ],
          onDismiss: () {},
        ),
      );

      expect(find.text('Takas yapıldı, ama dikkat'), findsOneWidget);
      expect(find.textContaining('aynı şirketten'), findsOneWidget);
    });

    testWidgets('ret şeridi uyarıdan ayrı', (tester) async {
      await _pump(
        tester,
        SwapErrorBanner(
          message: 'Bu atama sabitlenmiş; önce sabitlemeyi kaldır.',
          onDismiss: () {},
        ),
      );

      expect(find.textContaining('sabitlenmiş'), findsOneWidget);
      // Takas olmadı: "yapıldı" demiyor.
      expect(find.textContaining('Takas yapıldı'), findsNothing);
    });
  });

  group('özet paneli', () {
    PlanSummary plan({List<String> unmatched = const [], int requests = 0}) {
      return PlanSummary.fromJson({
        'id': 3,
        'version': 2,
        'status': 'draft',
        'job_status': 'done',
        'job_error': null,
        'created_at': '2026-08-06T14:30:00Z',
        'published_at': null,
        'seed': 42,
        'total_meetings': 96,
        'min_meetings_per_person': 4,
        'average_table_score': 0.42,
        'runtime_ms': 3286,
        'assignment_count': 96,
        'participant_count': 24,
        'unmatched': unmatched,
        'satisfied_requests': requests > 0 ? 3 : 0,
        'total_requests': requests,
        'unmet_requests': <Map<String, dynamic>>[],
      });
    }

    testWidgets('en az görüşme alan kişinin sayısı görünüyor', (tester) async {
      // Bölüm 10'un kabul kriteri. Ortalama iyi görünen bir plan tek kişiyi
      // ortada bırakmış olabilir; bu sayı onu ele veriyor.
      await _pump(tester, PlanSummaryPanel(plan: plan()));

      expect(find.text('En az görüşme'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);
      expect(find.text('96'), findsOneWidget);
      expect(find.text('24'), findsOneWidget);
    });

    testWidgets('hiç eşleşmeyenler isimle listeleniyor', (tester) async {
      await _pump(
        tester,
        PlanSummaryPanel(
          plan: plan(unmatched: ['Ayşe Yılmaz', 'Mehmet Demir']),
        ),
      );

      expect(find.text('Hiç eşleşmeyen 2 kişi'), findsOneWidget);
      expect(find.text('Ayşe Yılmaz'), findsOneWidget);
      expect(find.text('Mehmet Demir'), findsOneWidget);
    });

    testWidgets('eşleşmeyen yoksa bölüm hiç çıkmıyor', (tester) async {
      await _pump(tester, PlanSummaryPanel(plan: plan()));

      expect(find.textContaining('Hiç eşleşmeyen'), findsNothing);
    });

    testWidgets('talep sayacı ancak talep varsa görünüyor', (tester) async {
      await _pump(tester, PlanSummaryPanel(plan: plan()));
      expect(find.text('Karşılanan talep'), findsNothing);

      await _pump(tester, PlanSummaryPanel(plan: plan(requests: 5)));
      expect(find.text('Karşılanan talep'), findsOneWidget);
      expect(find.text('3/5'), findsOneWidget);
    });
  });

  group('kalite rozeti', () {
    testWidgets('üç seviye üç ayrı renk', (tester) async {
      await _pump(
        tester,
        const Column(
          children: [
            QualityBadge(quality: TableQuality.good),
            QualityBadge(quality: TableQuality.fair),
            QualityBadge(quality: TableQuality.weak),
          ],
        ),
      );

      expect(find.text('İyi'), findsOneWidget);
      expect(find.text('Orta'), findsOneWidget);
      expect(find.text('Zayıf'), findsOneWidget);

      final colors = tester
          .widgetList<Container>(find.byType(Container))
          .map((box) => (box.decoration! as BoxDecoration).border)
          .toSet();
      // Aynı renk iki seviyeyi anlatırsa rozet hiçbir şey anlatmaz.
      expect(colors.length, 3);
    });

    testWidgets('tek kişilik masaya "Boş" yazmıyor', (tester) async {
      // Sunucu tek kişilik masaya kalite vermiyor (skor en zayıf ikili bağ,
      // tek kişide bağ yok). Rozete "Boş" yazmak yanlış olurdu: masada biri
      // oturuyor. Tarayıcıda "1/3 · Boş" görüldükten sonra düzeltildi.
      await _pump(
        tester,
        const QualityBadge(quality: TableQuality.empty, occupantCount: 1),
      );

      expect(find.text('Tek kişi'), findsOneWidget);
      expect(find.text('Boş'), findsNothing);
    });

    testWidgets('gerçekten boş masa "Boş" diyor', (tester) async {
      await _pump(
        tester,
        const QualityBadge(quality: TableQuality.empty, occupantCount: 0),
      );

      expect(find.text('Boş'), findsOneWidget);
    });
  });
}
