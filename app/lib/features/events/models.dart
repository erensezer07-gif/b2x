/// Etkinlik, salon düzeni ve başvuru modelleri (şartname M3, M4, M5).
library;

import '../profile/models.dart';
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

// --- Eşleştirme (M6, 5.4) ----------------------------------------------------

/// Eşleştirme hesabının durumu.
///
/// **Plan durumundan ayrı.** `PlanStatus` planın kendisini anlatır, bu ise onu
/// üreten hesabın nerede olduğunu. Hesabı bitmiş bir plan hâlâ taslak olabilir.
enum JobStatus {
  queued('queued', 'Kuyrukta'),
  running('running', 'Çalışıyor'),
  done('done', 'Bitti'),
  failed('failed', 'Hata');

  const JobStatus(this.key, this.label);

  final String key;
  final String label;

  static JobStatus fromKey(String key) => JobStatus.values.firstWhere(
        (item) => item.key == key,
        orElse: () => JobStatus.queued,
      );

  /// Sonuç henüz belli değil — ekran yoklamaya devam etmeli.
  bool get isPending => this == JobStatus.queued || this == JobStatus.running;
}

/// Çalıştırma öncesi uyarılar (M6).
///
/// Sunucu İngilizce anahtar gönderiyor, Türkçe cümle burada kuruluyor —
/// profil eksikleriyle aynı kalıp. *"Sorun varsa organizatör uyarılır ama
/// çalıştırma engellenmez."*
enum MatchingWarning {
  noParticipants(
    'no_participants',
    'Kabul edilmiş katılımcı yok. Başvuruları onaylamadan eşleştirme yapılamaz.',
  ),
  noTables(
    'no_tables',
    'Salon düzeni kurulmamış. Masalar olmadan kimse oturtulamaz.',
  ),
  capacityBelowParticipants(
    'capacity_below_participants',
    'Salon kapasitesi katılımcı sayısından az. Bazı kişiler bazı turlarda '
        'boşta kalacak.',
  ),
  incompleteProfiles(
    'incomplete_profiles',
    'Bazı katılımcıların profili eksik. Eksik profil zayıf eşleşme demek.',
  ),
  requestsStillOpen(
    'requests_still_open',
    'Görüşme talepleri hâlâ açık. Şimdi çalıştırırsan sonradan gelecek '
        'talepler bu plana yansımaz.',
  ),
  unknown('', 'Beklenmeyen bir durum var.');

  const MatchingWarning(this.key, this.message);

  final String key;
  final String message;

  static MatchingWarning fromKey(String key) => MatchingWarning.values.firstWhere(
        (item) => item.key == key,
        // Sunucu ileride yeni bir uyarı eklerse arayüz çökmemeli.
        orElse: () => MatchingWarning.unknown,
      );
}

/// Çalıştırma öncesi kontrol listesi (M6).
class MatchingCheck {
  const MatchingCheck({
    required this.acceptedCount,
    required this.tableCount,
    required this.seatingCapacity,
    required this.requestCount,
    required this.incompleteProfileCount,
    required this.slotCount,
    required this.requestsOpen,
    required this.warnings,
    required this.canRun,
  });

  factory MatchingCheck.fromJson(Map<String, dynamic> json) => MatchingCheck(
        acceptedCount: json['accepted_count'] as int,
        tableCount: json['table_count'] as int,
        seatingCapacity: json['seating_capacity'] as int,
        requestCount: json['request_count'] as int,
        incompleteProfileCount: json['incomplete_profile_count'] as int,
        slotCount: json['slot_count'] as int,
        requestsOpen: json['requests_open'] as bool,
        warnings: (json['warnings'] as List<dynamic>)
            .map((item) => MatchingWarning.fromKey(item as String))
            .toList(),
        canRun: json['can_run'] as bool,
      );

  final int acceptedCount;
  final int tableCount;
  final int seatingCapacity;
  final int requestCount;
  final int incompleteProfileCount;
  final int slotCount;
  final bool requestsOpen;
  final List<MatchingWarning> warnings;

  /// Motor çalışabilir mi. Uyarılar engellemiyor; bu bayrak yalnızca hesabın
  /// hiç anlamlı olmadığı durumu söylüyor.
  final bool canRun;
}

/// Planın kendi durumu (Bölüm 5.2).
///
/// **Hesabın durumundan ayrı.** `JobStatus` motorun nerede olduğunu, bu ise
/// planın yayında olup olmadığını anlatır.
enum PlanStatus {
  draft('draft', 'Taslak'),
  published('published', 'Yayında'),
  archived('archived', 'Arşiv');

  const PlanStatus(this.key, this.label);

  final String key;
  final String label;

  static PlanStatus fromKey(String key) => PlanStatus.values.firstWhere(
        (item) => item.key == key,
        orElse: () => PlanStatus.draft,
      );
}

