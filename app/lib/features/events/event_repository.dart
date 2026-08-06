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
}
