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
  }

  /// Etkinlik listesini tazeler ve yeni verinin gelmesini bekler.
  ///
  /// Liste, kart üstünde adı, tur sayısını ve durum rozetini gösteriyor;
  /// sihirbazda değişen her şey oraya yansımalı.
  Future<void> refreshList() async {
    _ref.invalidate(myEventsProvider);
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