/// Bir plan versiyonu ve hesabının durumu.
class PlanSummary {
  const PlanSummary({
    required this.id,
    required this.version,
    required this.status,
    required this.jobStatus,
    required this.createdAt,
    required this.seed,
    required this.assignmentCount,
    required this.participantCount,
    required this.unmatched,
    required this.satisfiedRequests,
    required this.totalRequests,
    required this.unmetRequests,
    this.jobError,
    this.publishedAt,
    this.totalMeetings,
    this.minMeetingsPerPerson,
    this.averageTableScore,
    this.runtimeMs,
  });

  factory PlanSummary.fromJson(Map<String, dynamic> json) => PlanSummary(
        id: json['id'] as int,
        version: json['version'] as int,
        status: PlanStatus.fromKey(json['status'] as String),
        jobStatus: JobStatus.fromKey(json['job_status'] as String),
        jobError: json['job_error'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String).toLocal(),
        publishedAt: json['published_at'] == null
            ? null
            : DateTime.parse(json['published_at'] as String).toLocal(),
        seed: json['seed'] as int,
        totalMeetings: json['total_meetings'] as int?,
        minMeetingsPerPerson: json['min_meetings_per_person'] as int?,
        averageTableScore: (json['average_table_score'] as num?)?.toDouble(),
        runtimeMs: json['runtime_ms'] as int?,
        assignmentCount: json['assignment_count'] as int,
        participantCount: json['participant_count'] as int,
        unmatched: (json['unmatched'] as List<dynamic>)
            .map((item) => item as String)
            .toList(),
        satisfiedRequests: json['satisfied_requests'] as int,
        totalRequests: json['total_requests'] as int,
        unmetRequests: (json['unmet_requests'] as List<dynamic>)
            .map((item) => UnmetRequest.fromJson(item as Map<String, dynamic>))
            .toList(),
      );

  final int id;
  final int version;
  final PlanStatus status;

  final JobStatus jobStatus;
  final String? jobError;
  final DateTime createdAt;
  final DateTime? publishedAt;
  final int seed;

  /// Hesap bitene kadar boş — plan satırı iş kuyruğa girer girmez oluşuyor.
  final int? totalMeetings;
  final int? minMeetingsPerPerson;
  final double? averageTableScore;
  final int? runtimeMs;

  final int assignmentCount;
  final int participantCount;

  /// *"Hiç eşleşmemiş kişi var mı, varsa kimler."* (M7)
  ///
  /// Sayı değil isim: organizatör bunları görüp elle yerleştirebilmeli.
  final List<String> unmatched;

  /// *"Karşılanan talep sayısı / toplam talep."* (M7)
  final int satisfiedRequests;
  final int totalRequests;

  /// *"Organizatör plan ekranında karşılanmayan talepleri görür."* (M9)
  /// Karşılanmışlar gelmiyor: yapılacak bir şey kalmamış.
  final List<UnmetRequest> unmetRequests;

  /// Kaçırılan karşılıklı talepler — düzeltilmesi gerekenler.
  List<UnmetRequest> get unmetMutual =>
      unmetRequests.where((item) => item.mutual).toList();

  List<UnmetRequest> get unmetOneWay =>
      unmetRequests.where((item) => !item.mutual).toList();

  bool get isPending => jobStatus.isPending;
  bool get hasResult => jobStatus == JobStatus.done;
  bool get isPublished => status == PlanStatus.published;
}

// --- Plan önizleme ve elle düzeltme (M7) -------------------------------------

/// Masa kalite göstergesi (M7).
///
/// *"Sayı değil, üç seviye."* Sınırlar sunucuda ve **mutlak**: aynı renk her
/// zaman aynı şeyi anlatıyor, kötü bir planda "iyi" masa çıkmıyor. Skor da
/// dönüyor ama organizatöre gösterilmiyor.
enum TableQuality {
  empty('empty', 'Boş'),
  weak('weak', 'Zayıf'),
  fair('fair', 'Orta'),
  good('good', 'İyi');

  const TableQuality(this.key, this.label);

  final String key;
  final String label;

  static TableQuality fromKey(String key) => TableQuality.values.firstWhere(
        (item) => item.key == key,
        orElse: () => TableQuality.empty,
      );
}

/// Bir masada oturan kişi (M7: *"ad, şirket"*).
class SeatedPerson {
  const SeatedPerson({
    required this.assignmentId,
    required this.registrationId,
    required this.isPinned,
    this.fullName,
    this.company,
  });

  factory SeatedPerson.fromJson(Map<String, dynamic> json) => SeatedPerson(
        assignmentId: json['assignment_id'] as int,
        registrationId: json['registration_id'] as int,
        isPinned: json['is_pinned'] as bool,
        fullName: json['full_name'] as String?,
        company: json['company'] as String?,
      );

