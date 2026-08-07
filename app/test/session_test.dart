// Oturum değişince kullanıcıya ait önbellekler düşüyor mu (şartname M1).
//
// Tarayıcı turunda yakalandı: çıkış yapılıp başka hesapla girildiğinde
// "Profilim" bir önceki kullanıcının adını, şirketini ve etiketlerini
// gösteriyordu. Aynı cihazı iki kişi kullandığında birinin profili diğerine
// görünüyor demekti.
//
// Zincir şu: `apiClientProvider` → depolar → ekranların sağlayıcıları.
// `AuthController` girişte ve çıkışta kökü tazeliyor, zincirin tamamı
// düşüyor. Bu test zincirin kopmadığını kilitliyor — kopması sessiz olurdu.

import 'package:b2x/core/api/api_client.dart';
import 'package:b2x/core/api/api_exception.dart';
import 'package:b2x/core/auth/auth_controller.dart';
import 'package:b2x/core/auth/auth_repository.dart';
import 'package:b2x/core/auth/token_storage.dart';
import 'package:b2x/features/profile/models.dart';
import 'package:b2x/features/profile/profile_controller.dart';
import 'package:b2x/features/profile/profile_repository.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Sunucudaki oturumun testteki karşılığı: kim girdiyse o.
class _Session {
  String? email;
}

Map<String, dynamic> _profileJson(String name) => {
      'full_name': name,
      'title': null,
      'city': null,
      'bio': null,
      'photo_url': null,
      'website': null,
      'linkedin_url': null,
      'company': null,
      'sector': null,
      'offered_tags': <Map<String, dynamic>>[],
      'sought_tags': <Map<String, dynamic>>[],
      'completion_percent': 40,
      'missing_for_application': <String>[],
      'can_apply': true,
    };

class _FakeAuthRepository extends AuthRepository {
  _FakeAuthRepository(this._session, ApiClient api, {this.failWith})
      : super(api: api, storage: TokenStorage());

  final _Session _session;

  /// Doluysa `currentAccount` bunu fırlatır: açılışta sunucunun ne dediğini
  /// testin belirlemesi için.
  final ApiException? failWith;

  var loggedOut = false;

  @override
  Future<bool> get hasStoredSession async => _session.email != null;

  @override
  Future<Account> login({required String email, required String password}) async {
    _session.email = email;
    return Account(id: email.hashCode, email: email);
  }

  @override
  Future<Account> currentAccount() async {
    if (failWith != null) throw failWith!;
    return Account(id: _session.email.hashCode, email: _session.email!);
  }

  @override
  Future<void> logout() async {
    loggedOut = true;
    _session.email = null;
  }
}

/// Depo `apiClientProvider`'a bağlı kalmalı: zincir oradan kopuyor.
class _FakeProfileRepository extends ProfileRepository {
  const _FakeProfileRepository(this._session, ApiClient api) : super(api);

  final _Session _session;

  @override
  Future<Profile> load() async {
    return Profile.fromJson(_profileJson(_names[_session.email] ?? '—'));
  }

  static const _names = {
    'deniz@ornek.com': 'Deniz Aydın',
    'ayse@ornek.com': 'Ayşe Yılmaz',
  };
}

// ignore: library_private_types_in_public_api
_FakeAuthRepository? lastAuthRepository;

