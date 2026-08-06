import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'check_in_screen.dart';
import 'event_controller.dart';
import 'event_list_screen.dart';
import 'models.dart';
import 'plan_screen.dart';
import 'schedule.dart';

/// Eşleştirmeyi çalıştırma ekranı (şartname M6, 5.4).
///
/// *"Organizatör kayıtları kapatır. 'Eşleştirmeyi çalıştır' butonu aktif olur.
/// Basınca iş kuyruğa girer, ekranda durum gösterilir. Bittiğinde plan
/// önizlemesi açılır."*
///
/// Önizlemenin kendisi `PlanScreen`'de (M7); burası çalıştırma ve versiyon
/// listesi.
class MatchingScreen extends ConsumerStatefulWidget {
  const MatchingScreen({super.key, required this.eventId});

  static const routeName = 'eventMatching';
  static const routePath = '/etkinlikler/:eventId/eslestirme';

  final int eventId;

  @override
  ConsumerState<MatchingScreen> createState() => _MatchingScreenState();
}

class _MatchingScreenState extends ConsumerState<MatchingScreen> {
  /// İzlenen plan. Çalıştırıldığı andan sonucu gelene kadar burada tutuluyor.
  PlanSummary? _plan;
  bool _starting = false;
  String? _error;

  /// Ekran kapandıysa yoklama durmalı; yoksa kapalı bir ekrana veri yazılır.
  bool _alive = true;

  @override
  void dispose() {
    _alive = false;
    super.dispose();
  }

  Future<void> _run({bool minimalChange = false}) async {
    setState(() {
      _starting = true;
      _error = null;
    });

    final actions = ref.read(matchingActionsProvider(widget.eventId));
    try {
      final started = await actions.run(minimalChange: minimalChange);
      if (!mounted) return;
      setState(() {
        _plan = started;
        _starting = false;
      });

      await actions.waitForResult(
        started.id,
        onUpdate: (plan) {
          if (mounted) setState(() => _plan = plan);
        },
        shouldContinue: () => _alive,
      );
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _error = error.message;
          _starting = false;
        });
      }
    }
  }

  void _openPlan(int planId) {
    context.goNamed(
      PlanScreen.routeName,
      pathParameters: {
        'eventId': '${widget.eventId}',
        'planId': '$planId',
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final check = ref.watch(matchingCheckProvider(widget.eventId));
    final plans = ref.watch(eventPlansProvider(widget.eventId));

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Etkinliklere dön',
          onPressed: () => context.goNamed(EventListScreen.routeName),
        ),
        title: const Text('Eşleştirme'),
      ),
      body: switch (check) {
        AsyncLoading() => const LoadingView(message: 'Kontrol listesi hazırlanıyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException
                ? error.message
                : 'Kontrol listesi yüklenemedi.',
            onRetry: () => ref.invalidate(matchingCheckProvider(widget.eventId)),
          ),
        AsyncData(:final value) => _buildBody(value, plans.asData?.value ?? const []),
      },
    );
  }

  Widget _buildBody(MatchingCheck check, List<PlanSummary> history) {
    final theme = Theme.of(context);
    // Ekranda izlenen plan yoksa en son çalıştırma gösteriliyor: kullanıcı
    // sayfayı yeniden açtığında sonucu kaybetmemeli.
    final current = _plan ?? (history.isNotEmpty ? history.first : null);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(matchingCheckProvider(widget.eventId));
        ref.invalidate(eventPlansProvider(widget.eventId));
      },
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          _Checklist(check: check),
          if (check.warnings.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            _Warnings(warnings: check.warnings),
          ],
          const SizedBox(height: AppSpacing.lg),
          _RunButton(
            check: check,
            busy: _starting || (current?.isPending ?? false),
            onRun: _run,
            hasRun: current != null,
          ),
          if (_error != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          // Check-in ekranı (M10). Eşleştirmeden ayrı bir iş ama aynı
          // etkinliğin kapısı; organizatör buradan giriyor.
          OutlinedButton.icon(
            onPressed: () => context.goNamed(
              CheckInScreen.routeName,
              pathParameters: {'eventId': '${widget.eventId}'},
            ),
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Girişte kod okut'),
          ),
          if (current != null) ...[
            const SizedBox(height: AppSpacing.lg),
            _PlanCard(
              plan: current,
              onOpen: () => _openPlan(current.id),
              // *"Organizatör 'planı güncelle' der."* (M10) Yalnızca
              // check-in başladıysa anlamlı; kapı sunucuda.
              onRefresh: (check.acceptedCount > 0 && current.hasResult)
                  ? () => _run(minimalChange: true)
                  : null,
            ),
          ],
          if (history.length > 1) ...[
            const SizedBox(height: AppSpacing.lg),
            Text('Önceki çalıştırmalar', style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.sm),
            for (final plan in history.skip(1))
              _HistoryRow(
                plan: plan,
                onOpen: plan.hasResult ? () => _openPlan(plan.id) : null,
              ),
          ],
        ],
      ),
    );
  }
}

