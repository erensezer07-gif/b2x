import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/auth_controller.dart';
import '../../core/theme/app_theme.dart';
import 'auth_form_scaffold.dart';
import 'login_screen.dart';
import 'password_strength.dart';

/// Kayıt ekranı (şartname M1).
///
/// İki şey burada zorunlu:
///
/// * Şifre gücü için asgari kural.
/// * *"Şifrenizi unutursanız kurtarma seçeneği bulunmuyor"* uyarısı. MVP'de
///   e-posta gönderimi yok, dolayısıyla şifre sıfırlama da yok (Bölüm 2). Bu
///   bilinçli sadeleştirmenin bedelini kullanıcı kayıt olurken bilmeli.
class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  static const routeName = 'register';
  static const routePath = '/kayit';

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;
  bool _acknowledgedNoRecovery = false;
  bool _isSubmitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (!_acknowledgedNoRecovery) return;

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      await ref.read(authControllerProvider.notifier).register(
            email: _emailController.text.trim(),
            password: _passwordController.text,
          );
      // Başarılıysa yönlendirme oturum durumunu dinleyip ana ekrana geçiriyor;
      // burada gezinme çağrısı yapmaya gerek yok.
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSubmitting = _isSubmitting;

    return AuthFormScaffold(
      title: 'Hesap oluştur',
      subtitle: 'Etkinliklere başvurmak ve masanı öğrenmek için bir hesap gerekiyor.',
      children: [
        if (_errorMessage != null) FormErrorBanner(message: _errorMessage!),
        Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _emailController,
                enabled: !isSubmitting,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'E-posta',
                  hintText: 'ornek@sirket.com',
                ),
                validator: _validateEmail,
              ),
              const SizedBox(height: AppSpacing.md),
              TextFormField(
                controller: _passwordController,
                enabled: !isSubmitting,
                obscureText: _obscurePassword,
                autofillHints: const [AutofillHints.newPassword],
                decoration: InputDecoration(
                  labelText: 'Şifre',
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscurePassword ? Icons.visibility : Icons.visibility_off,
                    ),
                    tooltip: _obscurePassword ? 'Şifreyi göster' : 'Şifreyi gizle',
                    onPressed: () =>
                        setState(() => _obscurePassword = !_obscurePassword),
                  ),
                ),
                onChanged: (_) => setState(() {}),
                validator: _validatePassword,
              ),
              const SizedBox(height: AppSpacing.sm),
              PasswordStrengthIndicator(password: _passwordController.text),
              const SizedBox(height: AppSpacing.lg),
              _NoRecoveryWarning(
                acknowledged: _acknowledgedNoRecovery,
                onChanged: isSubmitting
                    ? null
                    : (value) => setState(() => _acknowledgedNoRecovery = value),
              ),
              const SizedBox(height: AppSpacing.lg),
              FilledButton(
                onPressed:
                    isSubmitting || !_acknowledgedNoRecovery ? null : _submit,
                child: isSubmitting
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Hesabı oluştur'),
              ),
              const SizedBox(height: AppSpacing.md),
              TextButton(
                onPressed: isSubmitting
                    ? null
                    : () => context.goNamed(LoginScreen.routeName),
                child: const Text('Zaten hesabım var, giriş yap'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

String? _validateEmail(String? value) {
  final email = (value ?? '').trim();
  if (email.isEmpty) return 'E-posta adresi gerekli.';
  if (!email.contains('@') || !email.contains('.')) {
    return 'Geçerli bir e-posta adresi gir.';
  }
  return null;
}

String? _validatePassword(String? value) {
  final password = value ?? '';
  if (password.isEmpty) return 'Şifre gerekli.';
  if (!PasswordStrength.of(password).isAcceptable) {
    return 'Şifre en az ${PasswordStrength.minimumLength} karakter olmalı.';
  }
  return null;
}

/// Şifre kurtarma olmadığını anlatan ve onay isteyen uyarı.
///
/// Onay kutusu işaretlenmeden kayıt düğmesi çalışmıyor: kullanıcı bu sonucu
/// gerçekten okumuş olmalı.
class _NoRecoveryWarning extends StatelessWidget {
  const _NoRecoveryWarning({required this.acknowledged, required this.onChanged});

  final bool acknowledged;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.sm),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.warning_amber_outlined, color: colors.onSurfaceVariant),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  'Şifreni unutursan kurtarma seçeneği bulunmuyor. '
                  'Bu sürümde şifre sıfırlama e-postası gönderilmiyor.',
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ],
          ),
          CheckboxListTile(
            value: acknowledged,
            onChanged: onChanged == null ? null : (value) => onChanged!(value ?? false),
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            title: const Text('Anladım, şifremi güvenli bir yerde saklayacağım'),
          ),
        ],
      ),
    );
  }
}
