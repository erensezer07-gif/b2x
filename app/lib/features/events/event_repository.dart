import 'package:dio/dio.dart';

import '../../core/api/api_client.dart';
import 'models.dart';

/// Etkinlik ve salon düzeni işlemleri (şartname M4, M5).
class EventRepository {
  const EventRepository(this._api);

  final ApiClient _api;

  /// Kullanıcının organizatör olduğu etkinlikler.
  ///
  /// Başkalarının etkinlikleri burada görünmez (Bölüm 7); etkinlik keşfi
  /// Aşama 6'nın konusu.
  Future<List<EventSummary>> listMine() async {
    final results = await _api.getList('/events');
    return results
        .map((item) => EventSummary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<EventDetail> load(int eventId) async {
    return EventDetail.fromJson(await _api.getObject('/events/$eventId'));
  }

  /// Sihirbazın ilk adımı — taslak açar.
  Future<EventDetail> createDraft({
    required String name,
    required DateTime startsAt,
  }) async {
    return EventDetail.fromJson(
      await _api.post('/events', body: {
        'name': name,
        'starts_at': startsAt.toUtc().toIso8601String(),
      }),
    );
  }

  /// Sihirbazın her adımı bunu çağırır; yalnızca verilen alanlar değişir.
  Future<EventDetail> update(int eventId, Map<String, dynamic> changes) async {
    return EventDetail.fromJson(
      await _api.patch('/events/$eventId', body: changes),
    );
  }

  /// Etkinliği siler.
  Future<void> deleteEvent(int eventId) async {
    await _api.delete('/events/$eventId');
  }

  Future<EventDetail> uploadCover({
    required int eventId,
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
        contentType: DioMediaType.parse(contentType),
      ),
    });
    return EventDetail.fromJson(
      await _api.postForm('/events/$eventId/cover', form),
    );
  }

  Future<EventDetail> removeCover(int eventId) async {
    return EventDetail.fromJson(await _api.delete('/events/$eventId/cover'));
  }

  /// Otomatik salon düzeni (M5).
  ///
  /// Çağrı mevcut düzenin **yerine geçer**; masa sayısı değişince eskiler
  /// silinir.
  Future<EventLayout> buildAutoLayout({
    required int eventId,
    required TableKind kind,
    required int tableCount,
    int? seatCount,
    int? minPeople,
    int? maxPeople,
  }) async {
    return EventLayout.fromJson(
      await _api.put('/events/$eventId/layout/auto', body: {
        'kind': kind.key,
        'table_count': tableCount,
        // Null olan alan hiç gönderilmiyor: masa tipiyle uyuşmayan bir alanı
        // `null` olarak yollamak sunucuda doğrulama hatası verirdi.
        'seat_count': ?seatCount,
        'min_people': ?minPeople,
        'max_people': ?maxPeople,
      }),
    );
  }

  /// Manuel moda geçirir veya ızgarayı yeniden boyutlandırır (M5).
  ///
  /// Otomatik modda kurulmuş masalar korunur; sunucu onları ızgaraya satır
  /// satır dizer.
  Future<EventLayout> buildManualLayout({
    required int eventId,
    required int gridWidth,
    required int gridHeight,
  }) async {
    return EventLayout.fromJson(
      await _api.put('/events/$eventId/layout/manual', body: {
        'grid_width': gridWidth,
        'grid_height': gridHeight,
      }),
    );
  }

  Future<EventLayout> loadLayout(int eventId) async {
    return EventLayout.fromJson(await _api.getObject('/events/$eventId/layout'));
  }

  /// Tuvale masa koyar (M5).
  ///
  /// Numara verilmezse sunucu sıradaki boş numarayı atar.
  Future<EventLayout> createTable({
    required int eventId,
    required TableKind kind,
    required int gridX,
    required int gridY,
    int? seatCount,
    int? minPeople,
    int? maxPeople,
    int? number,
    String? label,
  }) async {
    return EventLayout.fromJson(
      await _api.post('/events/$eventId/tables', body: {
        'kind': kind.key,
        'grid_x': gridX,
        'grid_y': gridY,
        'seat_count': ?seatCount,
        'min_people': ?minPeople,
        'max_people': ?maxPeople,
        'number': ?number,
        'label': ?label,
      }),
    );
  }

  Future<EventLayout> updateTable({
    required int eventId,
    required int tableId,
    required Map<String, dynamic> changes,
  }) async {
    return EventLayout.fromJson(
      await _api.patch('/events/$eventId/tables/$tableId', body: changes),
    );
  }

  Future<EventLayout> deleteTable({
    required int eventId,
    required int tableId,
  }) async {
    return EventLayout.fromJson(
      await _api.delete('/events/$eventId/tables/$tableId'),
    );
  }

  Future<EventLayout> createArea({
    required int eventId,
    required String label,
    required int gridX,
    required int gridY,
    required int width,
    required int height,
  }) async {
    return EventLayout.fromJson(
      await _api.post('/events/$eventId/areas', body: {
        'label': label,
        'grid_x': gridX,
        'grid_y': gridY,
        'width': width,
        'height': height,
      }),
    );
  }

