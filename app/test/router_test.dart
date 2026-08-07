// Açılışta istenen adres korunuyor mu (şartname Bölüm 0'ın "web de hedef
// platform" kararı).
//
// Tarayıcı turunda yakalandı: web'de herhangi bir sayfada sayfa yenilendiğinde
// kullanıcı profil sihirbazında buluyordu kendini. Sebep yönlendirme sırası —
// güvenli depo okunana kadar herkes açılış ekranına gidiyor, oturum çözülünce
// oradan sihirbaza atlanıyor ve istenen adres yolda düşüyordu.

import 'dart:async';

import 'package:b2x/core/auth/auth_controller.dart';
import 'package:b2x/core/auth/auth_repository.dart';
import 'package:b2x/core/router/app_router.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

/// Oturumu testin açtığı denetleyici.
///
/// `build()` tamamen değiştiriliyor: gerçek olan güvenli depoya ve `/auth/me`
/// çağrısına bakıyor, testin derdi yalnızca **ne zaman** çözüldüğü.
class _GatedAuth extends AuthController {
  _GatedAuth(this._gate);

  final Future<AuthState> _gate;

  @override
  Future<AuthState> build() => _gate;
}

/// Yönlendiriciyi kurar ve istenen adrese gider.
///
/// Adres oturum **çözülmeden önce** isteniyor: hatanın çıktığı an tam olarak
/// bu. Sonra kapı açılıyor ve nereye varıldığına bakılıyor.
Future<String> _resume(
  WidgetTester tester, {
  required String requested,
  required AuthState session,
}) async {
  final gate = Completer<AuthState>();
  final container = ProviderContainer(
    overrides: [authControllerProvider.overrideWith(() => _GatedAuth(gate.future))],
  );
  addTearDown(container.dispose);

  final router = container.read(appRouterProvider);
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp.router(routerConfig: router),
    ),
  );

  router.go(requested);
  await tester.pump();

  gate.complete(session);
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));

  return router.routerDelegate.currentConfiguration.uri.toString();
}

void main() {
  testWidgets('oturum çözülünce istenen adrese devam ediliyor', (tester) async {
    final landed = await _resume(
      tester,
      requested: '/etkinlikler/15/eslestirme',
      session: const SignedIn(Account(id: 1, email: 'deniz@ornek.com')),
    );

    expect(landed, '/etkinlikler/15/eslestirme');
  });

  testWidgets('sorgu dizesi de korunuyor', (tester) async {
    // `matchedLocation` sorguyu taşımıyor; süzgeçli bir listeye yenilenen
    // sayfa süzgecini kaybederdi.
    final landed = await _resume(
      tester,
      requested: '/kesfet/15/katilimcilar?sektor=3',
      session: const SignedIn(Account(id: 1, email: 'ayse@ornek.com')),
    );

    expect(landed, '/kesfet/15/katilimcilar?sektor=3');
  });

  testWidgets('oturum yoksa giriş ekranına gidiliyor', (tester) async {
    final landed = await _resume(
      tester,
      requested: '/etkinlikler/15/eslestirme',
      session: const SignedOut(),
    );

    expect(landed, '/giris');
  });

  testWidgets('adres istenmemişse sihirbaza gidiliyor', (tester) async {
    // Uygulamayı kökten açan kullanıcı: bekleyen bir adres yok.
    final landed = await _resume(
      tester,
      requested: '/',
      session: const SignedIn(Account(id: 1, email: 'deniz@ornek.com')),
    );

    expect(landed, '/profil/sihirbaz');
  });
}
