import '../api/api_client.dart';
import 'token_storage.dart';

/// Oturumdaki hesabın gösterilecek bilgileri.
class Account {
  const Account({required this.id, required this.email});

  factory Account.fromJson(Map<String, dynamic> json) => Account(
        id: json['id'] as int,
        email: json['email'] as String,
      );

  final int id;
  final String email;
}

/// Kimlik işlemleri (şartname M1).
///
/// Kayıt doğrudan oturum açar: sunucu jetonları kayıt yanıtında döndürüyor
/// (Bölüm 10 "Kayıt olan kullanıcı doğrudan giriş yapabiliyor").
class AuthRepository {
  const AuthRepository({required ApiClient api, required TokenStorage storage})
      : _api = api,
        _storage = storage;

  final ApiClient _api;
  final TokenStorage _storage;

  Future<Account> register({
    required String email,
    required String password,
  }) async {
    final tokens = await _api.post(
      '/auth/register',
      body: {'email': email, 'password': password},
    );
    await _saveTokens(tokens);
    return currentAccount();
  }

  Future<Account> login({
    required String email,
    required String password,
  }) async {
    final tokens = await _api.post(
      '/auth/login',
      body: {'email': email, 'password': password},
    );
    await _saveTokens(tokens);
    return currentAccount();
  }

  Future<Account> currentAccount() async {
    return Account.fromJson(await _api.getObject('/auth/me'));
  }

  /// Çıkış — jetonu silmek yeterli.
  ///
  /// Sunucuda oturum kaydı tutulmuyor, dolayısıyla bildirilecek bir uç da yok.
  Future<void> logout() => _storage.clear();

  Future<bool> get hasStoredSession => _storage.hasSession;

  Future<void> _saveTokens(Map<String, dynamic> tokens) {
    return _storage.save(
      accessToken: tokens['access_token'] as String,
      refreshToken: tokens['refresh_token'] as String,
    );
  }
}
