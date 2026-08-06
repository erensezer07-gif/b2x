import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/auth_controller.dart';
import '../../core/theme/app_theme.dart';
import 'auth_form_scaffold.dart';
import 'register_screen.dart';

/// Giriş ekranı (şartname M1).
///
/// "Şifremi unuttum" bağlantısı bilerek yok: MVP'de e-posta gönderilmediği için
/// şifre sıfırlama akışı da yok (Bölüm 2). Çalışmayan bir bağlantı koymak,
/// kullanıcıyı boşuna umutlandırırdı.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  static const routeName = 'login';
  static const routePath = '/giris';

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;
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

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      await ref.read(authControllerProvider.notifier).login(
            email: _emailController.text.trim(),
            password: _passwordController.text,
          );
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
      title: 'Giriş yap',
      subtitle: 'Hesabınla devam et.',
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
                decoration: const InputDecoration(labelText: 'E-posta'),
                validator: (value) =>
                    (value ?? '').trim().isEmpty ? 'E-posta adresi gerekli.' : null,
              ),
              const SizedBox(height: AppSpacing.md),
              TextFormField(
                controller: _passwordController,
                enabled: !isSubmitting,
                obscureText: _obscurePassword,
                autofillHints: const [AutofillHints.password],
                textInputAction: TextInputAction.done,
                onFieldSubmitted: (_) => isSubmitting ? null : _submit(),
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
                validator: (value) =>
                    (value ?? '').isEmpty ? 'Şifre gerekli.' : null,
              ),
              const SizedBox(height: AppSpacing.lg),
              FilledButton(
                onPressed: isSubmitting ? null : _submit,
                child: isSubmitting
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Giriş yap'),
              ),
              const SizedBox(height: AppSpacing.md),
              TextButton(
                onPressed: isSubmitting
                    ? null
                    : () => context.goNamed(RegisterScreen.routeName),
                child: const Text('Hesabım yok, kayıt ol'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
