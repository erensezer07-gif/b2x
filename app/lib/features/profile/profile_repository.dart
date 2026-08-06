import 'package:dio/dio.dart';

import '../../core/api/api_client.dart';
import 'models.dart';

/// Profil, şirket ve taksonomi işlemleri (şartname M2).
class ProfileRepository {
  const ProfileRepository(this._api);

  final ApiClient _api;

  Future<Profile> load() async {
    return Profile.fromJson(await _api.getObject('/profile'));
  }

  /// Sihirbazın her adımı bunu çağırır.
  ///
  /// Yalnızca verilen alanlar gönderilir; gönderilmeyen alan sunucuda değişmez
  /// (M2: *"her adım kaydedilir, kullanıcı yarıda bırakıp sonra devam
  /// edebilir"*).
  Future<Profile> update(Map<String, dynamic> changes) async {
    return Profile.fromJson(await _api.patch('/profile', body: changes));
  }

  /// Yazarken şirket önerileri (Bölüm 6).
  Future<List<Company>> searchCompanies(String query) async {
    final results = await _api.getList('/companies', query: {'q': query});
    return results
        .map((item) => Company.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  /// Şirketi bulur, yoksa oluşturur.
  ///
  /// Aynı şirketin farklı yazımları tek kimliğe düşer; tekilleştirme sunucuda
  /// yapılır (Bölüm 6).
  Future<Company> findOrCreateCompany(String name) async {
    return Company.fromJson(await _api.post('/companies', body: {'name': name}));
  }

  Future<List<Sector>> loadSectors() async {
    final results = await _api.getList('/sectors');
    return results
        .map((item) => Sector.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<TagCategory>> loadTagCategories() async {
    final results = await _api.getList('/tag-categories');
    return results
        .map((item) => TagCategory.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<Profile> uploadPhoto({
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
    return Profile.fromJson(await _api.postForm('/profile/photo', form));
  }

  Future<Profile> removePhoto() async {
    return Profile.fromJson(await _api.delete('/profile/photo'));
  }
}
