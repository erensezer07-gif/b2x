// Katılımcı görünümü — arayüz testleri (şartname M8, Bölüm 10).
//
// Kabul kriteri: *"Her masa arkadaşı için anlamlı bir cümle gösteriliyor.
// Hiçbir yerde sayısal skor görünmüyor."*
//
// Gerekçe cümleleri bu katmanda kuruluyor: sunucu {kind, values} gönderiyor.
// Çevirinin kopması sessiz bir hata olurdu — katılımcı boş bir kart görür.

import 'package:b2x/core/theme/app_theme.dart';
import 'package:b2x/features/events/models.dart';
import 'package:b2x/features/events/my_plan_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _reasonJson(String kind, List<String> values) => {
      'kind': kind,
      'values': values,
    };

Map<String, dynamic> _mateJson({
  int registrationId = 11,
  String? name = 'Ayşe Yılmaz',
  String? title = 'Kurucu',
  String? company = 'Yılmaz Ticaret',
  List<Map<String, dynamic>> reasons = const [],
}) {
  return {
    'registration_id': registrationId,
    'full_name': name,
    'title': title,
    'company': company,
    'photo_url': null,
    'reasons': reasons,
  };
}

Map<String, dynamic> _slotJson({
  int slotNumber = 1,
  int? tableNumber = 3,
  int? tableId = 30,
  String? tableLabel,
  List<Map<String, dynamic>> mates = const [],
}) {
  return {
    'slot_number': slotNumber,
    'starts_at': '2026-12-01T09:00:00Z',
    'ends_at': '2026-12-01T09:20:00Z',
    'table_id': tableId,
    'table_number': tableNumber,
    'table_label': tableLabel,
    'tablemates': mates,
  };
}

Map<String, dynamic> _planJson({
  bool published = true,
  int? version = 1,
  List<Map<String, dynamic>> slots = const [],
}) {
  return {
    'is_published': published,
    'plan_version': version,
    'slots': slots,
  };
}

Future<void> _pump(WidgetTester tester, Widget child) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
}

/// Kendi kaydırmasını kuran bileşenler için.
///
/// `TablemateProfileView` bir `ListView`; `SingleChildScrollView` içine
/// konursa yüksekliği sınırsız kalıyor ve düzen kuramıyor.
Future<void> _pumpScrollable(WidgetTester tester, Widget child) async {
  await tester.pumpWidget(
    MaterialApp(theme: AppTheme.light, home: Scaffold(body: child)),
  );
}

