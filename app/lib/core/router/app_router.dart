import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/login_screen.dart';
import '../../features/auth/register_screen.dart';
import '../../features/events/event_list_screen.dart';
import '../../features/events/layout/layout_editor_screen.dart';
import '../../features/events/matching_screen.dart';
import '../../features/events/public_event_screen.dart';
import '../../features/events/registrations_screen.dart';
import '../../features/events/wizard/event_wizard_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/profile/wizard/profile_wizard_screen.dart';
import '../../features/shell/home_shell.dart';
import '../../features/splash/splash_screen.dart';
import '../auth/auth_controller.dart';

/// Uygulama yönlendirmesi ve oturum koruması.
///
/// Koruma burada, tek yerde: her ekranın kendi başına "oturum var mı" sorması
/// gerekmiyor. Ama bu yalnızca gezinme kolaylığı — **asıl görünürlük kuralları
/// sunucuda uygulanıyor** (şartname Bölüm 7). Arayüzde gizlemek yeterli değil.
final appRouterProvider = Provider<GoRouter>((ref) {
  final refreshOnAuthChange = _AuthChangeNotifier(ref);
  ref.onDispose(refreshOnAuthChange.dispose);

  final eventsBranchKey = GlobalKey<NavigatorState>(debugLabel: 'events');
  final profileBranchKey = GlobalKey<NavigatorState>(debugLabel: 'profile');

  return GoRouter(
    initialLocation: SplashScreen.routePath,
    refreshListenable: refreshOnAuthChange,
    redirect: (context, state) {
      final session = ref.read(authControllerProvider).asData?.value;
      final location = state.matchedLocation;

      // Depo henüz okunmadı: kimseyi bir yere gönderme, açılışta bekle.
      if (session == null) {
        return location == SplashScreen.routePath ? null : SplashScreen.routePath;
      }

      final atLogin = location == LoginScreen.routePath;
      final atRegister = location == RegisterScreen.routePath;
      final atSplash = location == SplashScreen.routePath;

      if (session is! SignedIn) {
        return atLogin || atRegister ? null : LoginScreen.routePath;
      }
      // Oturum açıkken giriş kapısında durmanın anlamı yok. Profil sihirbazı
      // ilk durak: profil eksikse orada kalınır, tamamsa özete geçer.
      return atLogin || atRegister || atSplash
          ? ProfileWizardScreen.routePath
          : null;
    },
    routes: <RouteBase>[
      GoRoute(
        path: SplashScreen.routePath,
        name: SplashScreen.routeName,
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: LoginScreen.routePath,
        name: LoginScreen.routeName,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: RegisterScreen.routePath,
        name: RegisterScreen.routeName,
        builder: (context, state) => const RegisterScreen(),
      ),
      // Sihirbaz kabuğun dışında: alt gezinme çubuğu adım adım ilerlerken
      // dikkat dağıtırdı ve yarım bırakılan profille etkinlik oluşturulmamalı.
      GoRoute(
        path: ProfileWizardScreen.routePath,
        name: ProfileWizardScreen.routeName,
        builder: (context, state) => const ProfileWizardScreen(),
      ),
      GoRoute(
        path: EventWizardScreen.routePath,
        name: EventWizardScreen.routeName,
        builder: (context, state) => EventWizardScreen(
          eventId: int.parse(state.pathParameters['eventId']!),
        ),
      ),
      // Manuel salon editörü tam ekran: tuval, araç çubuğu ve paneller
      // sihirbazın dar sütununa sığmaz (M5).
      GoRoute(
        path: LayoutEditorScreen.routePath,
        name: LayoutEditorScreen.routeName,
        builder: (context, state) => LayoutEditorScreen(
          eventId: int.parse(state.pathParameters['eventId']!),
        ),
      ),
      // Organizatörün başvuru onay ekranı (M3).
      GoRoute(
        path: RegistrationsScreen.routePath,
        name: RegistrationsScreen.routeName,
        builder: (context, state) => RegistrationsScreen(
          eventId: int.parse(state.pathParameters['eventId']!),
        ),
      ),
      // Eşleştirmeyi çalıştırma ekranı (M6).
      GoRoute(
        path: MatchingScreen.routePath,
        name: MatchingScreen.routeName,
        builder: (context, state) => MatchingScreen(
          eventId: int.parse(state.pathParameters['eventId']!),
        ),
      ),
      // Katılımcının gördüğü etkinlik detayı. Yolu `/etkinlikler` altında
      // değil: orası organizatörün sihirbazı, burası herkesin gördüğü yüz.
      GoRoute(
        path: PublicEventScreen.routePath,
        name: PublicEventScreen.routeName,
        builder: (context, state) => PublicEventScreen(
          eventId: int.parse(state.pathParameters['eventId']!),
        ),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            HomeShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            navigatorKey: eventsBranchKey,
            routes: [
              GoRoute(
                path: EventListScreen.routePath,
                name: EventListScreen.routeName,
                builder: (context, state) => const EventListScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            navigatorKey: profileBranchKey,
            routes: [
              GoRoute(
                path: ProfileScreen.routePath,
                name: ProfileScreen.routeName,
                builder: (context, state) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
});

/// Oturum durumu değişince yönlendirmeyi yeniden değerlendirtir.
///
/// go_router değişiklikleri `Listenable` üzerinden duyuyor; Riverpod ile
/// arasındaki köprü bu.
class _AuthChangeNotifier extends ChangeNotifier {
  _AuthChangeNotifier(Ref ref) {
    ref.listen(authControllerProvider, (_, _) => notifyListeners());
  }
}