  final int assignmentId;
  final int registrationId;

  /// *"Sabitlenen atama, motor tekrar çalıştırılsa bile değişmez."* (M7)
  final bool isPinned;

  final String? fullName;
  final String? company;

  String get displayName => fullName ?? 'Adı girilmemiş';
}

/// Slot görünümündeki bir masa (M7).
///
/// Boş masalar da geliyor: organizatör birini boş sandalyeye taşıyabilmeli.
class SeatedTable {
  const SeatedTable({
    required this.tableId,
    required this.number,
    required this.capacity,
    required this.occupants,
    required this.quality,
    required this.score,
    this.label,
  });

  factory SeatedTable.fromJson(Map<String, dynamic> json) => SeatedTable(
        tableId: json['table_id'] as int,
        number: json['number'] as int,
        capacity: json['capacity'] as int,
        occupants: (json['occupants'] as List<dynamic>)
            .map((item) => SeatedPerson.fromJson(item as Map<String, dynamic>))
            .toList(),
        quality: TableQuality.fromKey(json['quality'] as String),
        score: (json['score'] as num).toDouble(),
        label: json['label'] as String?,
      );

  final int tableId;
  final int number;
  final int capacity;
  final List<SeatedPerson> occupants;
  final TableQuality quality;

  /// Hata ayıklama ve sıralama için; organizatöre gösterilmiyor (M8, Bölüm 13).
  final double score;

  final String? label;

  bool get isEmpty => occupants.isEmpty;
  bool get isFull => occupants.length >= capacity;
  String get title => label == null || label!.isEmpty ? 'Masa $number' : label!;
}

/// Bir turun bütün masaları.
class SlotView {
  const SlotView({required this.slotNumber, required this.tables});

  factory SlotView.fromJson(Map<String, dynamic> json) => SlotView(
        slotNumber: json['slot_number'] as int,
        tables: (json['tables'] as List<dynamic>)
            .map((item) => SeatedTable.fromJson(item as Map<String, dynamic>))
            .toList(),
      );

  final int slotNumber;
  final List<SeatedTable> tables;

  int get seatedCount =>
      tables.fold(0, (total, table) => total + table.occupants.length);
}

/// Takas sonrası uyarı (M7).
///
/// Sunucu anahtar gönderiyor, Türkçe cümle burada kuruluyor — kontrol
/// listesindeki uyarılarla aynı kalıp. **Engel değil:** takas zaten yapıldı,
/// *"organizatör uyarıya rağmen devam edebilir — ama ne yaptığını bilerek
/// yapar."*
class SwapWarning {
  const SwapWarning({
    required this.key,
    required this.people,
    this.tableNumber,
    this.slotNumber,
  });

  factory SwapWarning.fromJson(Map<String, dynamic> json) => SwapWarning(
        key: json['key'] as String,
        people: (json['people'] as List<dynamic>)
            .map((item) => item as String)
            .toList(),
        tableNumber: json['table_number'] as int?,
        slotNumber: json['slot_number'] as int?,
      );

  final String key;
  final List<String> people;
  final int? tableNumber;
  final int? slotNumber;

  /// Cümlenin başındaki masa etiketi.
  ///
  /// **Sayıya ek getirilmiyor.** Türkçede ek sayının okunuşuna göre değişiyor:
  /// "1'in" ama "2'nin", "3'ün", "4'te", "6'da"... Tabloya dökmek yerine cümle
  /// eki gerektirmeyecek şekilde kuruldu. Tarayıcıda "Masa 2'ın" ve
  /// "Masa 4'da" görüldükten sonra alınan karar.
  String get _table => tableNumber == null ? 'Masa' : 'Masa $tableNumber';

  /// Uyarının Türkçe karşılığı.
  ///
  /// Sunucu ileride yeni bir anahtar eklerse arayüz çökmemeli; tanınmayan
  /// anahtar genel bir cümleye düşüyor.
  String get message => switch (key) {
        'same_company' =>
          '$_table — aynı şirketten iki kişi var: ${people.join(', ')}. '
              'İkisi burada birbirine yeni bir şey katmaz.',
        'over_capacity' =>
          '$_table — kapasitenin üzerinde: ${people.length} kişi oturuyor.',
        'lonely_table' => '$_table — tek kişi kaldı: ${people.join(', ')}. '
            'Yarım saat tek başına oturur.',
        // Burada ek sorunu yok: "turda" eki sayıya değil "tur" kelimesine
        // geliyor ve her sayı için aynı.
        'repeat_pair' =>
          '${people.join(' ile ')} ${slotNumber ?? '?'}. turda zaten '
              'görüşüyor. İkinci görüşme kimseye yeni bir şey katmaz.',
        'quality_dropped' =>
          '$_table — eşleşme kalitesi eşiğin altına düştü.',
        _ => '$_table — beklenmeyen bir durum var.',
      };
}

