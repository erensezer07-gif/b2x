import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'event_controller.dart';
import 'matching_screen.dart';
import 'models.dart';
import 'plan_widgets.dart';

/// Plan önizleme ve elle düzeltme (şartname M7).
///
/// *"Slot seçici üstte. Seçili slot için tüm masalar ve kimlerin oturduğu
/// listelenir."*
///
/// ## Takas neden dokun-dokun
///
/// *"Bir kişiye dokunulur, sonra ikinci kişiye dokunulur, yerleri değişir."*
/// Sürükle-bırak mobilde kaygan: liste kayarken yanlış hedefe bırakmak kolay.
/// İki dokunuş aynı işi görüyor ve iptal edilebiliyor.
///
/// ## Görünüm nereden geliyor
///
/// Takas ve sabitleme uçları güncel görünümü **geri döndürüyor**; ekran onu
/// doğrudan gösteriyor. Sağlayıcıyı bekleseydi liste bir an eski hâline döner,
/// seçim kaybolurdu. Sağlayıcı yine de tazeleniyor: tura geri dönüldüğünde
/// taze veri bulunmalı.
class PlanScreen extends ConsumerStatefulWidget {
  const PlanScreen({super.key, required this.eventId, required this.planId});

  static const routeName = 'eventPlan';
  static const routePath = '/etkinlikler/:eventId/plan/:planId';

  final int eventId;
  final int planId;

  @override
  ConsumerState<PlanScreen> createState() => _PlanScreenState();
}

class _PlanScreenState extends ConsumerState<PlanScreen> {
  int _slotNumber = 1;

  /// Takastan sonra uçtan gelen taze görünüm.
  ///
  /// Sağlayıcının değerini geçersiz kılıyor. Tur değişince sıfırlanıyor.
  SlotView? _fresh;

  /// Takasın ilk dokunuşu: seçili atama.
  int? _selected;

  List<SwapWarning> _warnings = const [];
  String? _error;
  bool _busy = false;

  PlanQuery get _plan => PlanQuery(widget.eventId, widget.planId);
  SlotQuery get _slot => SlotQuery(widget.eventId, widget.planId, _slotNumber);

  void _selectSlot(int number) {
    if (number == _slotNumber) return;
    setState(() {
      _slotNumber = number;
      _fresh = null;
      _selected = null;
      _warnings = const [];
      _error = null;
    });
  }

  /// Bir kişiye dokunma.
  ///
  /// İlk dokunuş seçer, ikincisi takas eder. Aynı kişiye tekrar dokunmak
  /// seçimi bırakıyor — yanlışlıkla başlayan bir takas çıkmaz sokak olmamalı.
  void _tapPerson(SeatedPerson person) {
    if (_busy) return;
    if (_selected == person.assignmentId) {
      setState(() => _selected = null);
      return;
    }
    if (_selected == null) {
      setState(() {
        _selected = person.assignmentId;
        _warnings = const [];
        _error = null;
      });
      return;
    }
    _swap(targetAssignmentId: person.assignmentId);
  }

  /// Boş bir sandalyeye dokunma: seçili kişi oraya taşınıyor.
  void _tapTable(SeatedTable table) {
    if (_busy || _selected == null) return;
    _swap(targetTableId: table.tableId);
  }

