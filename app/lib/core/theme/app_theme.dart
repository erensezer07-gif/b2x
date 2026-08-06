import 'package:flutter/material.dart';

/// Uygulamanın tek tema kaynağı.
///
/// Hiçbir ekran renk, yazı tipi ölçeği veya aralık değerini kendi içine yazmaz;
/// hepsi buradan gelir. Sebep şartname Bölüm 12: görsel kimlik ("Departure Board
/// estetiği") henüz kararlaştırılmadı, ayrı bir tasarım notunda ele alınacak.
/// Karar verildiğinde yalnızca bu dosya değişecek, ekranlara dokunulmayacak.
///
/// Şu anki palet bilerek nötr: Material'ın varsayılan üretimi. Marka rengi
/// uydurmak, sonradan verilecek kararı zorlaştırırdı.
class AppTheme {
  const AppTheme._();

  /// Tema üretilirken kullanılan tohum renk.
  ///
  /// Departure Board kararı geldiğinde değişecek ilk yer burası.
  static const Color _seedColor = Color(0xFF2D3A4A);

  static ThemeData get light => _build(Brightness.light);

  static ThemeData get dark => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: _seedColor,
      brightness: brightness,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        // Hata metni iki satıra taşabiliyor; alan zıplamasın diye yer ayrılıyor.
        helperMaxLines: 2,
        errorMaxLines: 3,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(AppSpacing.buttonHeight),
        ),
      ),
    );
  }
}

/// Aralık ölçeği.
///
/// Ekranlarda çıplak sayı yazılmaz: `AppSpacing.md` yazmak, `16` yazmaktan hem
/// okunur hem de ölçek değiştiğinde tek yerden ayarlanabilir.
class AppSpacing {
  const AppSpacing._();

  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;

  /// Dokunma hedefi için asgari yükseklik.
  static const double buttonHeight = 48;

  /// Manuel salon editöründe bir ızgara hücresinin kenarı (şartname M5).
  ///
  /// Dokunma hedefinden (`buttonHeight`) geniş: parmakla sürüklerken masa
  /// parmağın altında kaybolmamalı. Sunucu piksel bilmez — hücre koordinatı
  /// tutar, ölçek yalnızca burada.
  static const double gridCell = 64;

  /// Formların okunur kaldığı azami genişlik — geniş ekranda satırlar uzamasın.
  static const double formMaxWidth = 440;
}
