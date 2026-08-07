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
    // Yenileme tutmadığında oturum düşürülüyor; yönlendirme kullanıcıyı giriş
    // ekranına alıyor. `read` çağrı anında yapılıyor — burada `watch` ile
    // bağımlılık kurmak döngü olurdu: kimlik → depo → istemci.
    onSessionLost: () => ref.read(authControllerProvider.notifier).sessionExpired(),
  );
});

/// Sunucu adresi verilmiş mi.
///
/// Sağlayıcı olarak duruyor çünkü `AppConfig.isConfigured` derleme zamanında
/// sabitleniyor: testler yapılandırılmış bir uygulamayı başka türlü taklit
/// edemez ve açılıştaki hata yolları hiç çalıştırılamazdı.
final apiConfiguredProvider = Provider<bool>((ref) => AppConfig.isConfigured);

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
    if (!ref.watch(apiConfiguredProvider)) return const SignedOut();

    if (!await _repository.hasStoredSession) return const SignedOut();

    try {
      // Depoda jeton olması yetmez: süresi dolmuş olabilir. `/auth/me` çağrısı
      // gerekirse sessiz yenilemeyi de tetikler.
      return SignedIn(await _repository.currentAccount());
    } on ApiException catch (error) {
      // **Yalnızca kimlik gerçekten reddedildiyse jeton silinir.** Sunucuya
      // ulaşamamak bir kimlik kararı değil: silinirse etkinlik günü şebekesi
      // zayıf olan katılımcı oturumunu ve giriş kodunu kaybeder, sunucu geri
      // geldiğinde şifresini yeniden girmek zorunda kalır.
      if (error.isUnauthorised) await _repository.logout();
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
    _dropUserCaches();
    state = AsyncData(SignedIn(account));
  }

  /// Giriş yapar. Hata davranışı `register` ile aynı.
  Future<void> login({
    required String email,
    required String password,
  }) async {
    final account = await _repository.login(email: email, password: password);
    _dropUserCaches();
    state = AsyncData(SignedIn(account));
  }

  /// Sunucu jetonu reddetti ve sessiz yenileme de tutmadı.
  ///
  /// `signOut`'tan farkı: jeton `ApiClient` tarafından zaten silindi, burada
  /// yapılacak tek şey durumu düşürmek. Düşmezse kullanıcı oturumu bitmiş
  /// hâlde ekranlarda dolaşır ve her istek hataya düşer.
  ///
  /// Sonraki döngüye bırakılıyor: çağrı bir araya giricinin içinden geliyor ve
  /// açılışta `build` henüz sürüyor olabilir — o sırada duruma yazmak hata.
  void sessionExpired() {
    Future.microtask(() {
      if (state.value is! SignedIn) return;
      state = const AsyncData(SignedOut());
      _dropUserCaches();
    });
  }

  Future<void> signOut() async {
    await _repository.logout();
    // Önce durum, sonra önbellek: durum değişince yönlendirme ekranları
    // söküyor. Ters sırada sağlayıcılar jetonsuz kalmış istemciyle yeniden
    // istek atar ve kullanıcı çıkarken bir anlık hata ekranı görürdü.
    state = const AsyncData(SignedOut());
    _dropUserCaches();
  }

  /// Kullanıcıya ait bütün önbellekleri düşürür.
  ///
  /// `apiClientProvider` zincirin kökü: depolar onu, ekranların sağlayıcıları
  /// da depoları izliyor. Kökü tazelemek zincirin tamamını düşürüyor.
  ///
  /// Sağlayıcıları tek tek saymak yerine kök seçildi: sonradan eklenen bir
  /// sağlayıcının listeye yazılması unutulduğunda sessizce sızdırırdı. Bu
  /// tarayıcıda gerçekten oldu — çıkış yapıp başka hesapla girildiğinde
  /// "Profilim" bir önceki kullanıcının adını, şirketini ve etiketlerini
  /// gösteriyordu.
  void _dropUserCaches() => ref.invalidate(apiClientProvider);
}

final authControllerProvider =
    AsyncNotifierProvider<AuthController, AuthState>(AuthController.new);

/// Yönlendirmenin ihtiyacı olan sade cevap.
final isSignedInProvider = Provider<bool>((ref) {
  return ref.watch(authControllerProvider).asData?.value is SignedIn;
});
