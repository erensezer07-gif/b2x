// Manuel salon editörü — arayüz testleri (şartname M5, Bölüm 10).
//
// Kabul kriteri: *"Masa sürüklenip bırakıldığında ızgaraya oturuyor."*
// Oturma hesabı istemcide; sunucu hazır hücre koordinatı alıyor. Bu yüzden
// yuvarlamanın doğruluğu burada kilitleniyor.

import 'package:b2x/core/theme/app_theme.dart';
import 'package:b2x/features/events/layout/layout_canvas.dart';
import 'package:b2x/features/events/layout/layout_sheets.dart';
import 'package:b2x/features/events/models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

const _cell = AppSpacing.gridCell;

EventLayout _layout({
  List<EventTable> tables = const [],
  List<LayoutArea> areas = const [],
  int gridWidth = 8,
  int gridHeight = 6,
}) {
  return EventLayout(
    id: 1,
    mode: LayoutMode.manual,
    gridWidth: gridWidth,
    gridHeight: gridHeight,
    tables: tables,
    areas: areas,
    seatingCapacity: tables.fold(0, (sum, table) => sum + table.capacity),
  );
}

EventTable _table({
  required int id,
  required int number,
  int? gridX,
  int? gridY,
  int seatCount = 6,
}) {
  return EventTable(
    id: id,
    number: number,
    kind: TableKind.seated,
    seatCount: seatCount,
    gridX: gridX,
    gridY: gridY,
  );
}

Future<void> _pumpCanvas(
  WidgetTester tester,
  EventLayout layout, {
  CanvasTool? tool,
  void Function(int, int)? onPlace,
  void Function(EventTable, int, int)? onMoveTable,
  void Function(LayoutArea, int, int)? onMoveArea,
  ValueChanged<EventTable>? onSelectTable,
  ValueChanged<LayoutArea>? onSelectArea,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.light,
      home: Scaffold(
        body: LayoutCanvas(
          layout: layout,
          controller: TransformationController(),
          tool: tool,
          busy: false,
          onPlace: onPlace ?? (_, _) {},
          onMoveTable: onMoveTable ?? (_, _, _) {},
          onMoveArea: onMoveArea ?? (_, _, _) {},
          onSelectTable: onSelectTable ?? (_) {},
          onSelectArea: onSelectArea ?? (_) {},
        ),
      ),
    ),
  );
}