void main() {
  group('eşleşme gerekçesi', () {
    String sentence(String kind, List<String> values) =>
        MatchReason.fromJson(_reasonJson(kind, values)).sentence;

    test('her tür Türkçe bir cümleye çevriliyor', () {
      expect(
        sentence('they_offer', ['Yazılım geliştirme']),
        'Kendisi Yazılım geliştirme sunuyor, siz bunu arıyorsunuz.',
      );
      expect(
        sentence('you_offer', ['Lojistik']),
        'Siz Lojistik sunuyorsunuz, kendisi bunu arıyor.',
      );
      expect(sentence('shared_category', ['Finansman']), contains('alanındasınız'));
      expect(sentence('same_sector', ['Fintek']), 'İkiniz de Fintek sektöründesiniz.');
      expect(sentence('same_city', ['İzmir']), 'İkiniz de İzmir şehrindesiniz.');
      expect(sentence('mutual_request', []), 'İkiniz de görüşmek istemiştiniz.');
    });

    test('yön karıştırılmıyor', () {
      // Aynı etiket iki tarafta farklı cümle demek; karışırsa katılımcı
      // kendi sunduğunu aradığını sanır.
      expect(sentence('they_offer', ['ERP']), startsWith('Kendisi'));
      expect(sentence('you_offer', ['ERP']), startsWith('Siz'));
    });

    test('hiçbir cümlede yüzde işareti yok', () {
      // M8: *"'Uyum: %62' gibi bir ifade kullanılmaz."*
      for (final kind in [
        'they_offer',
        'you_offer',
        'shared_category',
        'same_sector',
        'same_city',
        'mutual_request',
      ]) {
        expect(sentence(kind, ['Bir şey']), isNot(contains('%')));
      }
    });

    test('üçten fazla etiket kısaltılıyor', () {
      // Üç etiket birden yazılırsa cümle okunmaz uzunlukta oluyor.
      final text = sentence('they_offer', ['A', 'B', 'C', 'D']);
      expect(text, contains('A, B, 2 alan daha'));
      expect(text, isNot(contains('C')));
    });

    test('iki etiket olduğu gibi yazılıyor', () {
      expect(sentence('they_offer', ['A', 'B']), contains('A ve B'));
    });

    test('kısaltmada bağlaç değil virgül var', () {
      // Etiket adının kendisi "ve" içerebiliyor; bağlaç kullanılırsa
      // "... raporlama ve 1 alan daha" diye çift bağlaç çıkıyor. Tarayıcıda
      // görüldü.
      final text = sentence(
        'they_offer',
        ['Siber güvenlik', 'Veri analitiği ve raporlama', 'Yapay zekâ'],
      );
      expect(text, contains('raporlama, 1 alan daha'));
      expect(text, isNot(contains('raporlama ve 1')));
    });

    test('birden fazla etikette zamir çoğul', () {
      expect(sentence('they_offer', ['A']), contains('siz bunu arıyorsunuz'));
      expect(
        sentence('they_offer', ['A', 'B']),
        contains('siz bunları arıyorsunuz'),
      );
      expect(sentence('you_offer', ['A']), contains('kendisi bunu arıyor'));
      expect(
        sentence('you_offer', ['A', 'B']),
        contains('kendisi bunları arıyor'),
      );
    });

    test('tanınmayan tür boş dönüyor ve gösterilmiyor', () {
      // Uydurma bir cümle yazmaktansa susmak doğru.
      expect(sentence('gelecekte_eklenen', ['X']), isEmpty);

      final mate = Tablemate.fromJson(
        _mateJson(reasons: [_reasonJson('gelecekte_eklenen', ['X'])]),
      );
      expect(mate.sentences, isEmpty);
    });
  });

  group('plan modeli', () {
    test('sunucu yanıtı eksiksiz okunuyor', () {
      final plan = MyPlan.fromJson(
        _planJson(
          slots: [
            _slotJson(slotNumber: 1, mates: [_mateJson()]),
            _slotJson(slotNumber: 2, tableNumber: null, tableId: null),
          ],
        ),
      );

      expect(plan.isPublished, isTrue);
      expect(plan.planVersion, 1);
      expect(plan.slots, hasLength(2));
      expect(plan.seatedCount, 1);
      expect(plan.meetingCount, 1);
    });

    test('oturmadığı tur serbest sayılıyor', () {
      final slot = MySlot.fromJson(_slotJson(tableNumber: null, tableId: null));

      expect(slot.isFree, isTrue);
      expect(slot.tableTitle, 'Serbest');
      expect(slot.tablemates, isEmpty);
    });

    test('masa etiketi varsa numara yerine o yazılıyor', () {
      expect(
        MySlot.fromJson(_slotJson(tableLabel: 'Pencere kenarı')).tableTitle,
        'Pencere kenarı',
      );
      expect(MySlot.fromJson(_slotJson(tableNumber: 7)).tableTitle, 'Masa 7');
    });

    test('yayınlanmamış plan boş geliyor', () {
      final plan = MyPlan.fromJson(_planJson(published: false, version: null));

      expect(plan.isPublished, isFalse);
      expect(plan.planVersion, isNull);
      expect(plan.slots, isEmpty);
    });

    test('adı girilmemiş kişi de gösterilebiliyor', () {
      expect(
        Tablemate.fromJson(_mateJson(name: null)).displayName,
        'Adı girilmemiş',
      );
    });
  });

  group('slot listesi', () {
    testWidgets('tur, saat, masa ve isimler görünüyor', (tester) async {
      await _pump(
        tester,
        MySlotRow(
          slot: MySlot.fromJson(
            _slotJson(slotNumber: 2, tableNumber: 5, mates: [_mateJson()]),
          ),
          onOpen: () {},
        ),
      );

      expect(find.text('2. Tur'), findsOneWidget);
      expect(find.text('Masa 5'), findsOneWidget);
      expect(find.textContaining('Ayşe Yılmaz'), findsOneWidget);
      expect(find.textContaining('Yılmaz Ticaret'), findsOneWidget);
    });

    testWidgets('boş tur açıklamayla gösteriliyor', (tester) async {
      // M8: *"Boş bırakılmaz, açıklama yazılır."*
      await _pump(
        tester,
        MySlotRow(
          slot: MySlot.fromJson(_slotJson(tableNumber: null, tableId: null)),
          onOpen: null,
        ),
      );

      expect(find.text('Bu turda serbestsin.'), findsOneWidget);
      expect(find.byIcon(Icons.chevron_right), findsNothing);
    });

    testWidgets('dolu tura dokununca bildiriliyor', (tester) async {
      var opened = false;
      await _pump(
        tester,
        MySlotRow(
          slot: MySlot.fromJson(_slotJson(mates: [_mateJson()])),
          onOpen: () => opened = true,
        ),
      );

      await tester.tap(find.text('Masa 3'));
      expect(opened, isTrue);
    });

    testWidgets('özet kaç kişiyle tanışılacağını söylüyor', (tester) async {
      await _pump(
        tester,
        MyPlanHeadline(
          plan: MyPlan.fromJson(
            _planJson(
              slots: [
                _slotJson(slotNumber: 1, mates: [_mateJson(), _mateJson(registrationId: 12)]),
                _slotJson(slotNumber: 2, tableNumber: null, tableId: null),
              ],
            ),
          ),
        ),
      );

      expect(find.textContaining('1 turda 2 kişiyle'), findsOneWidget);
    });
  });

  group('tur detayı', () {
    testWidgets('masa numarası büyük ve net', (tester) async {
      await _pump(
        tester,
        SlotHeadline(slot: MySlot.fromJson(_slotJson(tableNumber: 9))),
      );

      expect(find.text('Masa 9'), findsOneWidget);
      final text = tester.widget<Text>(find.text('Masa 9'));
      expect(text.style?.fontSize, greaterThan(20));
    });

    testWidgets('masa arkadaşı kartı ad, unvan, şirket ve gerekçe taşıyor',
        (tester) async {
      await _pump(
        tester,
        TablemateCard(
          mate: Tablemate.fromJson(
            _mateJson(
              reasons: [
                _reasonJson('they_offer', ['Yazılım geliştirme']),
                _reasonJson('same_sector', ['Fintek']),
              ],
            ),
          ),
          onOpen: () {},
        ),
      );

      expect(find.text('Ayşe Yılmaz'), findsOneWidget);
      expect(find.text('Kurucu'), findsOneWidget);
      expect(find.text('Yılmaz Ticaret'), findsOneWidget);
      expect(find.textContaining('siz bunu arıyorsunuz'), findsOneWidget);
      expect(find.textContaining('Fintek sektöründesiniz'), findsOneWidget);
    });

    testWidgets('gerekçesiz kart da çiziliyor', (tester) async {
      await _pump(
        tester,
        TablemateCard(mate: Tablemate.fromJson(_mateJson()), onOpen: () {}),
      );

      expect(find.text('Ayşe Yılmaz'), findsOneWidget);
      expect(find.byType(Divider), findsNothing);
    });

    testWidgets('karta dokununca profil açılıyor', (tester) async {
      var opened = false;
      await _pump(
        tester,
        TablemateCard(
          mate: Tablemate.fromJson(_mateJson()),
          onOpen: () => opened = true,
        ),
      );

      await tester.tap(find.text('Ayşe Yılmaz'));
      expect(opened, isTrue);
    });
  });

  group('salon krokisi', () {
    Venue venue({
      int? gridWidth = 8,
      int? gridHeight = 6,
      List<Map<String, dynamic>> tables = const [],
    }) {
      return Venue.fromJson({
        'mode': 'manual',
        'grid_width': gridWidth,
        'grid_height': gridHeight,
        'tables': tables,
        'areas': [],
      });
    }

    Map<String, dynamic> table({
      int id = 30,
      int number = 3,
      int? gridX = 2,
      int? gridY = 1,
    }) {
      return {
        'id': id,
        'number': number,
        'label': null,
        'grid_x': gridX,
        'grid_y': gridY,
      };
    }

    test('ızgarasız düzende kroki çizilemez', () {
      // Otomatik modda görsel kroki yok (M5); yalnızca masa numarası.
      expect(venue(gridWidth: null, gridHeight: null).hasSketch, isFalse);
    });

    test('yerleştirilmemiş masa varsa kroki çizilmiyor', () {
      expect(venue(tables: [table(gridX: null, gridY: null)]).hasSketch, isFalse);
      expect(venue(tables: [table()]).hasSketch, isTrue);
    });

    testWidgets('kendi masası vurgulanıyor, kimse çizilmiyor', (tester) async {
      await _pump(
        tester,
        VenueSketch(
          venue: venue(
            tables: [table(id: 30, number: 3), table(id: 31, number: 4, gridX: 5)],
          ),
          highlightTableId: 30,
        ),
      );

      expect(find.text('3'), findsOneWidget);
      expect(find.text('4'), findsOneWidget);
      // Kroki oturan bilgisi taşımıyor: uçtan da gelmiyor.
      expect(find.text('Ayşe Yılmaz'), findsNothing);
    });
  });

  group('masa arkadaşı profili', () {
    TablemateProfile profile({
      List<Map<String, dynamic>> offered = const [],
      List<Map<String, dynamic>> sought = const [],
    }) {
      return TablemateProfile.fromJson({
        'registration_id': 11,
        'full_name': 'Mehmet Demir',
        'title': 'Satın Alma Müdürü',
        'city': 'Bursa',
        'bio': 'On yıldır ihracat yapıyoruz.',
        'photo_url': null,
        'website': null,
        'linkedin_url': null,
        'company': {'id': 1, 'name': 'Demir Ticaret'},
        'sector': {'id': 2, 'name': 'Lojistik'},
        'offered_tags': offered,
        'sought_tags': sought,
      });
    }

    testWidgets('tam profil gösteriliyor', (tester) async {
      await _pumpScrollable(
        tester,
        TablemateProfileView(
          profile: profile(
            offered: [
              {'id': 1, 'name': 'Depolama'},
            ],
            sought: [
              {'id': 2, 'name': 'Yazılım'},
            ],
          ),
        ),
      );

      expect(find.text('Mehmet Demir'), findsOneWidget);
      expect(find.text('Satın Alma Müdürü'), findsOneWidget);
      expect(find.text('Demir Ticaret'), findsOneWidget);
      expect(find.text('Lojistik'), findsOneWidget);
      expect(find.text('Bursa'), findsOneWidget);
      expect(find.text('On yıldır ihracat yapıyoruz.'), findsOneWidget);
      expect(find.text('Depolama'), findsOneWidget);
      expect(find.text('Yazılım'), findsOneWidget);
    });

    testWidgets('etiketsiz profil boş liste yerine cümle gösteriyor',
        (tester) async {
      await _pumpScrollable(tester, TablemateProfileView(profile: profile()));

      expect(find.text('Belirtilmemiş.'), findsNWidgets(2));
    });

    testWidgets('fotoğraf yoksa baş harf çıkıyor', (tester) async {
      await _pump(
        tester,
        const PersonAvatar(photoUrl: null, name: 'ayşe yılmaz'),
      );

      expect(find.text('A'), findsOneWidget);
    });
  });
}