/// *"Çalıştırma öncesi kontrol listesi gösterilir."* (M6)
class _Checklist extends StatelessWidget {
  const _Checklist({required this.check});

  final MatchingCheck check;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    final rows = <(IconData, String)>[
      (Icons.people_outline, '${check.acceptedCount} katılımcı kabul edildi'),
      (
        Icons.table_restaurant_outlined,
        '${check.tableCount} masa · ${check.seatingCapacity} kişilik kapasite',
      ),
      (Icons.forum_outlined, '${check.slotCount} tur'),
      (Icons.handshake_outlined, '${check.requestCount} görüşme talebi'),
      if (check.incompleteProfileCount > 0)
        (
          Icons.person_off_outlined,
          '${check.incompleteProfileCount} katılımcının profili eksik',
        ),
    ];

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Çalıştırmadan önce', style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.sm),
            for (final (icon, text) in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                child: Row(
                  children: [
                    Icon(icon, size: AppSpacing.lg, color: colors.onSurfaceVariant),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(child: Text(text, style: theme.textTheme.bodyMedium)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Uyarılar — engel değil (M6).
class _Warnings extends StatelessWidget {
  const _Warnings({required this.warnings});

  final List<MatchingWarning> warnings;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      color: colors.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.warning_amber_outlined, color: colors.onSurfaceVariant),
                const SizedBox(width: AppSpacing.sm),
                Text('Dikkat', style: theme.textTheme.titleSmall),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            for (final warning in warnings)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Text(
                  '• ${warning.message}',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
              ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Bunlar engel değil; yine de çalıştırabilirsin.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RunButton extends StatelessWidget {
  const _RunButton({
    required this.check,
    required this.busy,
    required this.onRun,
    required this.hasRun,
  });

  final MatchingCheck check;
  final bool busy;
  final VoidCallback onRun;
  final bool hasRun;

  @override
  Widget build(BuildContext context) {
    if (busy) {
      return const Center(child: CircularProgressIndicator());
    }

    // Düğme kapalıyken de asıl kapı sunucuda: uç iki kişiden az katılımcıyla
    // reddediyor.
    return FilledButton.icon(
      onPressed: check.canRun ? onRun : null,
      icon: const Icon(Icons.auto_awesome),
      label: Text(
        !check.canRun
            ? 'Eşleştirme için yeterli veri yok'
            : hasRun
                ? 'Yeniden çalıştır'
                : 'Eşleştirmeyi çalıştır',
      ),
    );
  }
}

/// Çalışan veya bitmiş planın durumu ve özeti.
class _PlanCard extends StatelessWidget {
  const _PlanCard({required this.plan, required this.onOpen, this.onRefresh});

  final PlanSummary plan;
  final VoidCallback onOpen;

  /// *"Gelmeyenler çıkarılmış halde tekrar çalıştır."* (M10, 9.8)
  final VoidCallback? onRefresh;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    final (icon, color, message) = switch (plan.jobStatus) {
      JobStatus.queued => (
          Icons.schedule,
          colors.onSurfaceVariant,
          'Sıraya alındı, birazdan başlayacak.',
        ),
      JobStatus.running => (
          Icons.autorenew,
          colors.primary,
          'Motor çalışıyor. Bu birkaç saniye sürebilir.',
        ),
      JobStatus.done => (
          Icons.check_circle_outline,
          colors.primary,
          plan.isPublished
              ? 'Plan yayında. Katılımcılar kendi masalarını görüyor.'
              : 'Plan hazır ve taslak olarak kaydedildi. Katılımcılar henüz '
                  'göremiyor.',
        ),
      JobStatus.failed => (
          Icons.error_outline,
          colors.error,
          plan.jobError ?? 'Eşleştirme tamamlanamadı.',
        ),
    };

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    'Versiyon ${plan.version} · ${plan.jobStatus.label}',
                    style: theme.textTheme.titleSmall,
                  ),
                ),
                if (plan.isPending)
                  const SizedBox(
                    width: AppSpacing.md,
                    height: AppSpacing.md,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: plan.jobStatus == JobStatus.failed
                    ? colors.error
                    : colors.onSurfaceVariant,
              ),
            ),
            if (plan.hasResult) ...[
              const Divider(height: AppSpacing.lg),
              _Summary(plan: plan),
              const SizedBox(height: AppSpacing.md),
              FilledButton.icon(
                onPressed: onOpen,
                icon: const Icon(Icons.grid_view_outlined),
                label: const Text('Planı incele ve düzelt'),
              ),
              if (onRefresh != null) ...[
                const SizedBox(height: AppSpacing.sm),
                OutlinedButton.icon(
                  onPressed: onRefresh,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Gelmeyenleri çıkar ve planı güncelle'),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

/// Hesap özeti (M7'nin özet panelinin çekirdeği).
class _Summary extends StatelessWidget {
  const _Summary({required this.plan});

  final PlanSummary plan;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    final rows = <(String, String)>[
      ('Toplam görüşme', '${plan.totalMeetings ?? 0}'),
      // Özet paneldeki en önemli sayı (M7): en kötü durumdaki kişi.
      ('En az görüşme alan', '${plan.minMeetingsPerPerson ?? 0} tur'),
      ('Masaya oturan', '${plan.participantCount} kişi'),
      (
        'Ortalama masa skoru',
        plan.averageTableScore == null
            ? '—'
            : plan.averageTableScore!.toStringAsFixed(2),
      ),
      ('Hesaplama süresi', '${plan.runtimeMs ?? 0} ms'),
      if (plan.unmatched.isNotEmpty)
        ('Hiç eşleşmeyen', '${plan.unmatched.length} kişi'),
    ];

    return Column(
      children: [
        for (final (label, value) in rows)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  label,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
                Text(value, style: theme.textTheme.bodyMedium),
              ],
            ),
          ),
      ],
    );
  }
}

class _HistoryRow extends StatelessWidget {
  const _HistoryRow({required this.plan, required this.onOpen});

  final PlanSummary plan;

  /// Hesabı bitmemiş plan açılamaz — gösterilecek bir şey yok.
  final VoidCallback? onOpen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return InkWell(
      onTap: onOpen,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Row(
          children: [
            Expanded(
              child: Text(
                'Versiyon ${plan.version} · ${formatDate(plan.createdAt)} '
                '${formatTime(plan.createdAt)}',
                style: theme.textTheme.bodyMedium,
              ),
            ),
            if (plan.status != PlanStatus.draft) ...[
              Text(
                plan.status.label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: plan.isPublished ? colors.primary : colors.onSurfaceVariant,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
            ],
            Text(
              plan.jobStatus == JobStatus.done
                  ? '${plan.totalMeetings ?? 0} görüşme'
                  : plan.jobStatus.label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
