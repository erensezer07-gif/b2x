import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'event_controller.dart';
import 'event_list_screen.dart';
import 'models.dart';
import 'schedule.dart';

/// Organizatörün başvuru yönetimi (şartname Aşama 6).
///
/// Her satırda başvuranın fotoğrafı, adı, unvanı, şirketi ve sektörü var:
/// organizatör kimi kabul ettiğini görmeden karar veremez. Bölüm 7 buna izin
/// veriyor — *"organizatör kendi etkinliğinin her şeyini görür."*
///
/// Süzgeç sunucuda uygulanıyor, listede değil: yüzlerce başvuruyu istemciye
/// indirip orada elemek gereksiz.
class RegistrationsScreen extends ConsumerStatefulWidget {
  const RegistrationsScreen({super.key, required this.eventId});

  static const routeName = 'eventRegistrations';
  static const routePath = '/etkinlikler/:eventId/basvurular';

  final int eventId;

  @override
  ConsumerState<RegistrationsScreen> createState() => _RegistrationsScreenState();
}

class _RegistrationsScreenState extends ConsumerState<RegistrationsScreen> {
  /// `null` = iptal edilenler hariç hepsi.
  RegistrationStatus? _filter;

  /// İşlem sürerken hangi satır bekliyor — yalnızca o satırın düğmeleri kapanır.
  int? _busyRow;

  Future<void> _decide(
    int registrationId,
    Future<RegistrationSummary> Function(int) action,
  ) async {
    setState(() => _busyRow = registrationId);
    try {
      await action(registrationId);
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _busyRow = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final query = RegistrationQuery(widget.eventId, _filter);
    final summary = ref.watch(eventRegistrationsProvider(query));

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Etkinliklere dön',
          onPressed: () => context.goNamed(EventListScreen.routeName),
        ),
        title: const Text('Başvurular'),
      ),
      body: switch (summary) {
        AsyncLoading() => const LoadingView(message: 'Başvurular yükleniyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Başvurular yüklenemedi.',
            onRetry: () => ref.invalidate(eventRegistrationsProvider(query)),
          ),
        AsyncData(:final value) => _buildList(value),
      },
    );
  }

  Widget _buildList(RegistrationSummary summary) {
    final actions = ref.read(registrationActionsProvider(widget.eventId));

    return Column(
      children: [
        _Summary(summary: summary),
        _Filters(
          selected: _filter,
          summary: summary,
          onChanged: (value) => setState(() => _filter = value),
        ),
        const Divider(height: 1),
        Expanded(
          child: summary.registrations.isEmpty
              ? EmptyView(
                  icon: Icons.how_to_reg_outlined,
                  message: _filter == null
                      ? 'Bu etkinliğe henüz başvuru yok.'
                      : 'Bu süzgeçte başvuru yok.',
                )
              : RefreshIndicator(
                  onRefresh: () async => ref.invalidate(
                    eventRegistrationsProvider(RegistrationQuery(widget.eventId, _filter)),
                  ),
                  child: ListView.separated(
                    padding: const EdgeInsets.all(AppSpacing.md),
                    itemCount: summary.registrations.length,
                    separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.sm),
                    itemBuilder: (context, index) {
                      final registration = summary.registrations[index];
                      return _ApplicantCard(
                        registration: registration,
                        busy: _busyRow == registration.id,
                        // Kontenjan doluyken onay düğmesi kapalı; asıl kapı
                        // sunucuda, uç da reddediyor.
                        canApprove: !summary.isFull ||
                            registration.status == RegistrationStatus.accepted,
                        onApprove: () => _decide(registration.id, actions.approve),
                        onReject: () => _decide(registration.id, actions.reject),
                      );
                    },
                  ),
                ),
        ),
      ],
    );
  }
}

/// Kontenjan ve sayılar.
class _Summary extends StatelessWidget {
  const _Summary({required this.summary});

  final RegistrationSummary summary;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.sm,
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '${summary.acceptedCount} / ${summary.capacity} kabul edildi',
              style: theme.textTheme.titleMedium,
            ),
          ),
          if (summary.isFull)
            Text(
              'Kontenjan doldu',
              style: theme.textTheme.labelLarge?.copyWith(color: colors.error),
            )
          else
            Text(
              '${summary.remainingCapacity} yer kaldı',
              style: theme.textTheme.labelLarge?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
        ],
      ),
    );
  }
}

class _Filters extends StatelessWidget {
  const _Filters({
    required this.selected,
    required this.summary,
    required this.onChanged,
  });

  final RegistrationStatus? selected;
  final RegistrationSummary summary;
  final ValueChanged<RegistrationStatus?> onChanged;

  @override
  Widget build(BuildContext context) {
    final options = <(String, RegistrationStatus?)>[
      ('Hepsi', null),
      ('Bekleyen (${summary.pendingCount})', RegistrationStatus.pending),
      ('Kabul (${summary.acceptedCount})', RegistrationStatus.accepted),
      ('Red (${summary.rejectedCount})', RegistrationStatus.rejected),
    ];

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
      child: Row(
        children: [
          for (final (label, status) in options) ...[
            ChoiceChip(
              label: Text(label),
              selected: selected == status,
              onSelected: (_) => onChanged(status),
            ),
            const SizedBox(width: AppSpacing.sm),
          ],
        ],
      ),
    );
  }
}

/// Başvuran satırı: profil özeti ve karar düğmeleri.
class _ApplicantCard extends StatelessWidget {
  const _ApplicantCard({
    required this.registration,
    required this.busy,
    required this.canApprove,
    required this.onApprove,
    required this.onReject,
  });

  final EventRegistration registration;
  final bool busy;
  final bool canApprove;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final applicant = registration.applicant;
    final accepted = registration.status == RegistrationStatus.accepted;
    final rejected = registration.status == RegistrationStatus.rejected;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: AppSpacing.lg,
                  backgroundColor: colors.surfaceContainerHighest,
                  foregroundImage: applicant.photoUrl == null
                      ? null
                      : NetworkImage(applicant.photoUrl!),
                  child: Icon(Icons.person_outline, color: colors.onSurfaceVariant),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(applicant.displayName, style: theme.textTheme.titleSmall),
                      if (applicant.subtitle.isNotEmpty)
                        Text(
                          applicant.subtitle,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: colors.onSurfaceVariant,
                          ),
                        ),
                      if (applicant.sector != null)
                        Text(
                          applicant.sector!.name,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colors.onSurfaceVariant,
                          ),
                        ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        '${formatDate(registration.appliedAt)} tarihinde başvurdu',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            if (busy)
              const Center(
                child: SizedBox(
                  width: AppSpacing.lg,
                  height: AppSpacing.lg,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              )
            else
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: rejected ? null : onReject,
                      icon: const Icon(Icons.close),
                      label: Text(rejected ? 'Reddedildi' : 'Reddet'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: rejected ? null : colors.error,
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: (accepted || !canApprove) ? null : onApprove,
                      icon: const Icon(Icons.check),
                      label: Text(
                        accepted
                            ? 'Kabul edildi'
                            : canApprove
                                ? 'Kabul et'
                                : 'Kontenjan dolu',
                      ),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