/// Takasın sonucu: yeni slot görünümü ve uyarılar.
///
/// İkisi birlikte dönüyor ki istemci ikinci bir istek atmasın.
class SwapResult {
  const SwapResult({required this.slot, required this.warnings});

  factory SwapResult.fromJson(Map<String, dynamic> json) => SwapResult(
        slot: SlotView.fromJson(json['slot'] as Map<String, dynamic>),
        warnings: (json['warnings'] as List<dynamic>)
            .map((item) => SwapWarning.fromJson(item as Map<String, dynamic>))
            .toList(),
      );

  final SlotView slot;
  final List<SwapWarning> warnings;
}

// --- Başvuru (M3) ------------------------------------------------------------

/// Başvurunun durumu.
///
/// *"Başvuru durumları kullanıcıya net gösterilir: başvurmadı / beklemede /
/// kabul edildi / reddedildi."* "Başvurmadı" bir durum değil, başvurunun
/// yokluğu — sunucu geri çekilmiş başvuruyu da yok sayıp `null` döndürüyor.
enum RegistrationStatus {
  pending('pending', 'Beklemede'),
  accepted('accepted', 'Kabul edildi'),
  rejected('rejected', 'Reddedildi'),
  cancelled('cancelled', 'Geri çekildi');

  const RegistrationStatus(this.key, this.label);

  final String key;
  final String label;

  static RegistrationStatus fromKey(String key) => RegistrationStatus.values.firstWhere(
        (item) => item.key == key,
        orElse: () => RegistrationStatus.pending,
      );
}

/// Oturumdaki kullanıcının bir etkinlikteki başvurusu.
class MyRegistration {
  const MyRegistration({
    required this.id,
    required this.status,
    required this.appliedAt,
  });

  factory MyRegistration.fromJson(Map<String, dynamic> json) => MyRegistration(
        id: json['id'] as int,
        status: RegistrationStatus.fromKey(json['status'] as String),
        appliedAt: DateTime.parse(json['applied_at'] as String).toLocal(),
      );

  final int id;
  final RegistrationStatus status;
  final DateTime appliedAt;
}

/// Keşif listesindeki kart (M3).
///
/// *"Her kart: ad, tarih, yer, kalan kontenjan, başvuru durumu."*
class DiscoverEvent {
  const DiscoverEvent({
    required this.id,
    required this.name,
    required this.startsAt,
    required this.slotCount,
    required this.capacity,
    required this.remainingCapacity,
    required this.isOpen,
    this.coverUrl,
    this.venueName,
    this.registrationDeadline,
    this.myRegistration,
  });

  factory DiscoverEvent.fromJson(Map<String, dynamic> json) => DiscoverEvent(
        id: json['id'] as int,
        name: json['name'] as String,
        coverUrl: json['cover_url'] as String?,
        startsAt: DateTime.parse(json['starts_at'] as String).toLocal(),
        venueName: json['venue_name'] as String?,
        slotCount: json['slot_count'] as int,
        capacity: json['capacity'] as int,
        remainingCapacity: json['remaining_capacity'] as int,
        registrationDeadline: json['registration_deadline'] == null
            ? null
            : DateTime.parse(json['registration_deadline'] as String).toLocal(),
        isOpen: json['is_open'] as bool,
        myRegistration: json['my_registration'] == null
            ? null
            : MyRegistration.fromJson(json['my_registration'] as Map<String, dynamic>),
      );

  final int id;
  final String name;
  final String? coverUrl;
  final DateTime startsAt;
  final String? venueName;
  final int slotCount;

  final int capacity;
  final int remainingCapacity;
  final DateTime? registrationDeadline;

  /// Başvuru şu anda mümkün mü — kontenjan, son tarih ve etkinlik durumu
  /// birlikte. Arayüz düğmeyi buna bakarak kapatıyor; asıl kapı sunucuda.
  final bool isOpen;

  final MyRegistration? myRegistration;

  bool get isFull => remainingCapacity == 0;

  /// Başvurulamıyorsa sebebi — kart üstünde yazılıyor.
  ///
  /// Kapalı bir etkinlik listeden düşmüyor; kullanıcı neden başvuramadığını
  /// görmeli, "dün buradaydı" diye aramamalı.
  String? get closedReason {
    if (isOpen || myRegistration != null) return null;
    if (isFull) return 'Kontenjan doldu';
    final deadline = registrationDeadline;
    if (deadline != null && DateTime.now().isAfter(deadline)) {
      return 'Son başvuru tarihi geçti';
    }
    return 'Başvurular kapalı';
  }
}

