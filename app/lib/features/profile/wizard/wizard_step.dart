import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Sihirbaz adımlarının ortak iskeleti (şartname M2).
///
/// Sıra: temel bilgiler → şirket ve sektör → ne sunuyorum → ne arıyorum →
/// fotoğraf.
///
/// Her adım kendi verisini **kendisi kaydediyor**; "ileri" düğmesi kaydetmeden
/// geçmiyor. Kullanıcı yarıda bırakıp sonra devam edebilsin diye.
class WizardStepScaffold extends StatelessWidget {
  const WizardStepScaffold({
    super.key,
    required this.stepIndex,
    required this.stepCount,
    required this.title,
    required this.description,
    required this.child,
    required this.onNext,
    this.onBack,
    this.onSkip,
    this.nextLabel = 'İleri',
    this.isSaving = false,
    this.errorMessage,
  });

  final int stepIndex;
  final int stepCount;
  final String title;
  final String description;
  final Widget child;

  /// `null` ise ileri düğmesi kapalı — adımın koşulu sağlanmamış demektir.
  final VoidCallback? onNext;
  final VoidCallback? onBack;

  /// Yalnızca zorunlu olmayan adımlarda (fotoğraf) dolu.
  final VoidCallback? onSkip;

  final String nextLabel;
  final bool isSaving;
  final String? errorMessage;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text('Adım ${stepIndex + 1} / $stepCount'),
        leading: onBack == null
            ? null
            : IconButton(
                icon: const Icon(Icons.arrow_back),
                tooltip: 'Geri',
                onPressed: isSaving ? null : onBack,
              ),
        automaticallyImplyLeading: false,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: LinearProgressIndicator(value: (stepIndex + 1) / stepCount),
        ),
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: AppSpacing.formMaxWidth),
            child: Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(AppSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(title, style: theme.textTheme.headlineSmall),
                        const SizedBox(height: AppSpacing.xs),
                        Text(
                          description,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.lg),
                        if (errorMessage != null) ...[
                          _ErrorNote(message: errorMessage!),
                          const SizedBox(height: AppSpacing.md),
                        ],
                        child,
                      ],
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Column(
                    children: [
                      FilledButton(
                        onPressed: isSaving ? null : onNext,
                        child: isSaving
                            ? const SizedBox.square(
                                dimension: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : Text(nextLabel),
                      ),
                      if (onSkip != null)
                        TextButton(
                          onPressed: isSaving ? null : onSkip,
                          child: const Text('Bu adımı atla'),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ErrorNote extends StatelessWidget {
  const _ErrorNote({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: colors.errorContainer,
        borderRadius: BorderRadius.circular(AppSpacing.sm),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.error_outline, color: colors.onErrorContainer),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(message, style: TextStyle(color: colors.onErrorContainer)),
          ),
        ],
      ),
    );
  }
}
