import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/auth_controller.dart';
import 'models.dart';
import 'profile_repository.dart';

final profileRepositoryProvider = Provider<ProfileRepository>((ref) {
  return ProfileRepository(ref.watch(apiClientProvider));
});

/// Kullanıcının profili.
///
/// Sihirbazın her adımı bunu güncelliyor; tamamlanma yüzdesi ve başvuru
/// yeterliliği sunucudan geldiği için ekranlar kendi hesaplarını yapmıyor.
class ProfileController extends AsyncNotifier<Profile> {
  ProfileRepository get _repository => ref.read(profileRepositoryProvider);

  @override
  Future<Profile> build() => _repository.load();

  /// Bir adımı kaydeder.
  ///
  /// Hata **fırlatılır**: adım ekranı onu kendi içinde gösterir. Paylaşılan
  /// duruma yazılsaydı sihirbaz komple hata ekranına düşer, kullanıcı girdiği
  /// veriyi kaybederdi.
  Future<void> save(Map<String, dynamic> changes) async {
    final updated = await _repository.update(changes);
    state = AsyncData(updated);
  }

  Future<void> uploadPhoto({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    final updated = await _repository.uploadPhoto(
      bytes: bytes,
      filename: filename,
      contentType: contentType,
    );
    state = AsyncData(updated);
  }

  Future<void> removePhoto() async {
    state = AsyncData(await _repository.removePhoto());
  }

  Future<void> reload() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_repository.load);
  }
}

final profileControllerProvider =
    AsyncNotifierProvider<ProfileController, Profile>(ProfileController.new);

/// Sektör listesi — sihirbazın ikinci adımında kullanılıyor.
///
/// Bir kez yüklenip önbelleğe alınıyor: liste etkinlik boyunca değişmiyor.
final sectorsProvider = FutureProvider<List<Sector>>((ref) {
  return ref.watch(profileRepositoryProvider).loadSectors();
});

/// Etiket havuzu — üçüncü ve dördüncü adımda aynı liste kullanılıyor (Bölüm 6).
final tagCategoriesProvider = FutureProvider<List<TagCategory>>((ref) {
  return ref.watch(profileRepositoryProvider).loadTagCategories();
});

/// Şirket arama sonuçları.
///
/// `autoDispose`: kullanıcı yazmayı bıraktığında sonuçlar bellekte kalmasın.
final companySearchProvider =
    FutureProvider.autoDispose.family<List<Company>, String>((ref, query) async {
  final trimmed = query.trim();
  // Tek harfe sorgu atmak hem gereksiz hem de neredeyse tüm listeyi döndürür.
  if (trimmed.length < 2) return const [];
  return ref.watch(profileRepositoryProvider).searchCompanies(trimmed);
});