ProviderContainer _container(_Session session, {ApiException? failWith}) {
  final container = ProviderContainer(
    overrides: [
      // Sunucu adresi derleme zamanında verilmiyor; yapılandırılmış bir
      // uygulama taklit edilmezse `build` daha ilk satırda çıkar ve açılış
      // hata yolları hiç çalışmaz.
      apiConfiguredProvider.overrideWithValue(true),
      // `overrideWith` (değerle değil): sahte depolar da `apiClientProvider`'ı
      // izliyor, yoksa test zinciri kendisi koparır ve hep geçerdi.
      authRepositoryProvider.overrideWith(
        (ref) => lastAuthRepository = _FakeAuthRepository(
          session,
          ref.watch(apiClientProvider),
          failWith: failWith,
        ),
      ),
      profileRepositoryProvider.overrideWith(
        (ref) => _FakeProfileRepository(session, ref.watch(apiClientProvider)),
      ),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('başka hesapla girildiğinde önceki profil gösterilmiyor', () async {
    final session = _Session();
    final container = _container(session);

    await container
        .read(authControllerProvider.notifier)
        .login(email: 'deniz@ornek.com', password: 'sifre');
    // Profil ekranı gibi dinleyici tut: dinlenmeyen sağlayıcı zaten düşer,
    // hata tam da dinlenirken ayakta kalmasından çıkıyordu.
    final subscription = container.listen(profileControllerProvider, (_, _) {});
    addTearDown(subscription.close);
    expect(
      (await container.read(profileControllerProvider.future)).fullName,
      'Deniz Aydın',
    );

    await container.read(authControllerProvider.notifier).signOut();
    await container
        .read(authControllerProvider.notifier)
        .login(email: 'ayse@ornek.com', password: 'sifre');

    expect(
      (await container.read(profileControllerProvider.future)).fullName,
      'Ayşe Yılmaz',
    );
  });

  test('çıkış yapınca profil bellekte kalmıyor', () async {
    final session = _Session();
    final container = _container(session);

    await container
        .read(authControllerProvider.notifier)
        .login(email: 'deniz@ornek.com', password: 'sifre');
    final subscription = container.listen(profileControllerProvider, (_, _) {});
    addTearDown(subscription.close);
    await container.read(profileControllerProvider.future);

    await container.read(authControllerProvider.notifier).signOut();

    expect(container.read(authControllerProvider).value, isA<SignedOut>());
    expect(
      (await container.read(profileControllerProvider.future)).fullName,
      '—',
    );
  });

  group('açılışta sunucu cevap vermiyorsa', () {
    test('ağ hatası jetonu silmiyor', () async {
      // Etkinlik günü şebekesi zayıf olan katılımcı oturumunu kaybetmemeli:
      // sunucuya ulaşamamak bir kimlik kararı değil. Jeton silinseydi sunucu
      // geri geldiğinde şifresini yeniden girmek zorunda kalırdı.
      final session = _Session()..email = 'deniz@ornek.com';
      final container = _container(
        session,
        failWith: const ApiException('Sunucuya ulaşılamıyor.'),
      );

      final state = await container.read(authControllerProvider.future);

      expect(state, isA<SignedOut>());
      expect(lastAuthRepository!.loggedOut, isFalse);
      expect(session.email, 'deniz@ornek.com', reason: 'Jeton silinmiş.');
    });

    test('kimlik reddedildiyse jeton siliniyor', () async {
      final session = _Session()..email = 'deniz@ornek.com';
      final container = _container(
        session,
        failWith: const ApiException('Oturum süresi doldu.', statusCode: 401),
      );

      final state = await container.read(authControllerProvider.future);

      expect(state, isA<SignedOut>());
      expect(lastAuthRepository!.loggedOut, isTrue);
    });
  });

  test('yenileme tutmayınca oturum düşüyor', () async {
    // `ApiClient` jetonu siliyor ama uygulama hâlâ oturumu açık sanıyordu:
    // kullanıcı her ekranda hata görüp çıkışı elle bulmak zorunda kalıyordu.
    final session = _Session();
    final container = _container(session);

    await container
        .read(authControllerProvider.notifier)
        .login(email: 'deniz@ornek.com', password: 'sifre');
    expect(container.read(authControllerProvider).value, isA<SignedIn>());

    container.read(authControllerProvider.notifier).sessionExpired();
    await Future<void>.delayed(Duration.zero);

    expect(container.read(authControllerProvider).value, isA<SignedOut>());
  });
}
