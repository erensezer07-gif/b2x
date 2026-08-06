import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../events/event_list_screen.dart';
import '../profile/profile_screen.dart';

/// Oturum açıldıktan sonraki ana kabuk.
///
/// Şartname Bölüm 7: *"Rol kullanıcıya değil, etkinliğe göre belirlenir: kendi
/// oluşturduğu etkinlikte organizatör, başvurduğu etkinlikte katılımcıdır."*
///
/// Bu yüzden ayrı bir "organizatör modu" yok. Tek bir Etkinlikler sekmesi var;
/// kullanıcı orada hem kendi düzenlediklerini görür hem (Aşama 6'dan sonra)
/// başvurabileceklerini.
class HomeShell extends StatelessWidget {
  const HomeShell({super.key, required this.navigationShell});

  /// go_router'ın dal durumunu taşıyan kabuk.
  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (index) => navigationShell.goBranch(
          index,
          // Aynı sekmeye tekrar dokunulunca o dalın köküne dönülür.
          initialLocation: index == navigationShell.currentIndex,
        ),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.event_outlined),
            selectedIcon: Icon(Icons.event),
            label: 'Etkinlikler',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Profilim',
          ),
        ],
      ),
    );
  }
}

/// Kabuğun dalları — yönlendirmede kullanılıyor.
class ShellBranch {
  const ShellBranch._();

  static const events = EventListScreen.routePath;
  static const profile = ProfileScreen.routePath;
}
