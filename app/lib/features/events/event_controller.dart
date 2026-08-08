import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/auth_controller.dart';
import 'event_repository.dart';
import 'models.dart';

final eventRepositoryProvider = Provider<EventRepository>((ref) {
  return EventRepository(ref.watch(apiClientProvider));
});

/// Organizatörün etkinlik listesi.
final myEventsProvider = FutureProvider<List<EventSummary>>((ref) {
  return ref.watch(eventRepositoryProvider).listMine();
});

/// Tek bir etkinliğin ayrıntısı.
///
/// Program ve kapasite özeti sunucudan geliyor; adımlar kendi hesaplarını
/// yapmıyor — anlık önizleme hariç (M4, kaydetmeden önce gösteriliyor).
final eventDetailProvider =
    FutureProvider.family<EventDetail, int>((ref, eventId) {
  return ref.watch(eventRepositoryProvider).load(eventId);
});

/// Etkinliğin salon düzeni; henüz kurulmadıysa `null`.
///
/// Ayrı sağlayıcı: düzen yalnızca son adımda ve editörde gerekiyor, her
/// etkinlik yüklemesinde çekmek gereksiz olurdu.
///
/// Etkinliğin `hasLayout` alanına bakılmıyor: o alan "düzen var **ve** masası
/// var" demek (kayıt açma kapısı için). Manuel modda ızgara kurulmuş ama henüz
/// masa konmamış olabilir — editörün o düzeni görmesi gerekiyor.
final eventLayoutProvider =
    FutureProvider.family<EventLayout?, int>((ref, eventId) async {
  try {
    return await ref.watch(eventRepositoryProvider).loadLayout(eventId);
  } on ApiException catch (error) {
    if (error.statusCode == 404) return null;
    rethrow;
  }
});

/// Başvurulabilecek yaklaşan etkinlikler (M3).
final discoverEventsProvider = FutureProvider<List<DiscoverEvent>>((ref) {
  return ref.watch(eventRepositoryProvider).discover();
});

/// Katılımcının gördüğü etkinlik detayı.
final publicEventProvider =
    FutureProvider.family<PublicEvent, int>((ref, eventId) {
  return ref.watch(eventRepositoryProvider).loadPublic(eventId);
});

/// Organizatörün başvuru listesi; süzgeç sağlayıcının argümanında.
final eventRegistrationsProvider =
    FutureProvider.family<RegistrationSummary, RegistrationQuery>((ref, query) {
  return ref
      .watch(eventRepositoryProvider)
      .loadRegistrations(query.eventId, status: query.status);
});

/// Başvuru listesinin sorgusu.
///
/// `family` argümanı olarak kullanıldığı için değer eşitliği şart: aynı süzgeç
/// aynı önbelleğe düşmeli, her yeniden çizimde yeni istek atılmamalı.
class RegistrationQuery {
  const RegistrationQuery(this.eventId, [this.status]);

  final int eventId;
  final RegistrationStatus? status;

  @override
  bool operator ==(Object other) =>
      other is RegistrationQuery && other.eventId == eventId && other.status == status;

  @override
  int get hashCode => Object.hash(eventId, status);
}

/// Çalıştırma öncesi kontrol listesi (M6).
final matchingCheckProvider =
    FutureProvider.family<MatchingCheck, int>((ref, eventId) {
  return ref.watch(eventRepositoryProvider).loadMatchingCheck(eventId);
});

/// Etkinliğin plan versiyonları, yenisi önce.
final eventPlansProvider =
    FutureProvider.family<List<PlanSummary>, int>((ref, eventId) {
  return ref.watch(eventRepositoryProvider).loadPlans(eventId);
});

/// Katılımcının kendi planı (M8).
///
/// Plan yayında değilse boş bir sonuç dönüyor, hata değil: *"Oturma planınız
/// henüz hazırlanıyor"* bir bekleme durumu.
final myPlanProvider = FutureProvider.family<MyPlan, int>((ref, eventId) {
  return ref.watch(eventRepositoryProvider).loadMyPlan(eventId);
});

