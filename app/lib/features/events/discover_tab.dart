import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'event_controller.dart';
import 'models.dart';
import 'public_event_screen.dart';
import 'schedule.dart';

/// Keşfet yaprağı — yaklaşan etkinlikler (şartname M3).
///
/// *"Yaklaşan etkinliklerin listesi. Her kart: ad, tarih, yer, kalan
/// kontenjan, başvuru durumu."*
///
/// Kontenjanı dolmuş veya son tarihi geçmiş etkinlik listeden düşmüyor; kart
/// nedenini yazıyor. Sessizce kaybolmak kullanıcıyı şaşırtırdı.
class DiscoverTab extends ConsumerWidget {
  const DiscoverTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(discoverEventsProvider);

    return switch (events) {
      AsyncLoading() => const LoadingView(message: 'Etkinlikler yükleniyor'),
      AsyncError(:final error) => ErrorView(
          message: error is ApiException ? error.message : 'Etkinlikler yüklenemedi.',
          onRetry: () => ref.invalidate(discoverEventsProvider),
        ),
      AsyncData(:final value) when value.isEmpty => const EmptyView(
          icon: Icons.explore_outlined,
          message: 'Şu anda başvurulabilecek bir etkinlik yok.\n'
              'Yeni etkinlikler açıldığında burada görünecek.',
        ),
      AsyncData(:final value) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(discoverEventsProvider),
          child: ListView.builder(
            padding: const EdgeInsets.all(AppSpacing.md),
            itemCount: value.length,
            itemBuilder: (context, index) => _DiscoverCard(event: value[index]),
          ),
        ),
    };
  }
}

class _DiscoverCard extends StatelessWidget {
  const _DiscoverCard({required this.event});

  final DiscoverEvent event;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => context.goNamed(
          PublicEventScreen.routeName,
          pathParameters: {'eventId': '${event.id}'},
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(event.name, style: theme.textTheme.titleMedium),
              const SizedBox(height: AppSpacing.xs),
              Text(
                [
                  formatDate(event.startsAt),
                  if (event.venueName != null && event.venueName!.isNotEmpty)
                    event.venueName!,
                ].join(' · '),
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  RegistrationBadge(
                    status: event.myRegistration?.status,
                    closedReason: event.closedReason,
                  ),
                  const Spacer(),
                  Text(
                    event.isFull
                        ? '${event.capacity} kişilik'
                        : '${event.remainingCapacity} kontenjan',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Başvuru durumu rozeti (M3).
///
/// *"Başvuru durumları kullanıcıya net gösterilir: başvurmadı / beklemede /
/// kabul edildi / reddedildi."* Başvurulmamışsa ya "Başvuruya açık" ya da
/// kapalı olma sebebi yazıyor.
class RegistrationBadge extends StatelessWidget {
  const RegistrationBadge({super.key, this.status, this.closedReason});

  final RegistrationStatus? status;
  final String? closedReason;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    final (label, background, foreground, icon) = switch (status) {
      RegistrationStatus.accepted => (
          'Kabul edildi',
          colors.primaryContainer,
          colors.onPrimaryContainer,
          Icons.check_circle_outline,
        ),
      RegistrationStatus.pending => (
          'Beklemede',
          colors.tertiaryContainer,
          colors.onTertiaryContainer,
          Icons.hourglass_empty,
        ),
      RegistrationStatus.rejected => (
          'Reddedildi',
          colors.errorContainer,
          colors.onErrorContainer,
          Icons.cancel_outlined,
        ),
      // İptal edilen başvuru sunucudan `null` geliyor; bu dal yalnızca
      // eksiksizlik için.
      RegistrationStatus.cancelled || null => closedReason == null
          ? (
              'Başvuruya açık',
              colors.surfaceContainerHighest,
              colors.onSurfaceVariant,
              Icons.how_to_reg_outlined,
            )
          : (
              closedReason!,
              colors.surfaceContainerHighest,
              colors.onSurfaceVariant,
              Icons.lock_outline,
            ),
    };

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(AppSpacing.sm),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: AppSpacing.md, color: foreground),
          const SizedBox(width: AppSpacing.xs),
          Text(
            label,
            style: theme.textTheme.labelMedium?.copyWith(color: foreground),
          ),
        ],
      ),
    );
  }
}
