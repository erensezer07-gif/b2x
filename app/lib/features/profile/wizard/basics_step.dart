import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../models.dart';
import '../profile_controller.dart';
import 'wizard_step.dart';

/// Adım 1 — temel bilgiler (şartname M2).
///
/// Ad soyad başvuru için zorunlu; unvan, şehir ve tanıtım isteğe bağlı ama
/// tamamlanma yüzdesine giriyor.
class BasicsStep extends ConsumerStatefulWidget {
  const BasicsStep({
    super.key,
    required this.profile,
    required this.stepIndex,
    required this.stepCount,
    required this.onCompleted,
  });

  final Profile profile;
  final int stepIndex;
  final int stepCount;
  final VoidCallback onCompleted;

  @override
  ConsumerState<BasicsStep> createState() => _BasicsStepState();
}

class _BasicsStepState extends ConsumerState<BasicsStep> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _fullName;
  late final TextEditingController _title;
  late final TextEditingController _city;
  late final TextEditingController _bio;

  bool _isSaving = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    // Alanlar kayıtlı değerle açılıyor: kullanıcı yarıda bıraktıysa kaldığı
    // yerden devam etmeli (M2).
    _fullName = TextEditingController(text: widget.profile.fullName ?? '');
    _title = TextEditingController(text: widget.profile.title ?? '');
    _city = TextEditingController(text: widget.profile.city ?? '');
    _bio = TextEditingController(text: widget.profile.bio ?? '');
  }

  @override
  void dispose() {
    _fullName.dispose();
    _title.dispose();
    _city.dispose();
    _bio.dispose();
    super.dispose();
  }

  Future<void> _saveAndContinue() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      await ref.read(profileControllerProvider.notifier).save({
        'full_name': _fullName.text.trim(),
        'title': _emptyToNull(_title.text),
        'city': _emptyToNull(_city.text),
        'bio': _emptyToNull(_bio.text),
      });
      widget.onCompleted();
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: 'Seni tanıyalım',
      description:
          'Bu bilgiler masandaki kişilere gösterilir. Ad soyad başvuru için gerekli.',
      isSaving: _isSaving,
      errorMessage: _errorMessage,
      onNext: _saveAndContinue,
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              controller: _fullName,
              enabled: !_isSaving,
              textInputAction: TextInputAction.next,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Ad soyad',
                helperText: 'Başvuru için gerekli',
              ),
              validator: (value) =>
                  (value ?? '').trim().isEmpty ? 'Ad soyad gerekli.' : null,
            ),
            const SizedBox(height: AppSpacing.md),
            TextFormField(
              controller: _title,
              enabled: !_isSaving,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Unvan',
                hintText: 'Kurucu, Satış Müdürü, Danışman...',
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            TextFormField(
              controller: _city,
              enabled: !_isSaving,
              textInputAction: TextInputAction.next,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Şehir'),
            ),
            const SizedBox(height: AppSpacing.md),
            TextFormField(
              controller: _bio,
              enabled: !_isSaving,
              maxLines: 4,
              maxLength: 500,
              decoration: const InputDecoration(
                labelText: 'Kısa tanıtım',
                hintText: 'Ne iş yapıyorsun, neyle ilgileniyorsun?',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Boş metni `null` yapar.
///
/// Sunucuda "gönderilmedi" ile "boşalt" farklı: boş dize göndermek alanı boş
/// metinle doldururdu, oysa kullanıcı temizlemek istiyor.
String? _emptyToNull(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}
