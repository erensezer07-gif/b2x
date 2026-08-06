/// Etkinlik ve salon düzeni modelleri (şartname M4, M5).
library;

import 'schedule.dart';

/// Etkinlik durumu — yalnızca **başvuru akışını** yönetir (Bölüm 6).
///
/// Planın hazır veya yayında olup olmadığı buraya yazılmaz; o bilgi plan
/// tablosundan gelir (Bölüm 5.2, Bölüm 13).
enum EventStatus {
  draft('draft', 'Taslak'),
  registrationOpen('registration_open', 'Kayıtlar açık'),
  registrationClosed('registration_closed', 'Kayıtlar kapalı'),
  completed('completed', 'Tamamlandı');

  const EventStatus(this.key, this.label);

  final String key;
  final String label;

  static EventStatus fromKey(String key) => EventStatus.values.firstWhere(
        (item) => item.key == key,
        orElse: () => EventStatus.draft,
      );
}

enum TableKind {
  seated('seated', 'Oturmalı'),
  standing('standing', 'Ayaklı');

  const TableKind(this.key, this.label);

  final String key;
  final String label;

  static TableKind fromKey(String key) => TableKind.values.firstWhere(
        (item) => item.key == key,
        orElse: () => TableKind.seated,
      );
}

/// Salon düzeninin modu (M5).
///
/// Otomatik modda görsel kroki yoktur, katılımcıya yalnızca masa numarası
/// gösterilir. Manuel modda organizatör salonu ızgara üzerinde kurar.
enum LayoutMode {
  auto('auto', 'Otomatik'),
  manual('manual', 'Manuel');

  const LayoutMode(this.key, this.label);

  final String key;
  final String label;

  static LayoutMode fromKey(String key) => LayoutMode.values.firstWhere(
        (item) => item.key == key,
        orElse: () => LayoutMode.auto,
      );
}

/// Liste görünümü için kısa özet.
class EventSummary {
  const EventSummary({
    required this.id,
    required this.name,
    required this.startsAt,
    required this.status,
    required this.slotCount,
    required this.capacity,
    this.venueName,
  });

  factory EventSummary.fromJson(Map<String, dynamic> json) => EventSummary(
        id: json['id'] as int,
        name: json['name'] as String,
        startsAt: DateTime.parse(json['starts_at'] as String).toLocal(),
        status: EventStatus.fromKey(json['status'] as String),
        slotCount: json['slot_count'] as int,
        capacity: json['capacity'] as int,
        venueName: json['venue_name'] as String?,
      );

  final int id;
  final String name;
  final DateTime startsAt;
  final EventStatus status;
  final int slotCount;
  final int capacity;
  final String? venueName;
}

/// Kontenjan ile salon kapasitesinin karşılaştırması (M4).
///
/// *"Kontenjan kapasiteden büyükse organizatör uyarılır. Bu bir engel değil
/// uyarıdır, çünkü gelmeyecekler hesaba katılabilir."*
class CapacitySummary {
  const CapacitySummary({
    required this.capacity,
    required this.seatingCapacity,
    required this.tableCount,
    required this.exceedsSeating,
  });

  factory CapacitySummary.fromJson(Map<String, dynamic> json) => CapacitySummary(
        capacity: json['capacity'] as int,
        seatingCapacity: json['seating_capacity'] as int,
        tableCount: json['table_count'] as int,
        exceedsSeating: json['exceeds_seating'] as bool,
      );

  final int capacity;
  final int seatingCapacity;
  final int tableCount;
  final bool exceedsSeating;
}

/// Etkinliğin tamamı: alanlar, hesaplanmış program ve kapasite özeti.
class EventDetail {
  const EventDetail({
    required this.id,
    required this.name,
    required this.startsAt,
    required this.slotDurationMinutes,
    required this.breakDurationMinutes,
    required this.slotCount,
    required this.capacity,
    required this.autoApproveRegistrations,
    required this.requestQuota,
    required this.status,
    required this.schedule,
    required this.endsAt,
    required this.totalMinutes,
    required this.capacitySummary,
    required this.hasLayout,
    required this.canOpenRegistration,
    this.description,
    this.coverUrl,
    this.venueName,
    this.address,
    this.registrationDeadline,
    this.requestsCloseAt,
  });

  factory EventDetail.fromJson(Map<String, dynamic> json) {
    DateTime? optionalDate(String key) {
      final raw = json[key] as String?;
      return raw == null ? null : DateTime.parse(raw).toLocal();
    }

    return EventDetail(
      id: json['id'] as int,
      name: json['name'] as String,
      description: json['description'] as String?,
      coverUrl: json['cover_url'] as String?,
      startsAt: DateTime.parse(json['starts_at'] as String).toLocal(),
      venueName: json['venue_name'] as String?,
      address: json['address'] as String?,
      slotDurationMinutes: json['slot_duration_minutes'] as int,
      breakDurationMinutes: json['break_duration_minutes'] as int,
      slotCount: json['slot_count'] as int,
      capacity: json['capacity'] as int,
      registrationDeadline: optionalDate('registration_deadline'),
      autoApproveRegistrations: json['auto_approve_registrations'] as bool,
      requestQuota: json['request_quota'] as int,
      requestsCloseAt: optionalDate('requests_close_at'),
      status: EventStatus.fromKey(json['status'] as String),
      schedule: (json['schedule'] as List<dynamic>)
          .map((item) => SlotTiming.fromJson(item as Map<String, dynamic>))
          .toList(),
      endsAt: DateTime.parse(json['ends_at'] as String).toLocal(),
      totalMinutes: json['total_minutes'] as int,
      capacitySummary:
          CapacitySummary.fromJson(json['capacity_summary'] as Map<String, dynamic>),
      hasLayout: json['has_layout'] as bool,
      canOpenRegistration: json['can_open_registration'] as bool,
    );
  }

