import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Jetonların cihazdaki deposu (şartname M1).
///
/// *"Jetonlar cihazda güvenli depoda saklanır."* Android'de Keystore, iOS'ta
/// Keychain kullanılıyor.
///
/// Web tarafında tarayıcının sunduğu koruma sınırlı — orada gerçek bir güvenli
/// alan yok. MVP'de web yalnızca geliştirme ve demo için derleniyor; üretimde
/// mobil hedefleniyor.
class TokenStorage {
  TokenStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _accessTokenKey = 'b2x_access_token';
  static const _refreshTokenKey = 'b2x_refresh_token';

  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: _accessTokenKey, value: accessToken);
    await _storage.write(key: _refreshTokenKey, value: refreshToken);
  }

  Future<String?> readAccessToken() => _storage.read(key: _accessTokenKey);

  Future<String?> readRefreshToken() => _storage.read(key: _refreshTokenKey);

  Future<bool> get hasSession async => (await readRefreshToken()) != null;

  /// Çıkış.
  ///
  /// Sunucuda oturum kaydı yok (jetonlar durumsuz), bu yüzden çıkış tamamen
  /// burada oluyor: jetonu silmek oturumu bitirir.
  Future<void> clear() async {
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _refreshTokenKey);
  }
}
