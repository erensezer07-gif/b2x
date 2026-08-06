import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/auth/auth_controller.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'models.dart';
import 'profile_controller.dart';
import 'wizard/profile_wizard_screen.dart';

/// Profil özeti (şartname M2).
///
/// Sihirbaz bittikten sonra açılan ekran. İki şeyi gösteriyor:
///
/// * **Tamamlanma yüzdesi** — *"Eksik profil eşleştirmede kötü sonuç verir,
///   kullanıcının bunu bilmesi lazım."*
/// * **Başvuru yeterliliği** — eksikse neyin eksik olduğu yazılıyor.
///
/// Profil her zaman düzenlenebilir (M2), bu yüzden sihirbaza dönüş var.
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  static const routeName = 'profile';
  static const routePath = '/profil';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profileState = ref.watch(profileControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profilim'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Çıkış yap',
            onPressed: () => ref.read(authControllerProvider.notifier).signOut(),
          ),
        ],
      ),
      body: switch (profileState) {
        AsyncLoading() => const LoadingView(message: 'Profilin yükleniyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Profilin yüklenemedi.',
            onRetry: () => ref.invalidate(profileControllerProvider),
          ),
        AsyncData(:final value) => _ProfileBody(profile: value),
      },
    );
  }
}

class _ProfileBody extends StatelessWidget {
  const _ProfileBody({required this.profile});

  final Profile profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: AppSpacing.formMaxWidth),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _Header(profile: profile),
              const SizedBox(height: AppSpacing.lg),
              _CompletionCard(profile: profile),
              const SizedBox(height: AppSpacing.md),
              _ApplicationReadinessCard(profile: profile),
              const SizedBox(height: AppSpacing.lg),
              if (profile.offeredTags.isNotEmpty)
                _TagSection(title: 'Sunduklarım', tags: profile.offeredTags),
              if (profile.soughtTags.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.md),
                _TagSection(title: 'Aradıklarım', tags: profile.soughtTags),
              ],
              const SizedBox(height: AppSpacing.xl),
              OutlinedButton.icon(
                onPressed: () =>
                    context.goNamed(ProfileWizardScreen.routeName),
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Profili düzenle'),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                'Etkinlik listesi hazırlanıyor. Profilin tamamlandığında '
                'başvurabileceksin.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.profile});

  final Profile profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final subtitle = [
      profile.title,
      profile.company?.name,
    ].where((item) => item != null && item.isNotEmpty).join(' · ');

    return Row(
      children: [
        CircleAvatar(
          radius: 36,
          backgroundColor: theme.colorScheme.surfaceContainerHighest,
          foregroundImage:
              profile.photoUrl == null ? null : NetworkImage(profile.photoUrl!),
          onForegroundImageError: profile.photoUrl == null ? null : (_, _) {},
          child: Icon(
            Icons.person_outline,
            size: 32,
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                profile.fullName ?? 'Adın henüz girilmedi',
                style: theme.textTheme.titleLarge,
              ),
              if (subtitle.isNotEmpty)
                Text(subtitle, style: theme.textTheme.bodyMedium),
              if (profile.sector != null)
                Text(
                  profile.sector!.name,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CompletionCard extends StatelessWidget {
  const _CompletionCard({required this.profile});

  final Profile profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Profil tamamlanma', style: theme.textTheme.titleMedium),
                Text(
                  '%${profile.completionPercent}',
                  style: theme.textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            LinearProgressIndicator(value: profile.completionPercent / 100),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Eksik profil eşleştirmede daha zayıf sonuç verir.',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

/// Başvuru yeterliliği ve eksikler.
///
/// Şartname M2: *"Eksikse başvuru butonu çalışmaz ve neyin eksik olduğu
/// yazılır."* Eksik listesi sunucudan geliyor, Türkçe karşılığı burada.
class _ApplicationReadinessCard extends StatelessWidget {
  const _ApplicationReadinessCard({required this.profile});

  final Profile profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final ready = profile.canApply;

    return Card(
      margin: EdgeInsets.zero,
      color: ready ? colors.surfaceContainerHighest : colors.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  ready ? Icons.check_circle_outline : Icons.info_outline,
                  color: ready ? colors.onSurfaceVariant : colors.onErrorContainer,
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    ready
                        ? 'Etkinliklere başvurabilirsin'
                        : 'Başvurmak için eksikler var',
                    style: theme.textTheme.titleMedium?.copyWith(
                      color:
                          ready ? colors.onSurfaceVariant : colors.onErrorContainer,
                    ),
                  ),
                ),
              ],
            ),
            if (!ready) ...[
              const SizedBox(height: AppSpacing.sm),
              for (final requirement in profile.missingForApplication)
                Padding(
                  padding: const EdgeInsets.only(top: AppSpacing.xs),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.remove,
                        size: 16,
                        color: colors.onErrorContainer,
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: Text(
                          requirement.label,
                          style: theme.textTheme.bodyMedium
                              ?.copyWith(color: colors.onErrorContainer),
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class _TagSection extends StatelessWidget {
  const _TagSection({required this.title, required this.tags});

  final String title;
  final List<Tag> tags;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [for (final tag in tags) Chip(label: Text(tag.name))],
        ),
      ],
    );
  }
}