/// Katılımcının gördüğü etkinlik detayı (M3).
///
/// Organizatörün gördüğü `EventDetail`'den az alan taşıyor: otomatik onay,
/// talep kotası ve kapasite özeti buraya girmiyor (Bölüm 7).
class PublicEvent {
  const PublicEvent({
    required this.id,
    required this.name,
    required this.startsAt,
    required this.slotDurationMinutes,
    required this.breakDurationMinutes,
    required this.slotCount,
    required this.schedule,
    required this.endsAt,
    required this.totalMinutes,
    required this.capacity,
    required this.remainingCapacity,
    required this.acceptedCount,
    required this.isOpen,
    this.description,
    this.coverUrl,
    this.venueName,
    this.address,
    this.registrationDeadline,
    this.myRegistration,
  });

  factory PublicEvent.fromJson(Map<String, dynamic> json) => PublicEvent(
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
        schedule: (json['schedule'] as List<dynamic>)
            .map((item) => SlotTiming.fromJson(item as Map<String, dynamic>))
            .toList(),
        endsAt: DateTime.parse(json['ends_at'] as String).toLocal(),
        totalMinutes: json['total_minutes'] as int,
        capacity: json['capacity'] as int,
        remainingCapacity: json['remaining_capacity'] as int,
        acceptedCount: json['accepted_count'] as int,
        registrationDeadline: json['registration_deadline'] == null
            ? null
            : DateTime.parse(json['registration_deadline'] as String).toLocal(),
        isOpen: json['is_open'] as bool,
        myRegistration: json['my_registration'] == null
            ? null
            : MyRegistration.fromJson(json['my_registration'] as Map<String, dynamic>),
      );

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

  /// Sunucunun hesapladığı program — *"slot saatleri hesaplanmış halde"* (M3).
  final List<SlotTiming> schedule;
  final DateTime endsAt;
  final int totalMinutes;

  final int capacity;
  final int remainingCapacity;

  /// *"Kaç kişi katılıyor"* — kabul edilen başvuru sayısı.
  final int acceptedCount;

  final DateTime? registrationDeadline;
  final bool isOpen;
  final MyRegistration? myRegistration;
}

/// Başvuranın özeti — organizatörün onay ekranı için.
class Applicant {
  const Applicant({this.fullName, this.title, this.photoUrl, this.company, this.sector});

  factory Applicant.fromJson(Map<String, dynamic> json) => Applicant(
        fullName: json['full_name'] as String?,
        title: json['title'] as String?,
        photoUrl: json['photo_url'] as String?,
        company: json['company'] == null
            ? null
            : Company.fromJson(json['company'] as Map<String, dynamic>),
        sector: json['sector'] == null
            ? null
            : Sector.fromJson(json['sector'] as Map<String, dynamic>),
      );

  final String? fullName;
  final String? title;
  final String? photoUrl;
  final Company? company;
  final Sector? sector;

  String get displayName => (fullName?.trim().isNotEmpty ?? false) ? fullName! : 'Adı girilmemiş';

  /// Unvan ve şirket tek satırda; ikisi de yoksa boş.
  String get subtitle =>
      [title, company?.name].where((part) => part != null && part.isNotEmpty).join(' · ');
}

/// Organizatörün başvuru listesindeki bir satır.
class EventRegistration {
  const EventRegistration({
    required this.id,
    required this.status,
    required this.appliedAt,
    required this.applicant,
  });

  factory EventRegistration.fromJson(Map<String, dynamic> json) => EventRegistration(
        id: json['id'] as int,
        status: RegistrationStatus.fromKey(json['status'] as String),
        appliedAt: DateTime.parse(json['applied_at'] as String).toLocal(),
        applicant: Applicant.fromJson(json['applicant'] as Map<String, dynamic>),
      );

  final int id;
  final RegistrationStatus status;
  final DateTime appliedAt;
  final Applicant applicant;
}

/// Başvuru listesi ve sayılar.
///
/// Sayılar listeyle birlikte geliyor: organizatör süzgeci değiştirdiğinde
/// "kaç bekleyen kaldı" bilgisi kaybolmasın.
class RegistrationSummary {
  const RegistrationSummary({
    required this.registrations,
    required this.pendingCount,
    required this.acceptedCount,
    required this.rejectedCount,
    required this.capacity,
    required this.remainingCapacity,
  });

  factory RegistrationSummary.fromJson(Map<String, dynamic> json) => RegistrationSummary(
        registrations: (json['registrations'] as List<dynamic>)
            .map((item) => EventRegistration.fromJson(item as Map<String, dynamic>))
            .toList(),
        pendingCount: json['pending_count'] as int,
        acceptedCount: json['accepted_count'] as int,
        rejectedCount: json['rejected_count'] as int,
        capacity: json['capacity'] as int,
        remainingCapacity: json['remaining_capacity'] as int,
      );

