import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_exception.dart';
import '../config/app_config.dart';
import 'auth_repository.dart';
import 'token_storage.dart';

final tokenStorageProvider = Provider<TokenStorage>((ref) => TokenStorage());

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(
    baseUrl: AppConfig.apiBaseUrl,
    tokenStorage: ref.watch(tokenStorageProvider),
  );
});

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    api: ref.watch(apiClientProvider),
    storage: ref.watch(tokenStorageProvider),
  );
});

/// Oturum durumu.
///
/// Yönlendirme buna bakarak karar veriyor, bu yüzden "henüz bilmiyoruz" ile
/// "oturum yok" ayrı tutuluyor: uygulama açılırken güvenli depo okunana kadar
/// kullanıcıyı giriş ekranına atmak yanlış olurdu.
sealed class AuthState {
  const AuthState();
}

class SignedOut extends AuthState {
  const SignedOut();
}

class SignedIn extends AuthState {
  const SignedIn(this.account);

  final Account account;
}

/// Oturumu yöneten denetleyici.
class AuthController extends AsyncNotifier<AuthState> {
  AuthRepository get _repository => ref.read(authRepositoryProvider);

  @override
  Future<AuthState> build() async {
    // Sunucu adresi verilmemişse hiçbir istek atılamaz; kullanıcıyı sonsuz
    // yükleniyor ekranında bırakmamak için doğrudan oturumsuz sayılıyor.
    if (!AppConfig.isConfigured) return const SignedOut();

    if (!await _repository.hasStoredSession) return const SignedOut();

    try {
      // Depoda jeton olması yetmez: süresi dolmuş olabilir. `/auth/me` çağrısı
      // gerekirse sessiz yenilemeyi de tetikler.
      return SignedIn(await _repository.currentAccount());
    } on ApiException {
      await _repository.logout();
      return const SignedOut();
    }
  }

  /// Kayıt olur ve oturumu açar.
  ///
  /// Hata **fırlatılır, duruma yazılmaz**. Sebep yönlendirme: paylaşılan durum
  /// "yükleniyor" veya "hata" olsaydı, giriş denemesi sırasında kullanıcı açılış
  /// ekranına atılır ya da hatayı göremeden başka bir sayfaya gönderilirdi.
  /// Formun kendi hatası formda kalmalı.
  Future<void> register({
    required String email,
    required String password,
  }) async {
    final account = await _repository.register(email: email, password: password);
    state = AsyncData(SignedIn(account));
  }

  /// Giriş yapar. Hata davranışı `register` ile aynı.
  Future<void> login({
    required String email,
    required String password,
  }) async {
    final account = await _repository.login(email: email, password: password);
    state = AsyncData(SignedIn(account));
  }

  Future<void> signOut() async {
    await _repository.logout();
    state = const AsyncData(SignedOut());
  }
}

final authControllerProvider =
    AsyncNotifierProvider<AuthController, AuthState>(AuthController.new);

/// Yönlendirmenin ihtiyacı olan sade cevap.
final isSignedInProvider = Provider<bool>((ref) {
  return ref.watch(authControllerProvider).asData?.value is SignedIn;
});