  Future<EventLayout> updateArea({
    required int eventId,
    required int areaId,
    required Map<String, dynamic> changes,
  }) async {
    return EventLayout.fromJson(
      await _api.patch('/events/$eventId/areas/$areaId', body: changes),
    );
  }

  Future<EventLayout> deleteArea({
    required int eventId,
    required int areaId,
  }) async {
    return EventLayout.fromJson(
      await _api.delete('/events/$eventId/areas/$areaId'),
    );
  }

  /// Kayıtları açar.
  ///
  /// Salon düzeni kurulmadan çağrılırsa sunucu reddeder (M4, Bölüm 10).
  Future<EventDetail> openRegistration(int eventId) async {
    return EventDetail.fromJson(
      await _api.post('/events/$eventId/open-registration'),
    );
  }

  // --- Keşif ve başvuru (M3) -------------------------------------------------

  /// *"Yaklaşan etkinliklerin listesi."*
  ///
  /// Kendi düzenlediklerin de burada görünür — rol etkinliğe göre belirleniyor
  /// (Bölüm 7). Kartın `isOpen` alanı başvurulup başvurulamayacağını söyler.
  Future<List<DiscoverEvent>> discover() async {
    final results = await _api.getList('/events/discover');
    return results
        .map((item) => DiscoverEvent.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// Katılımcının gördüğü etkinlik detayı.
  ///
  /// Organizatörün ucu ayrı (`load`); bu uç organizatör alanlarını taşımaz.
  Future<PublicEvent> loadPublic(int eventId) async {
    return PublicEvent.fromJson(await _api.getObject('/events/$eventId/public'));
  }

  /// Etkinliğe başvurur.
  ///
  /// Profil eksikse sunucu 422 ile eksik alanların listesini döner;
  /// `ApiException.message` bunu Türkçe cümleye çevirmiyor — ekran
  /// `missingForApplication` üzerinden kendi metnini kuruyor.
  Future<PublicEvent> apply(int eventId) async {
    return PublicEvent.fromJson(await _api.post('/events/$eventId/registration'));
  }

  Future<PublicEvent> withdraw(int eventId) async {
    return PublicEvent.fromJson(await _api.delete('/events/$eventId/registration'));
  }

  // --- Organizatör: başvuru yönetimi -----------------------------------------

  Future<RegistrationSummary> loadRegistrations(
    int eventId, {
    RegistrationStatus? status,
  }) async {
    return RegistrationSummary.fromJson(
      await _api.getObject(
        '/events/$eventId/registrations',
        query: {'status': ?status?.key},
      ),
    );
  }

  Future<RegistrationSummary> approveRegistration({
    required int eventId,
    required int registrationId,
  }) async {
    return RegistrationSummary.fromJson(
      await _api.post('/events/$eventId/registrations/$registrationId/approve'),
    );
  }

  Future<RegistrationSummary> rejectRegistration({
    required int eventId,
    required int registrationId,
  }) async {
    return RegistrationSummary.fromJson(
      await _api.post('/events/$eventId/registrations/$registrationId/reject'),
    );
  }

  // --- Eşleştirme (M6, 5.4) --------------------------------------------------

  /// Çalıştırma öncesi kontrol listesi.
  Future<MatchingCheck> loadMatchingCheck(int eventId) async {
    return MatchingCheck.fromJson(
      await _api.getObject('/events/$eventId/matching-check'),
    );
  }

  /// Eşleştirmeyi kuyruğa atar.
  ///
  /// Anında dönüyor; plan `queued` durumunda. Sonuç `loadPlan` ile izleniyor.
  Future<PlanSummary> runMatching(
    int eventId, {
    int? seed,
    bool minimalChange = false,
  }) async {
    return PlanSummary.fromJson(
      await _api.post(
        '/events/$eventId/plans',
        body: {'seed': ?seed, 'minimal_change': minimalChange},
      ),
    );
  }

  Future<List<PlanSummary>> loadPlans(int eventId) async {
    final results = await _api.getList('/events/$eventId/plans');
    return results
        .map((item) => PlanSummary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<PlanSummary> loadPlan(int eventId, int planId) async {
    return PlanSummary.fromJson(
      await _api.getObject('/events/$eventId/plans/$planId'),
    );
  }

  // --- Plan önizleme ve elle düzeltme (M7) -----------------------------------

  /// Bir turun masaları ve oturanları. Boş masalar da geliyor.
  Future<SlotView> loadSlot(int eventId, int planId, int slotNumber) async {
    return SlotView.fromJson(
      await _api.getObject('/events/$eventId/plans/$planId/slots/$slotNumber'),
    );
  }

  /// İki kişinin yerini değiştirir ya da birini boş yere taşır.
  ///
  /// Hedef olarak ya bir kişi ya bir masa verilir; ikisi birden geçersiz.
  /// Kural ihlalleri **uyarı** olarak dönüyor, takası engellemiyor (M7).
  Future<SwapResult> swap({
    required int eventId,
    required int planId,
    required int slotNumber,
    required int assignmentId,
    int? targetAssignmentId,
    int? targetTableId,
  }) async {
    return SwapResult.fromJson(
      await _api.post(
        '/events/$eventId/plans/$planId/swap',
        body: {
          'slot_number': slotNumber,
          'assignment_id': assignmentId,
          'target_assignment_id': ?targetAssignmentId,
          'target_table_id': ?targetTableId,
        },
      ),
    );
  }

  /// Atamayı sabitler veya çözer; güncel slot görünümünü döner.
  Future<SlotView> setPinned({
    required int eventId,
    required int planId,
    required int assignmentId,
    required bool isPinned,
  }) async {
    return SlotView.fromJson(
      await _api.patch(
        '/events/$eventId/plans/$planId/assignments/$assignmentId',
        body: {'is_pinned': isPinned},
      ),
    );
  }

  /// Planı yayına alır; varsa önceki yayındaki plan arşive geçer.
  Future<PlanSummary> publishPlan(int eventId, int planId) async {
    return PlanSummary.fromJson(
      await _api.post('/events/$eventId/plans/$planId/publish'),
    );
  }

  // --- Katılımcı görünümü (M8) -----------------------------------------------

  /// Katılımcının kendi planı.
  ///
  /// Kimlik gönderilmiyor: sunucu jetondan alıyor. Plan yayında değilse
  /// `isPublished` yanlış ve tur listesi boş geliyor (Bölüm 7).
  Future<MyPlan> loadMyPlan(int eventId) async {
    return MyPlan.fromJson(await _api.getObject('/events/$eventId/my-plan'));
  }

  /// Salon krokisi — kimin oturduğu yok.
  Future<Venue> loadVenue(int eventId) async {
    return Venue.fromJson(await _api.getObject('/events/$eventId/venue'));
  }

  /// Masa arkadaşının tam profili. Masa arkadaşı değilse sunucu 404 döner.
  Future<TablemateProfile> loadTablemate(int eventId, int registrationId) async {
    return TablemateProfile.fromJson(
      await _api.getObject('/events/$eventId/tablemates/$registrationId'),
    );
  }

  // --- Görüşme talepleri (M9) ------------------------------------------------

  /// Etkinliğin katılımcıları ve kalan talep hakkım.
  ///
  /// Liste tam profil taşımıyor: ad, unvan, şirket, sektör (Bölüm 7).
  Future<ParticipantList> loadParticipants(
    int eventId, {
    String? search,
    int? sectorId,
  }) async {
    return ParticipantList.fromJson(
      await _api.getObject(
        '/events/$eventId/participants',
        query: {'q': ?search, 'sector_id': ?sectorId?.toString()},
      ),
    );
  }

  /// Talep gönderir; güncel listeyi döner.
  Future<ParticipantList> sendRequest(int eventId, int targetRegistrationId) async {
    return ParticipantList.fromJson(
      await _api.post(
        '/events/$eventId/requests',
        body: {'target_registration_id': targetRegistrationId},
      ),
    );
  }

  /// Talebi geri çeker ve hakkı iade eder; güncel listeyi döner.
  Future<ParticipantList> withdrawRequest(int eventId, int requestId) async {
    return ParticipantList.fromJson(
      await _api.delete('/events/$eventId/requests/$requestId'),
    );
  }

  // --- Check-in (M10) --------------------------------------------------------

  /// Katılımcının kendi giriş kodu.
  Future<MyQrCode> loadMyQr(int eventId) async {
    return MyQrCode.fromJson(await _api.getObject('/events/$eventId/my-qr'));
  }

  /// Check-in listesi ve sayaç (organizatör).
  Future<AttendanceBoard> loadAttendance(int eventId, {String? search}) async {
    return AttendanceBoard.fromJson(
      await _api.getObject('/events/$eventId/attendance', query: {'q': ?search}),
    );
  }

  /// Okutulan kodu işler.
  Future<ScanResult> scanCode(int eventId, String qrCode) async {
    return ScanResult.fromJson(
      await _api.post('/events/$eventId/attendance/scan', body: {'qr_code': qrCode}),
    );
  }

  /// Elle geldi/gelmedi işaretler; güncel listeyi döner.
  Future<AttendanceBoard> markAttendance({
    required int eventId,
    required int registrationId,
    required bool present,
  }) async {
    return AttendanceBoard.fromJson(
      await _api.post(
        '/events/$eventId/attendance/$registrationId',
        body: {'present': present},
      ),
    );
  }

  /// İki plan arasında kimin yeri değişti (M10).
  Future<PlanChanges> loadPlanChanges(int eventId, int planId) async {
    return PlanChanges.fromJson(
      await _api.getObject('/events/$eventId/plans/$planId/changes'),
    );
  }
}