/// Salon krokisi — kimin oturduğu yok. Düzen kurulmamışsa `null`.
///
/// Ayrı sağlayıcı: kroki yalnızca tur detayında gerekiyor, plan her
/// yüklendiğinde çekmek gereksiz olurdu.
final venueProvider = FutureProvider.family<Venue?, int>((ref, eventId) async {
  try {
    return await ref.watch(eventRepositoryProvider).loadVenue(eventId);
  } on ApiException catch (error) {
    if (error.statusCode == 404) return null;
    rethrow;
  }
});

/// Masa arkadaşının profili. Masa arkadaşı değilse sunucu 404 veriyor.
final tablemateProvider =
    FutureProvider.family<TablemateProfile, TablemateQuery>((ref, query) {
  return ref
      .watch(eventRepositoryProvider)
      .loadTablemate(query.eventId, query.registrationId);
});

/// Masa arkadaşı sağlayıcısının argümanı.
class TablemateQuery {
  const TablemateQuery(this.eventId, this.registrationId);

  final int eventId;
  final int registrationId;

  @override
  bool operator ==(Object other) =>
      other is TablemateQuery &&
      other.eventId == eventId &&
      other.registrationId == registrationId;

  @override
  int get hashCode => Object.hash(eventId, registrationId);
}

/// Katılımcının kendi giriş kodu (M10).
final myQrProvider = FutureProvider.family<MyQrCode, int>((ref, eventId) {
  return ref.watch(eventRepositoryProvider).loadMyQr(eventId);
});

/// Check-in listesi ve sayaç (M10, organizatör).
final attendanceProvider =
    FutureProvider.family<AttendanceBoard, AttendanceQuery>((ref, query) {
  return ref
      .watch(eventRepositoryProvider)
      .loadAttendance(query.eventId, search: query.search);
});

/// Check-in listesinin sorgusu.
class AttendanceQuery {
  const AttendanceQuery(this.eventId, {this.search});

  final int eventId;
  final String? search;

  @override
  bool operator ==(Object other) =>
      other is AttendanceQuery && other.eventId == eventId && other.search == search;

  @override
  int get hashCode => Object.hash(eventId, search);
}

/// İki plan arasında kimin yeri değişti (M10).
final planChangesProvider =
    FutureProvider.family<PlanChanges, PlanQuery>((ref, query) {
  return ref
      .watch(eventRepositoryProvider)
      .loadPlanChanges(query.eventId, query.planId);
});

/// Etkinliğin katılımcıları ve kalan talep hakkım (M9).
///
/// Süzgeç argümanda: her süzgeç ayrı bir önbellek. Talep gönderildiğinde
/// hepsi tazeleniyor (`RequestActions`), yoksa başka bir süzgeçte satır eski
/// hâlinde kalırdı — `eventRegistrationsProvider` ile aynı tuzak.
final participantsProvider =
    FutureProvider.family<ParticipantList, ParticipantQuery>((ref, query) {
  return ref.watch(eventRepositoryProvider).loadParticipants(
        query.eventId,
        search: query.search,
        sectorId: query.sectorId,
      );
});

/// Katılımcı listesinin sorgusu.
class ParticipantQuery {
  const ParticipantQuery(this.eventId, {this.search, this.sectorId});

  final int eventId;
  final String? search;
  final int? sectorId;

  @override
  bool operator ==(Object other) =>
      other is ParticipantQuery &&
      other.eventId == eventId &&
      other.search == search &&
      other.sectorId == sectorId;

  @override
  int get hashCode => Object.hash(eventId, search, sectorId);
}

/// Tek bir plan versiyonu — önizleme ekranının özet paneli (M7).
final planProvider =
    FutureProvider.family<PlanSummary, PlanQuery>((ref, query) {
  return ref.watch(eventRepositoryProvider).loadPlan(query.eventId, query.planId);
});

