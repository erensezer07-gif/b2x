import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/config/app_config.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'core/widgets/state_views.dart';

void main() {
  runApp(const ProviderScope(child: B2xApp()));
}

/// Uygulamanın kökü.
///
/// Tema tek bir dosyadan geliyor (`AppTheme`): görsel kimlik kararı verildiğinde
/// (şartname Bölüm 12, "Departure Board estetiği") yalnızca orası değişecek.
class B2xApp extends ConsumerWidget {
  const B2xApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Sunucu adresi olmadan hiçbir istek atılamaz; kullanıcıyı boş bir giriş
    // ekranında bırakmak yerine durum açıkça söyleniyor.
    if (!AppConfig.isConfigured) {
      return const _MissingConfigurationApp();
    }

    return MaterialApp.router(
      title: 'B2X',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      routerConfig: ref.watch(appRouterProvider),
      locale: const Locale('tr'),
      supportedLocales: const [Locale('tr')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
    );
  }
}

class _MissingConfigurationApp extends StatelessWidget {
  const _MissingConfigurationApp();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'B2X',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      locale: const Locale('tr'),
      supportedLocales: const [Locale('tr')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const Scaffold(
        body: ErrorView(
          message: 'Sunucu adresi tanımlı değil.\n\n'
              'Uygulama derlenirken API_BASE_URL verilmemiş. Adres koda gömülmez, '
              'dışarıdan verilir:\n\n'
              'flutter run --dart-define=API_BASE_URL=<sunucu adresi>',
        ),
      ),
    );
  }
}
