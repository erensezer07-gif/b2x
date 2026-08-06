import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

/// Şifre gücü (şartname M1).
///
/// *"Kayıt ekranında şifre gücü için asgari kural uygulanır."*
///
/// Asgari kural sunucudaki ile aynı: en az sekiz karakter. Sunucu da bunu
/// doğruluyor — buradaki kontrol kullanıcıya anında geri bildirim vermek için,
/// güvenlik sınırı değil.
enum PasswordStrength {
  tooShort,
  weak,
  fair,
  strong;

  static const minimumLength = 8;

  static PasswordStrength of(String password) {
    if (password.length < minimumLength) return PasswordStrength.tooShort;

    var variety = 0;
    if (password.contains(RegExp(r'[a-zçğıöşü]'))) variety++;
    if (password.contains(RegExp(r'[A-ZÇĞİÖŞÜ]'))) variety++;
    if (password.contains(RegExp(r'[0-9]'))) variety++;
    if (password.contains(RegExp(r'[^A-Za-zÇĞİÖŞÜçğıöşü0-9]'))) variety++;

    if (password.length >= 12 && variety >= 3) return PasswordStrength.strong;
    if (variety >= 2) return PasswordStrength.fair;
    return PasswordStrength.weak;
  }

  bool get isAcceptable => this != PasswordStrength.tooShort;

  String get label => switch (this) {
        PasswordStrength.tooShort => 'En az $minimumLength karakter olmalı',
        PasswordStrength.weak => 'Zayıf',
        PasswordStrength.fair => 'Orta',
        PasswordStrength.strong => 'Güçlü',
      };

  double get ratio => switch (this) {
        PasswordStrength.tooShort => 0.15,
        PasswordStrength.weak => 0.4,
        PasswordStrength.fair => 0.7,
        PasswordStrength.strong => 1.0,
      };
}

/// Şifre gücünü çubuk ve metinle gösterir.
class PasswordStrengthIndicator extends StatelessWidget {
  const PasswordStrengthIndicator({super.key, required this.password});

  final String password;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final strength = PasswordStrength.of(password);

    final color = switch (strength) {
      PasswordStrength.tooShort => theme.colorScheme.error,
      PasswordStrength.weak => theme.colorScheme.error,
      PasswordStrength.fair => theme.colorScheme.tertiary,
      PasswordStrength.strong => theme.colorScheme.primary,
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LinearProgressIndicator(
          value: password.isEmpty ? 0 : strength.ratio,
          color: color,
          backgroundColor: theme.colorScheme.surfaceContainerHighest,
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          password.isEmpty ? 'Şifre gücü' : strength.label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: password.isEmpty ? theme.colorScheme.onSurfaceVariant : color,
          ),
        ),
      ],
    );
  }
}