/// Bir turun masaları ve oturanları (M7).
final planSlotProvider =
    FutureProvider.family<SlotView, SlotQuery>((ref, query) {
  return ref
      .watch(eventRepositoryProvider)
      .loadSlot(query.eventId, query.planId, query.slotNumber);
});

/// Plan sağlayıcısının argümanı.
///
/// `family` argümanı olduğu için değer eşitliği şart: aynı plan aynı önbelleğe
/// düşmeli, her yeniden çizimde yeni istek atılmamalı.
class PlanQuery {
  const PlanQuery(this.eventId, this.planId);

  final int eventId;
  final int planId;

  @override
  bool operator ==(Object other) =>
      other is PlanQuery && other.eventId == eventId && other.planId == planId;

  @override
  int get hashCode => Object.hash(eventId, planId);
}

/// Slot sağlayıcısının argümanı.
class SlotQuery {
  const SlotQuery(this.eventId, this.planId, this.slotNumber);

  final int eventId;
  final int planId;
  final int slotNumber;

  @override
  bool operator ==(Object other) =>
      other is SlotQuery &&
      other.eventId == eventId &&
      other.planId == planId &&
      other.slotNumber == slotNumber;

  @override
  int get hashCode => Object.hash(eventId, planId, slotNumber);
}

/// Etkinliği değiştiren işlemler.
///
/// Depoyu sarmalayıp değişiklikten sonra ilgili sağlayıcıları tazeliyor.
/// Hatalar **fırlatılıyor**: adım ekranı onu kendi içinde gösteriyor.
/// Paylaşılan duruma yazılsaydı sihirbaz komple hata ekranına düşer, girilen
/// veri kaybolurdu.
class EventActions {
  const EventActions(this._ref, this.eventId);

  final Ref _ref;
  final int eventId;

  EventRepository get _repository => _ref.read(eventRepositoryProvider);

  Future<void> save(Map<String, dynamic> changes) async {
    await _repository.update(eventId, changes);
    await _refreshDetail();
  }

  Future<void> uploadCover({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    await _repository.uploadCover(
      eventId: eventId,
      bytes: bytes,
      filename: filename,
      contentType: contentType,
    );
    await _refreshDetail();
  }

  Future<void> removeCover() async {
    await _repository.removeCover(eventId);
    await _refreshDetail();
  }

  /// Otomatik salon düzenini kurar (M5).
  ///
  /// Düzen değişince kapasite özeti ve "kayıtlar açılabilir mi" bilgisi de
  /// değişiyor; ikisi de etkinlik yanıtında, o yüzden ikisi de tazeleniyor.
  Future<void> buildAutoLayout({
    required TableKind kind,
    required int tableCount,
    int? seatCount,
    int? minPeople,
    int? maxPeople,
  }) async {
    await _repository.buildAutoLayout(
      eventId: eventId,
      kind: kind,
      tableCount: tableCount,
      seatCount: seatCount,
      minPeople: minPeople,
      maxPeople: maxPeople,
    );
    await _refreshDetail();
    _ref.invalidate(eventLayoutProvider(eventId));
  }

  /// Manuel salon düzenine geçirir veya ızgarayı yeniden boyutlandırır (M5).
  ///
  /// Otomatik moddaki masalar korunuyor; sunucu onları ızgaraya diziyor.
  Future<EventLayout> buildManualLayout({
    required int gridWidth,
    required int gridHeight,
  }) async {
    final layout = await _repository.buildManualLayout(
      eventId: eventId,
      gridWidth: gridWidth,
      gridHeight: gridHeight,
    );
    await _refreshDetail();
    _ref.invalidate(eventLayoutProvider(eventId));
    return layout;
  }

  /// Editörden çıkarken etkinliği ve düzeni tazeler.
  ///
  /// Editör masa ekleyip silmiş olabilir; kapasite özeti ve "kayıtlar
  /// açılabilir mi" bilgisi etkinlik yanıtında duruyor.
  Future<void> refreshLayout() async {
    _ref.invalidate(eventLayoutProvider(eventId));
    await _refreshDetail();
  }

  Future<void> openRegistration() async {
    await _repository.openRegistration(eventId);
    await _refreshDetail();
    await refreshList();
    _ref.invalidate(discoverEventsProvider);
  }

  /// Etkinlik listesini tazeler ve yeni verinin gelmesini bekler.
  ///
  /// Liste, kart üstünde adı, tur sayısını ve durum rozetini gösteriyor;
  /// sihirbazda değişen her şey oraya yansımalı. Keşfet listesi de yenilenir.
  Future<void> refreshList() async {
    _ref.invalidate(myEventsProvider);
    _ref.invalidate(discoverEventsProvider);
    await _ref.read(myEventsProvider.future);
  }

  /// Değişikliği bekleyerek uygular.
  ///
  /// `invalidate` tek başına yeterli değil: yeniden hesaplama asenkron
  /// başlıyor, çağıran hemen gezinirse ekran eski veriyle açılıyor.
  /// `read(...future)` yeni değeri bekletiyor.
  Future<void> _refreshDetail() async {
    _ref.invalidate(eventDetailProvider(eventId));
    await _ref.read(eventDetailProvider(eventId).future);
  }
}

final eventActionsProvider = Provider.family<EventActions, int>((ref, eventId) {
  return EventActions(ref, eventId);
});

/// Başvuru işlemleri (M3).
///
/// `EventActions`'tan ayrı: o organizatörün sihirbazına hizmet ediyor, bu
/// katılımcının ve onay ekranının. Aynı sınıfta toplamak, her ekranın
/// ilgilenmediği sağlayıcıları da tazelemesine yol açardı.
class RegistrationActions {
  const RegistrationActions(this._ref, this.eventId);