  final List<EventRegistration> registrations;
  final int pendingCount;
  final int acceptedCount;
  final int rejectedCount;
  final int capacity;
  final int remainingCapacity;

  bool get isFull => remainingCapacity == 0;
}

// --- Katılımcı görünümü (M8) --------------------------------------------------

/// Bir masa arkadaşıyla neden eşleştiğini anlatan tek bir gerekçe.
///
/// Sunucu anahtar ve adları gönderiyor, Türkçe cümle burada kuruluyor —
/// Aşama 6-7-8'deki kalıp. **Sayı yok:** M8 açıkça yasaklıyor, *"Uyum: %62
/// gibi bir ifade kullanılmaz. Sayı gören insan not almış gibi hisseder."*
class MatchReason {
  const MatchReason({required this.kind, required this.values});

  factory MatchReason.fromJson(Map<String, dynamic> json) => MatchReason(
        kind: json['kind'] as String,
        values:
            (json['values'] as List<dynamic>).map((item) => item as String).toList(),
      );

  final String kind;
  final List<String> values;

  /// Cümleye giren etiketler.
  ///
  /// Üç etiket birden yazılırsa cümle okunmaz uzunlukta oluyor. İlk ikisi
  /// yazılıp gerisi sayıya dönüşüyor.
  ///
  /// **Üç ve fazlasında bağlaç değil virgül** kullanılıyor: etiket adının
  /// kendisi "ve" içerebiliyor ("Veri analitiği ve raporlama") ve cümlede
  /// "... raporlama ve 1 alan daha" diye çift bağlaç çıkıyordu. Tarayıcıda
  /// görüldü.
  String get _listed {
    if (values.length <= 2) return values.join(' ve ');
    return '${values.take(2).join(', ')}, ${values.length - 2} alan daha';
  }

  /// Tek etiket "bunu", birden fazlası "bunları".
  String get _it => values.length > 1 ? 'bunları' : 'bunu';

  /// Gerekçenin Türkçe karşılığı.
  ///
  /// Sunucu ileride yeni bir anahtar eklerse arayüz çökmemeli; tanınmayan
  /// anahtar boş dönüyor ve o gerekçe hiç gösterilmiyor — uydurma bir cümle
  /// yazmaktansa susmak doğru.
  String get sentence => switch (kind) {
        'they_offer' => 'Kendisi $_listed sunuyor, siz $_it arıyorsunuz.',
        'you_offer' => 'Siz $_listed sunuyorsunuz, kendisi $_it arıyor.',
        'shared_category' => 'İkiniz de $_listed alanındasınız.',
        'same_sector' => 'İkiniz de $_listed sektöründesiniz.',
        'same_city' => 'İkiniz de $_listed şehrindesiniz.',
        'mutual_request' => 'İkiniz de görüşmek istemiştiniz.',
        _ => '',
      };
}

/// Masa arkadaşı kartı (M8: *"fotoğraf, ad, unvan, şirket"*).
class Tablemate {
  const Tablemate({
    required this.registrationId,
    required this.reasons,
    this.fullName,
    this.title,
    this.company,
    this.photoUrl,
  });

  factory Tablemate.fromJson(Map<String, dynamic> json) => Tablemate(
        registrationId: json['registration_id'] as int,
        reasons: (json['reasons'] as List<dynamic>)
            .map((item) => MatchReason.fromJson(item as Map<String, dynamic>))
            .toList(),
        fullName: json['full_name'] as String?,
        title: json['title'] as String?,
        company: json['company'] as String?,
        photoUrl: json['photo_url'] as String?,
      );

  final int registrationId;
  final List<MatchReason> reasons;
  final String? fullName;
  final String? title;
  final String? company;
  final String? photoUrl;

  String get displayName => fullName ?? 'Adı girilmemiş';

  /// Gösterilebilir gerekçeler — tanınmayan anahtarlar eleniyor.
  List<String> get sentences =>
      reasons.map((reason) => reason.sentence).where((text) => text.isNotEmpty).toList();
}

/// Katılımcının bir turu.
class MySlot {
  const MySlot({
    required this.slotNumber,
    required this.startsAt,
    required this.endsAt,
    required this.tablemates,
    this.tableId,
    this.tableNumber,
    this.tableLabel,
  });

  factory MySlot.fromJson(Map<String, dynamic> json) => MySlot(
        slotNumber: json['slot_number'] as int,
        startsAt: DateTime.parse(json['starts_at'] as String).toLocal(),
        endsAt: DateTime.parse(json['ends_at'] as String).toLocal(),
        tablemates: (json['tablemates'] as List<dynamic>)
            .map((item) => Tablemate.fromJson(item as Map<String, dynamic>))
            .toList(),
        tableId: json['table_id'] as int?,
        tableNumber: json['table_number'] as int?,
        tableLabel: json['table_label'] as String?,
      );