  final int id;
  final String name;
  final String? description;
  final String? coverUrl;
  final DateTime startsAt;
  final String? venueName;
  final String? address;

  final int slotDurationMinutes;
  final int breakDurationMinutes;
  final int slotCount;

  final int capacity;
  final DateTime? registrationDeadline;
  final bool autoApproveRegistrations;
  final int requestQuota;
  final DateTime? requestsCloseAt;

  final EventStatus status;

  /// Sunucunun hesapladığı program — kaydedilmiş hâlin doğrusu.
  final List<SlotTiming> schedule;
  final DateTime endsAt;
  final int totalMinutes;

  final CapacitySummary capacitySummary;
  final bool hasLayout;

  /// Salon düzeni kurulmadan kayıtlar açılamaz (M4). Arayüz düğmeyi buna
  /// bakarak kapatıyor; asıl kapı sunucuda.
  final bool canOpenRegistration;
}

class EventTable {
  const EventTable({
    required this.id,
    required this.number,
    required this.kind,
    this.seatCount,
    this.minPeople,
    this.maxPeople,
    this.label,
    this.gridX,
    this.gridY,
  });

  factory EventTable.fromJson(Map<String, dynamic> json) => EventTable(
        id: json['id'] as int,
        number: json['number'] as int,
        kind: TableKind.fromKey(json['kind'] as String),
        seatCount: json['seat_count'] as int?,
        minPeople: json['min_people'] as int?,
        maxPeople: json['max_people'] as int?,
        label: json['label'] as String?,
        gridX: json['grid_x'] as int?,
        gridY: json['grid_y'] as int?,
      );

  final int id;
  final int number;
  final TableKind kind;
  final int? seatCount;
  final int? minPeople;
  final int? maxPeople;
  final String? label;

  /// Izgaradaki yeri — yalnızca manuel modda dolu.
  final int? gridX;
  final int? gridY;

  /// Masaya oturabilecek azami kişi (9.5).
  ///
  /// Ayaklı masanın **alt** sınırı bir hedeftir, kapasiteye girmez.
  int get capacity => seatCount ?? maxPeople ?? 0;

  bool get isPlaced => gridX != null && gridY != null;
}

/// Sahne, giriş, büfe gibi masa olmayan işaretler (M5).
///
/// *"Sadece metin etiketi ve konum. Katılımcının salonda yön bulmasına
/// yarar."* Eşleştirmeye girmez, kapasiteye sayılmaz.
class LayoutArea {
  const LayoutArea({
    required this.id,
    required this.label,
    required this.gridX,
    required this.gridY,
    required this.width,
    required this.height,
  });

  factory LayoutArea.fromJson(Map<String, dynamic> json) => LayoutArea(
        id: json['id'] as int,
        label: json['label'] as String,
        gridX: json['grid_x'] as int,
        gridY: json['grid_y'] as int,
        width: json['width'] as int,
        height: json['height'] as int,
      );

  final int id;
  final String label;
  final int gridX;
  final int gridY;
  final int width;
  final int height;
}

class EventLayout {
  const EventLayout({
    required this.id,
    required this.mode,
    required this.tables,
    required this.areas,
    required this.seatingCapacity,
    this.gridWidth,
    this.gridHeight,
  });

  factory EventLayout.fromJson(Map<String, dynamic> json) => EventLayout(
        id: json['id'] as int,
        mode: LayoutMode.fromKey(json['mode'] as String),
        gridWidth: json['grid_width'] as int?,
        gridHeight: json['grid_height'] as int?,
        tables: (json['tables'] as List<dynamic>)
            .map((item) => EventTable.fromJson(item as Map<String, dynamic>))
            .toList(),
        areas: (json['areas'] as List<dynamic>)
            .map((item) => LayoutArea.fromJson(item as Map<String, dynamic>))
            .toList(),
        seatingCapacity: json['seating_capacity'] as int,
      );

  final int id;
  final LayoutMode mode;

  /// Izgara ölçüsü — yalnızca manuel modda dolu.
  final int? gridWidth;
  final int? gridHeight;

  final List<EventTable> tables;
  final List<LayoutArea> areas;
  final int seatingCapacity;

  bool get isEmpty => tables.isEmpty && areas.isEmpty;

  /// Kullanılmamış en küçük numara — yeni masaya önerilir (M5).
  int get nextTableNumber =>
      tables.fold(0, (highest, table) => table.number > highest ? table.number : highest) + 1;
}