  final Ref _ref;
  final int eventId;

  EventRepository get _repository => _ref.read(eventRepositoryProvider);

  Future<void> apply() async {
    await _repository.apply(eventId);
    await _refresh();
  }

  Future<void> withdraw() async {
    await _repository.withdraw(eventId);
    await _refresh();
  }

  Future<RegistrationSummary> approve(int registrationId) async {
    final summary = await _repository.approveRegistration(
      eventId: eventId,
      registrationId: registrationId,
    );
    _invalidateRegistrations();
    return summary;
  }

  Future<RegistrationSummary> reject(int registrationId) async {
    final summary = await _repository.rejectRegistration(
      eventId: eventId,
      registrationId: registrationId,
    );
    _invalidateRegistrations();
    return summary;
  }

  /// Başvuru sonrası detay ve keşif listesi birlikte tazeleniyor.
  ///
  /// İkisi de kalan kontenjanı ve başvuru durumunu gösteriyor; biri
  /// güncellenip diğeri kalırsa kullanıcı iki farklı gerçek görür.
  /// `invalidate` tek başına yetmiyor — yeniden hesaplama asenkron başlıyor
  /// (Aşama 4'te öğrenildi).
  Future<void> _refresh() async {
    _ref.invalidate(publicEventProvider(eventId));
    _ref.invalidate(discoverEventsProvider);
    await _ref.read(publicEventProvider(eventId).future);
  }

  /// Onay listesinin bütün süzgeçlerini tazeler.
  ///
  /// Süzgeç sağlayıcının argümanında olduğu için her süzgeç ayrı bir önbellek.
  /// Bir başvuru onaylandığında "bekleyen" listesinden düşüp "kabul" listesine
  /// girmeli; yalnızca açık olanı tazelemek diğerlerini bayat bırakırdı.
  void _invalidateRegistrations() {
    for (final status in [null, ...RegistrationStatus.values]) {
      _ref.invalidate(eventRegistrationsProvider(RegistrationQuery(eventId, status)));
    }
  }
}

final registrationActionsProvider =
    Provider.family<RegistrationActions, int>((ref, eventId) {
  return RegistrationActions(ref, eventId);
});

/// Eşleştirmeyi çalıştıran ve durumunu izleyen işlemler (M6, 5.4).
class MatchingActions {
  const MatchingActions(this._ref, this.eventId);