  Future<void> _swap({int? targetAssignmentId, int? targetTableId}) async {
    final moving = _selected;
    if (moving == null) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final result = await ref.read(planEditActionsProvider(_plan)).swap(
            slotNumber: _slotNumber,
            assignmentId: moving,
            targetAssignmentId: targetAssignmentId,
            targetTableId: targetTableId,
          );
      if (!mounted) return;
      setState(() {
        _fresh = result.slot;
        _warnings = result.warnings;
        _selected = null;
        _busy = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      // Ret (sabitlenmiş atama) uyarı değil hata: takas hiç olmadı.
      setState(() {
        _error = error.message;
        _selected = null;
        _busy = false;
      });
    }
  }

  Future<void> _togglePin(SeatedPerson person) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final slot = await ref.read(planEditActionsProvider(_plan)).setPinned(
            slotNumber: _slotNumber,
            assignmentId: person.assignmentId,
            isPinned: !person.isPinned,
          );
      if (!mounted) return;
      setState(() {
        _fresh = slot;
        _busy = false;
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _busy = false;
      });
    }
  }

  Future<void> _publish() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Planı yayınla'),
        content: const Text(
          'Katılımcılar kendi masalarını ve görüşecekleri kişileri görmeye '
          'başlayacak. Varsa önceki yayındaki plan arşive geçecek.\n\n'
          'Yayınladıktan sonra da düzeltebilirsin; düzeltme anında yansır.',
        ),
        actions: [
          TextButton(
            onPressed: () => context.pop(false),
            child: const Text('Vazgeç'),
          ),
          FilledButton(
            onPressed: () => context.pop(true),
            child: const Text('Yayınla'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await ref.read(planEditActionsProvider(_plan)).publish();
      if (!mounted) return;
      setState(() => _busy = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Plan yayınlandı.')),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final plan = ref.watch(planProvider(_plan));
    final event = ref.watch(eventDetailProvider(widget.eventId));
    final slot = ref.watch(planSlotProvider(_slot));
    final summary = plan.asData?.value;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Eşleştirmeye dön',
          onPressed: () => context.goNamed(
            MatchingScreen.routeName,
            pathParameters: {'eventId': '${widget.eventId}'},
          ),
        ),
        title: Text(
          summary == null ? 'Plan' : 'Plan · Versiyon ${summary.version}',
        ),
        actions: [
          if (summary?.isPublished ?? false)
            Padding(
              padding: const EdgeInsets.only(right: AppSpacing.md),
              child: Chip(
                avatar: const Icon(Icons.public, size: AppSpacing.md),
                label: const Text('Yayında'),
                visualDensity: VisualDensity.compact,
              ),
            ),
        ],
      ),
      body: switch ((plan, event)) {
        (AsyncError(:final error), _) || (_, AsyncError(:final error)) => ErrorView(
            message: error is ApiException ? error.message : 'Plan yüklenemedi.',
            onRetry: () {
              ref.invalidate(planProvider(_plan));
              ref.invalidate(eventDetailProvider(widget.eventId));
            },
          ),
        (AsyncData(value: final summary), AsyncData(value: final detail)) =>
          _buildBody(summary, detail, slot),
        _ => const LoadingView(message: 'Plan yükleniyor'),
      },
      bottomNavigationBar: switch (plan) {
        AsyncData(value: final summary) => _PublishBar(
            plan: summary,
            busy: _busy,
            onPublish: _publish,
          ),
        _ => null,
      },
    );
  }

  Widget _buildBody(PlanSummary plan, EventDetail event, AsyncValue<SlotView> slot) {
    final view = _fresh ?? slot.asData?.value;

    return Column(
      children: [
        SlotSelector(
          slotCount: event.slotCount,
          selected: _slotNumber,
          onSelect: _busy ? null : _selectSlot,
        ),
        if (_busy) const LinearProgressIndicator(minHeight: 2),
        Expanded(
          child: switch (view) {
            null when slot is AsyncError => ErrorView(
                message: slot.error is ApiException
                    ? (slot.error! as ApiException).message
                    : 'Tur yüklenemedi.',
                onRetry: () => ref.invalidate(planSlotProvider(_slot)),
              ),
            null => const LoadingView(message: 'Tur yükleniyor'),
            final loaded when loaded.tables.isEmpty => const EmptyView(
                icon: Icons.table_restaurant_outlined,
                message: 'Bu etkinlikte masa yok. Salon düzenini kurmadan '
                    'plan gösterilemez.',
              ),
            final loaded => _buildSlot(plan, loaded),
          },
        ),
      ],
    );
  }

  Widget _buildSlot(PlanSummary plan, SlotView view) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        PlanSummaryPanel(plan: plan),
        if (_error != null) ...[
          const SizedBox(height: AppSpacing.md),
          SwapErrorBanner(
            message: _error!,
            onDismiss: () => setState(() => _error = null),
          ),
        ],
        if (_warnings.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          SwapWarningBanner(
            warnings: _warnings,
            onDismiss: () => setState(() => _warnings = const []),
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        SwapHint(
          selected: _selected == null ? null : _nameOf(view, _selected!),
          onCancel: () => setState(() => _selected = null),
        ),
        const SizedBox(height: AppSpacing.md),
        for (final table in view.tables)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: TableCard(
              table: table,
              selectedAssignmentId: _selected,
              // Boş masaya ancak elde bir kişi varken dokunulabilir.
              onTapTable: _selected == null ? null : () => _tapTable(table),
              onTapPerson: _tapPerson,
              onTogglePin: _togglePin,
            ),
          ),
      ],
    );
  }

  String _nameOf(SlotView view, int assignmentId) {
    for (final table in view.tables) {
      for (final person in table.occupants) {
        if (person.assignmentId == assignmentId) return person.displayName;
      }
    }
    return 'Seçili kişi';
  }
}

/// Yayınlama çubuğu.
///
/// Alt çubukta: ekranın her yerinden erişilebilir olmalı ama masaların arasına
/// karışmamalı.
class _PublishBar extends StatelessWidget {
  const _PublishBar({
    required this.plan,
    required this.busy,
    required this.onPublish,
  });

  final PlanSummary plan;
  final bool busy;
  final VoidCallback onPublish;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              plan.isPublished
                  ? 'Katılımcılar bu planı görüyor.'
                  : 'Plan taslak. Katılımcılar henüz hiçbir şey göremiyor.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            FilledButton.icon(
              onPressed: busy ? null : onPublish,
              icon: const Icon(Icons.public),
              label: Text(plan.isPublished ? 'Yeniden yayınla' : 'Planı yayınla'),
            ),
          ],
        ),
      ),
    );
  }
}