  final int slotNumber;
  final DateTime startsAt;
  final DateTime endsAt;
  final List<Tablemate> tablemates;
  final int? tableId;
  final int? tableNumber;
  final String? tableLabel;

  /// M8: *"Bir slotta eşleşmemişse o slot 'Bu turda serbestsin' olarak
  /// gösterilir. Boş bırakılmaz, açıklama yazılır."*
  bool get isFree => tableNumber == null;

  String get tableTitle {
    if (tableNumber == null) return 'Serbest';
    final label = tableLabel;
    return label == null || label.isEmpty ? 'Masa $tableNumber' : label;
  }
}

/// Katılımcının gördüğü planın tamamı.
class MyPlan {
  const MyPlan({
    required this.isPublished,
    required this.slots,
    this.planVersion,
  });

  factory MyPlan.fromJson(Map<String, dynamic> json) => MyPlan(
        isPublished: json['is_published'] as bool,
        planVersion: json['plan_version'] as int?,
        slots: (json['slots'] as List<dynamic>)
            .map((item) => MySlot.fromJson(item as Map<String, dynamic>))
            .toList(),
      );

  final bool isPublished;
  final int? planVersion;
  final List<MySlot> slots;

  /// Kaç turda birileriyle oturuyor.
  int get seatedCount => slots.where((slot) => !slot.isFree).length;

  int get meetingCount =>
      slots.fold(0, (total, slot) => total + slot.tablemates.length);
}

/// Krokideki bir masa. **Kimin oturduğu yok.**
class VenueTable {
  const VenueTable({
    required this.id,
    required this.number,
    this.label,
    this.gridX,
    this.gridY,
  });

  factory VenueTable.fromJson(Map<String, dynamic> json) => VenueTable(
        id: json['id'] as int,
        number: json['number'] as int,
        label: json['label'] as String?,
        gridX: json['grid_x'] as int?,
        gridY: json['grid_y'] as int?,
      );

  final int id;
  final int number;
  final String? label;
  final int? gridX;
  final int? gridY;

  bool get isPlaced => gridX != null && gridY != null;
}

/// Salon krokisi (M8).
///
/// Otomatik düzende ızgara yok — kroki çizilemez, yalnızca masa numarası
/// gösterilir.
class Venue {
  const Venue({
    required this.mode,
    required this.tables,
    required this.areas,
    this.gridWidth,
    this.gridHeight,
  });

  factory Venue.fromJson(Map<String, dynamic> json) => Venue(
        mode: LayoutMode.fromKey(json['mode'] as String),
        tables: (json['tables'] as List<dynamic>)
            .map((item) => VenueTable.fromJson(item as Map<String, dynamic>))
            .toList(),
        areas: (json['areas'] as List<dynamic>)
            .map((item) => LayoutArea.fromJson(item as Map<String, dynamic>))
            .toList(),
        gridWidth: json['grid_width'] as int?,
        gridHeight: json['grid_height'] as int?,
      );

  final LayoutMode mode;
  final List<VenueTable> tables;
  final List<LayoutArea> areas;
  final int? gridWidth;
  final int? gridHeight;

  /// Kroki çizilebilir mi: ızgara var ve en az bir masa yerleştirilmiş.
  bool get hasSketch =>
      gridWidth != null && gridHeight != null && tables.any((table) => table.isPlaced);
}

/// Masa arkadaşının tam profili (M8).
class TablemateProfile {
  const TablemateProfile({
    required this.registrationId,
    required this.offeredTags,
    required this.soughtTags,
    this.fullName,
    this.title,
    this.city,
    this.bio,
    this.photoUrl,
    this.website,
    this.linkedinUrl,
    this.company,
    this.sector,
  });

  factory TablemateProfile.fromJson(Map<String, dynamic> json) => TablemateProfile(
        registrationId: json['registration_id'] as int,
        offeredTags: (json['offered_tags'] as List<dynamic>)
            .map((item) => Tag.fromJson(item as Map<String, dynamic>))
            .toList(),
        soughtTags: (json['sought_tags'] as List<dynamic>)
            .map((item) => Tag.fromJson(item as Map<String, dynamic>))
            .toList(),
        fullName: json['full_name'] as String?,
        title: json['title'] as String?,
        city: json['city'] as String?,
        bio: json['bio'] as String?,
        photoUrl: json['photo_url'] as String?,
        website: json['website'] as String?,
        linkedinUrl: json['linkedin_url'] as String?,
        company: json['company'] == null
            ? null
            : Company.fromJson(json['company'] as Map<String, dynamic>),
        sector: json['sector'] == null
            ? null
            : Sector.fromJson(json['sector'] as Map<String, dynamic>),
      );