  /// İki yoklama arası bekleme.
  ///
  /// Motor 200 kişide birkaç saniye sürüyor (9.9); saniyede bir sormak hem
  /// yeterince canlı hem de sunucuyu yormuyor. Sunucu iteklemesi (websocket)
  /// bu iş için fazla altyapı olurdu — organizatör ekranda bekliyor, sayfa
  /// zaten açık.
  static const pollInterval = Duration(seconds: 1);

  /// Yoklamanın vazgeçme sınırı.
  ///
  /// İşçi hiç çalışmıyorsa plan sonsuza kadar `queued` kalır. Kullanıcıyı
  /// dönen bir çarkla baş başa bırakmamak için bir noktada durup ne olduğunu
  /// söylemek gerekiyor.
  static const pollTimeout = Duration(minutes: 5);

  final Ref _ref;
  final int eventId;

  EventRepository get _repository => _ref.read(eventRepositoryProvider);

  /// Yeni bir plan versiyonu açar ve hesabı kuyruğa atar.
  ///
  /// `minimalChange` check-in sonrası yenileme (9.8): önceki plan başlangıç
  /// noktası oluyor, gelmeyenler çıkarılıyor, başlamış turlar donuyor.
  Future<PlanSummary> run({int? seed, bool minimalChange = false}) async {
    final plan = await _repository.runMatching(
      eventId,
      seed: seed,
      minimalChange: minimalChange,
    );
    _ref.invalidate(eventPlansProvider(eventId));
    return plan;
  }

  /// Hesap bitene kadar yoklar.
  ///
  /// Her adımda `onUpdate` çağrılıyor: ekran "kuyrukta"dan "çalışıyor"a
  /// geçişi göstermeli, yoksa kullanıcı bir şey olup olmadığını anlamaz.
  Future<PlanSummary> waitForResult(
    int planId, {
    required void Function(PlanSummary) onUpdate,
    required bool Function() shouldContinue,
  }) async {
    final deadline = DateTime.now().add(pollTimeout);
    var plan = await _repository.loadPlan(eventId, planId);
    onUpdate(plan);

    while (plan.isPending && shouldContinue()) {
      if (DateTime.now().isAfter(deadline)) {
        throw const ApiException(
          'Eşleştirme uzun süredir kuyrukta. Arka plan işçisi çalışmıyor '
          'olabilir.',
        );
      }
      await Future<void>.delayed(pollInterval);
      if (!shouldContinue()) break;
      plan = await _repository.loadPlan(eventId, planId);
      onUpdate(plan);
    }

    _ref.invalidate(eventPlansProvider(eventId));
    return plan;
  }
}

final matchingActionsProvider =
    Provider.family<MatchingActions, int>((ref, eventId) {
  return MatchingActions(ref, eventId);
});

/// Planı elle düzelten işlemler (M7).
///
/// Takas ve sabitleme güncel slot görünümünü **geri döndürüyor**; ekran onu
/// doğrudan kullanıyor, sağlayıcıyı tazeleyip yeniden istek atmıyor. Takas
/// sırasında listenin bir an eski hâline dönmesi seçimi kaybettirirdi.
///
/// Sağlayıcı yine de tazeleniyor: kullanıcı tura geri döndüğünde taze veri
/// bulmalı.
class PlanEditActions {
  const PlanEditActions(this._ref, this.eventId, this.planId);

  final Ref _ref;
  final int eventId;
  final int planId;

  EventRepository get _repository => _ref.read(eventRepositoryProvider);