void main() {
  group('ızgaraya oturma', () {
    test('hücrenin yarısını geçmeyen sürükleme yerinde kalır', () {
      // 2. hücreden başlayıp 30 piksel kaydırma: yarıyı (32) geçmiyor.
      expect(snapToGrid(2 * _cell + 30, 10), 2);
    });

    test('hücrenin yarısını geçen sürükleme bir sonrakine oturur', () {
      expect(snapToGrid(2 * _cell + 34, 10), 3);
    });

    test('geriye sürükleme de en yakına oturur', () {
      expect(snapToGrid(3 * _cell - 34, 10), 2);
      expect(snapToGrid(3 * _cell - 30, 10), 3);
    });

    test('tuvalin dışına taşan sürükleme kenara sıkışır', () {
      expect(snapToGrid(-200, 10), 0);
      expect(snapToGrid(99 * _cell, 7), 7);
    });

    test('çok hücreli öğe için üst sınır genişliği kadar geride', () {
      // 8 sütunluk ızgarada 3 hücrelik alan bloğu en fazla 5. sütundan başlar.
      expect(snapToGrid(99 * _cell, 8 - 3), 5);
    });

    test('öğe ızgaradan genişse sıfıra oturur', () {
      expect(snapToGrid(400, -1), 0);
    });
  });

  group('tuval', () {
    testWidgets('yerleşmiş masalar numaralarıyla çizilir', (tester) async {
      await _pumpCanvas(
        tester,
        _layout(tables: [
          _table(id: 1, number: 1, gridX: 0, gridY: 0),
          _table(id: 2, number: 7, gridX: 3, gridY: 2),
        ]),
      );

      expect(find.text('1'), findsOneWidget);
      expect(find.text('7'), findsOneWidget);
    });

    testWidgets('konumu olmayan masa tuvale çizilmez', (tester) async {
      // Otomatik moddan kalan, henüz dizilmemiş masa krokide yeri olmadan
      // görünmemeli.
      await _pumpCanvas(
        tester,
        _layout(tables: [_table(id: 1, number: 4)]),
      );

      expect(find.text('4'), findsNothing);
    });

    testWidgets('alan blokları etiketleriyle çizilir', (tester) async {
      await _pumpCanvas(
        tester,
        _layout(areas: const [
          LayoutArea(id: 1, label: 'Sahne', gridX: 0, gridY: 0, width: 3, height: 1),
        ]),
      );

      expect(find.text('Sahne'), findsOneWidget);
    });

    testWidgets('araç seçiliyken boş hücreye dokunma o hücreyi bildirir',
        (tester) async {
      final placed = <(int, int)>[];
      await _pumpCanvas(
        tester,
        _layout(),
        tool: CanvasTool.seatedTable,
        onPlace: (x, y) => placed.add((x, y)),
      );

      // 4. sütun, 2. satırın ortası.
      await tester.tapAt(Offset(4 * _cell + _cell / 2, 2 * _cell + _cell / 2));
      await tester.pump();

      expect(placed, [(4, 2)]);
    });

    testWidgets('araç seçili değilken dokunma masa koymaz', (tester) async {
      // Yanlışlıkla masa serpiştirmeyi engelliyor.
      final placed = <(int, int)>[];
      await _pumpCanvas(tester, _layout(), onPlace: (x, y) => placed.add((x, y)));

      await tester.tapAt(const Offset(_cell / 2, _cell / 2));
      await tester.pump();

      expect(placed, isEmpty);
    });

    testWidgets('masaya dokunma paneli açacak seçimi bildirir', (tester) async {
      final selected = <int>[];
      await _pumpCanvas(
        tester,
        _layout(tables: [_table(id: 9, number: 3, gridX: 1, gridY: 1)]),
        onSelectTable: (table) => selected.add(table.id),
      );

      await tester.tapAt(const Offset(1.5 * _cell, 1.5 * _cell));
      await tester.pump();

      expect(selected, [9]);
    });

    testWidgets('masa sürüklenip bırakılınca ızgaraya oturmuş konum bildirilir',
        (tester) async {
      final moves = <(int, int, int)>[];
      await _pumpCanvas(
        tester,
        _layout(tables: [_table(id: 5, number: 2, gridX: 1, gridY: 1)]),
        onMoveTable: (table, x, y) => moves.add((table.id, x, y)),
      );

      // İki hücre sağa, bir hücre aşağı — üstüne hücrenin dörtte biri kadar
      // fazla; yuvarlama onu yutmalı.
      await tester.drag(
        find.text('2'),
        const Offset(2 * _cell + _cell / 4, _cell + _cell / 4),
      );
      await tester.pump();

      expect(moves, [(5, 3, 2)]);
    });

    testWidgets('aynı hücreye bırakılan masa için istek atılmaz', (tester) async {
      final moves = <(int, int, int)>[];
      await _pumpCanvas(
        tester,
        _layout(tables: [_table(id: 5, number: 2, gridX: 1, gridY: 1)]),
        onMoveTable: (table, x, y) => moves.add((table.id, x, y)),
      );

      await tester.drag(find.text('2'), const Offset(6, 4));
      await tester.pump();

      expect(moves, isEmpty);
    });

    testWidgets('alan bloğu sürüklenince kendi hareketi bildirilir',
        (tester) async {
      final moves = <(int, int, int)>[];
      await _pumpCanvas(
        tester,
        _layout(areas: const [
          LayoutArea(id: 4, label: 'Büfe', gridX: 0, gridY: 0, width: 2, height: 1),
        ]),
        onMoveArea: (area, x, y) => moves.add((area.id, x, y)),
      );

      await tester.drag(find.text('Büfe'), const Offset(3 * _cell, 2 * _cell));
      await tester.pump();

      expect(moves, [(4, 3, 2)]);
    });
  });

  group('masa paneli', () {
    /// Paneli açar; kaydedilen yığınları toplar.
    Future<List<Map<String, dynamic>>> openSheet(
      WidgetTester tester, {
      String? Function(Map<String, dynamic>)? failWith,
    }) async {
      final saved = <Map<String, dynamic>>[];
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          home: Scaffold(
            body: Builder(
              builder: (context) => TextButton(
                onPressed: () => showTableSheet(
                  context: context,
                  table: _table(id: 1, number: 7, gridX: 0, gridY: 0),
                  onSave: (changes) async {
                    saved.add(changes);
                    return failWith?.call(changes);
                  },
                  onDelete: () async => null,
                ),
                child: const Text('paneli aç'),
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('paneli aç'));
      await tester.pumpAndSettle();
      return saved;
    }

    testWidgets('arka arkaya iki değişiklik tek istekte birikir', (tester) async {
      // Önceki hâlinde sonraki değişiklik öncekini eziyordu: sandalye sayısını
      // artırıp hemen etiket yazan organizatör ilkini kaybediyordu.
      final saved = await openSheet(tester);

      await tester.tap(find.byTooltip('Sandalye sayısı artır'));
      await tester.pump();
      await tester.enterText(find.byType(TextField).last, 'Sponsor Masası');
      await tester.pump(const Duration(milliseconds: 900));

      expect(saved, hasLength(1));
      expect(saved.single, containsPair('seat_count', 7));
      expect(saved.single, containsPair('label', 'Sponsor Masası'));
    });

    testWidgets('duraklamadan önce istek atılmaz', (tester) async {
      // *"1" → "12"* yazarken yarım numarayı göndermek gereksiz çakışma
      // uyarısı verirdi.
      final saved = await openSheet(tester);

      await tester.enterText(find.byType(TextField).first, '1');
      await tester.pump(const Duration(milliseconds: 200));
      await tester.enterText(find.byType(TextField).first, '12');
      await tester.pump(const Duration(milliseconds: 900));

      expect(saved, hasLength(1));
      expect(saved.single, containsPair('number', 12));
    });

    testWidgets('numara çakışması numaranın altında uyarı verir', (tester) async {
      // *"Bu kritik — katılımcı masasını numarayla buluyor."*
      await openSheet(
        tester,
        failWith: (changes) =>
            changes.containsKey('number') ? 'Bu numara başka bir masada.' : null,
      );

      await tester.enterText(find.byType(TextField).first, '3');
      await tester.pump(const Duration(milliseconds: 900));
      await tester.pump();

      expect(find.text('Bu numara başka bir masada.'), findsOneWidget);
      // Değer alanda kalıyor: organizatör düzeltebilsin.
      expect(find.text('3'), findsOneWidget);
    });

    testWidgets('panel kapanırken bekleyen değişiklik gönderilir', (tester) async {
      final saved = await openSheet(tester);

      await tester.enterText(find.byType(TextField).last, 'Yatırımcı Masası');
      // Duraklama dolmadan panel kapanıyor.
      await tester.pump(const Duration(milliseconds: 100));
      Navigator.of(tester.element(find.byType(TextButton))).pop();
      await tester.pumpAndSettle();

      expect(saved, hasLength(1));
      expect(saved.single, containsPair('label', 'Yatırımcı Masası'));
    });
  });

  group('düzen modeli', () {
    test('sunucu yanıtı ızgara ve alan bloklarıyla okunur', () {
      final layout = EventLayout.fromJson({
        'id': 12,
        'mode': 'manual',
        'grid_width': 24,
        'grid_height': 16,
        'seating_capacity': 6,
        'tables': [
          {
            'id': 3,
            'number': 5,
            'kind': 'seated',
            'seat_count': 6,
            'min_people': null,
            'max_people': null,
            'label': 'Sponsor Masası',
            'grid_x': 2,
            'grid_y': 6,
          },
        ],
        'areas': [
          {
            'id': 8,
            'label': 'Sahne',
            'grid_x': 0,
            'grid_y': 0,
            'width': 4,
            'height': 2,
          },
        ],
      });

      expect(layout.mode, LayoutMode.manual);
      expect(layout.gridWidth, 24);
      expect(layout.gridHeight, 16);
      expect(layout.tables.single.gridX, 2);
      expect(layout.tables.single.isPlaced, isTrue);
      expect(layout.areas.single.label, 'Sahne');
      expect(layout.isEmpty, isFalse);
    });

    test('otomatik modda ızgara boş, masaların yeri yok', () {
      final layout = EventLayout.fromJson({
        'id': 1,
        'mode': 'auto',
        'grid_width': null,
        'grid_height': null,
        'seating_capacity': 12,
        'tables': [
          {
            'id': 1,
            'number': 1,
            'kind': 'standing',
            'seat_count': null,
            'min_people': 3,
            'max_people': 12,
            'label': null,
            'grid_x': null,
            'grid_y': null,
          },
        ],
        'areas': <dynamic>[],
      });

      expect(layout.mode, LayoutMode.auto);
      expect(layout.gridWidth, isNull);
      expect(layout.tables.single.isPlaced, isFalse);
      // Ayaklı masanın kapasitesi üst sınırdan gelir (9.5).
      expect(layout.tables.single.capacity, 12);
    });

    test('yeni masaya önerilen numara en büyüğün bir fazlası', () {
      expect(_layout().nextTableNumber, 1);
      expect(
        _layout(tables: [
          _table(id: 1, number: 3),
          _table(id: 2, number: 9),
          _table(id: 3, number: 4),
        ]).nextTableNumber,
        10,
      );
    });
  });
}
