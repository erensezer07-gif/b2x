import 'package:flutter/material.dart';

import '../../core/widgets/state_views.dart';

/// Açılış ekranı.
///
/// Güvenli depodaki jeton okunup doğrulanana kadar burada beklenir. Bu adım
/// olmadan kullanıcı, oturumu açık olsa bile bir an giriş ekranını görürdü.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  static const routeName = 'splash';
  static const routePath = '/';

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: LoadingView(message: 'Oturum kontrol ediliyor'));
  }
}