  Future<SwapResult> swap({
    required int slotNumber,
    required int assignmentId,
    int? targetAssignmentId,
    int? targetTableId,
  }) async {
    final result = await _repository.swap(
      eventId: eventId,
      planId: planId,
      slotNumber: slotNumber,
      assignmentId: assignmentId,
      targetAssignmentId: targetAssignmentId,
      targetTableId: targetTableId,
    );
    _ref.invalidate(planSlotProvider(SlotQuery(eventId, planId, slotNumber)));
    // Takas yalnızca o turu değil özeti de değiştiriyor: karşılanan talep
    // sayısı düşebilir, karşılanmayan karşılıklı talep listeye girebilir,
    // biri eşleşmesiz kalabilir. Özet tazelenmezse organizatör neyi bozduğunu
    // göremez — tarayıcı turunda tam olarak böyle oldu.
    _ref.invalidate(planProvider(PlanQuery(eventId, planId)));
    await _ref.read(planProvider(PlanQuery(eventId, planId)).future);
    return result;
  }

  Future<SlotView> setPinned({
    required int slotNumber,
    required int assignmentId,
    required bool isPinned,
  }) async {
    final slot = await _repository.setPinned(
      eventId: eventId,
      planId: planId,
      assignmentId: assignmentId,
      isPinned: isPinned,
    );
    _ref.invalidate(planSlotProvider(SlotQuery(eventId, planId, slotNumber)));
    return slot;
  }

  /// Planı yayına alır.
  ///
  /// Etkinliğin bütün planları tazeleniyor: önceki yayındaki plan arşive
  /// geçtiği için liste de değişti.
  Future<PlanSummary> publish() async {
    final plan = await _repository.publishPlan(eventId, planId);
    _ref.invalidate(planProvider(PlanQuery(eventId, planId)));
    _ref.invalidate(eventPlansProvider(eventId));
    await _ref.read(planProvider(PlanQuery(eventId, planId)).future);
    return plan;
  }
}

final planEditActionsProvider =
    Provider.family<PlanEditActions, PlanQuery>((ref, query) {
  return PlanEditActions(ref, query.eventId, query.planId);
});

/// Görüşme talebi işlemleri (M9).
///
/// Uçlar güncel listeyi geri döndürüyor; ekran onu doğrudan kullanıyor.
/// Sağlayıcı yine de tazeleniyor: başka bir süzgeçle geri dönüldüğünde satır
/// eski hâlinde kalmamalı.
class RequestActions {
  const RequestActions(this._ref, this.eventId);

  final Ref _ref;
  final int eventId;

  Future<ParticipantList> send(int targetRegistrationId) async {
    final list = await _ref
        .read(eventRepositoryProvider)
        .sendRequest(eventId, targetRegistrationId);
    _invalidate();
    return list;
  }

  Future<ParticipantList> withdraw(int requestId) async {
    final list =
        await _ref.read(eventRepositoryProvider).withdrawRequest(eventId, requestId);
    _invalidate();
    return list;
  }

  /// Bütün süzgeçleri tazeliyor.
  ///
  /// Talep gönderilen kişi başka bir süzgeçte de görünüyor olabilir; yalnızca
  /// açık olanı tazelemek onu eski hâlinde bırakırdı.
  void _invalidate() => _ref.invalidate(participantsProvider);
}

final requestActionsProvider = Provider.family<RequestActions, int>((ref, eventId) {
  return RequestActions(ref, eventId);
});

/// Check-in işlemleri (M10).
///
/// Uçlar güncel listeyi geri döndürüyor; ekran onu doğrudan kullanıyor.
/// Sağlayıcı yine de tazeleniyor — arama süzgeci değişince taze veri gelmeli.
class AttendanceActions {
  const AttendanceActions(this._ref, this.eventId);

  final Ref _ref;
  final int eventId;

  Future<ScanResult> scan(String qrCode) async {
    final result = await _ref.read(eventRepositoryProvider).scanCode(eventId, qrCode);
    _ref.invalidate(attendanceProvider);
    return result;
  }

  Future<AttendanceBoard> mark(int registrationId, {required bool present}) async {
    final board = await _ref.read(eventRepositoryProvider).markAttendance(
          eventId: eventId,
          registrationId: registrationId,
          present: present,
        );
    _ref.invalidate(attendanceProvider);
    return board;
  }
}

final attendanceActionsProvider =
    Provider.family<AttendanceActions, int>((ref, eventId) {
  return AttendanceActions(ref, eventId);
});