  final int registrationId;
  final List<Tag> offeredTags;
  final List<Tag> soughtTags;
  final String? fullName;
  final String? title;
  final String? city;
  final String? bio;
  final String? photoUrl;
  final String? website;
  final String? linkedinUrl;
  final Company? company;
  final Sector? sector;

  String get displayName => fullName ?? 'Adı girilmemiş';
}

// --- Görüşme talepleri (M9) ---------------------------------------------------

/// Katılımcı listesindeki bir satır.
///
/// M9: *"Listede ad, unvan, şirket, sektör görünür."* Tam profil burada yok —
/// o yalnızca aynı masaya düşen kişiler için (Bölüm 7).
class ParticipantRow {
  const ParticipantRow({
    required this.registrationId,
    this.fullName,
    this.title,
    this.company,
    this.sector,
    this.photoUrl,
    this.myRequestId,
  });

  factory ParticipantRow.fromJson(Map<String, dynamic> json) => ParticipantRow(
        registrationId: json['registration_id'] as int,
        fullName: json['full_name'] as String?,
        title: json['title'] as String?,
        company: json['company'] as String?,
        sector: json['sector'] as String?,
        photoUrl: json['photo_url'] as String?,
        myRequestId: json['my_request_id'] as int?,
      );

  final int registrationId;
  final String? fullName;
  final String? title;
  final String? company;
  final String? sector;
  final String? photoUrl;

  /// Doluysa **ben** bu kişiye talep göndermişim; geri çekmek için kimlik.
  ///
  /// Karşı tarafın bana talep gönderip göndermediği burada yok ve sunucuda da
  /// yok — M9: *"talep gönderildiği kişiye bildirilmez."*
  final int? myRequestId;

  bool get requested => myRequestId != null;

  String get displayName => fullName ?? 'Adı girilmemiş';
}

/// Katılımcı listesi ve talep hakkım.
class ParticipantList {
  const ParticipantList({
    required this.participants,
    required this.requestQuota,
    required this.requestsUsed,
    required this.requestsRemaining,
    required this.requestsOpen,
  });

  factory ParticipantList.fromJson(Map<String, dynamic> json) => ParticipantList(
        participants: (json['participants'] as List<dynamic>)
            .map((item) => ParticipantRow.fromJson(item as Map<String, dynamic>))
            .toList(),
        requestQuota: json['request_quota'] as int,
        requestsUsed: json['requests_used'] as int,
        requestsRemaining: json['requests_remaining'] as int,
        requestsOpen: json['requests_open'] as bool,
      );

  final List<ParticipantRow> participants;
  final int requestQuota;
  final int requestsUsed;
  final int requestsRemaining;

  /// *"Talepler bir zamanda kapanır."* Kapalıysa düğmeler kapalı; asıl kapı
  /// sunucuda.
  final bool requestsOpen;

  bool get exhausted => requestsRemaining <= 0;

  /// Kalan hakkın Türkçe karşılığı.
  String get quotaSentence {
    if (requestQuota == 0) return 'Bu etkinlikte görüşme talebi gönderilemiyor.';
    if (requestsRemaining == 0) {
      return 'Talep hakkın doldu. Birini geri çekersen yenisini gönderebilirsin.';
    }
    return '$requestQuota talep hakkından $requestsRemaining tanesi kaldı.';
  }
}

/// Karşılanmayan bir talep — **organizatör** görünümü (M9).
class UnmetRequest {
  const UnmetRequest({
    required this.requesterRegistrationId,
    required this.targetRegistrationId,
    required this.requesterName,
    required this.targetName,
    required this.mutual,
    this.fixableSlot,
  });

  factory UnmetRequest.fromJson(Map<String, dynamic> json) => UnmetRequest(
        requesterRegistrationId: json['requester_registration_id'] as int,
        targetRegistrationId: json['target_registration_id'] as int,
        requesterName: json['requester_name'] as String,
        targetName: json['target_name'] as String,
        mutual: json['mutual'] as bool,
        fixableSlot: json['fixable_slot'] as int?,
      );

  final int requesterRegistrationId;
  final int targetRegistrationId;
  final String requesterName;
  final String targetName;

  /// *"Neredeyse kesin eşleşme."* Karşılanmadıysa gerçek bir kusur.
  final bool mutual;

  /// İki tarafın da oturduğu ama farklı masalara düştüğü ilk tur — takasla
  /// düzeltilebilecek yer. Biri hiç oturmuyorsa boş.
  final int? fixableSlot;

  /// Karşılıklıda çift yönlü ok, tek taraflıda tek yönlü.
  String get pair => mutual
      ? '$requesterName ↔ $targetName'
      : '$requesterName → $targetName';
}
