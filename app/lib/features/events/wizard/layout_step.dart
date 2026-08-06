import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/state_views.dart';
import '../../profile/wizard/wizard_step.dart';
import '../event_controller.dart';
import '../layout/layout_editor_screen.dart';
import '../models.dart';

/// Adım 4 — salon düzeni (şartname M5).
///
/// İki mod var. **Otomatik:** *"Organizatör sadece şunları girer: masa tipi,
/// masa sayısı, oturmalı ise sandalye sayısı, ayaklı ise alt ve üst kişi
/// sınırı. Sistem masaları oluşturur ve 1'den başlayarak numaralandırır. Görsel
/// kroki yoktur."*
///
/// **Manuel:** organizatör salonu ızgara üzerinde kurar. Tuval bu adıma
/// sığmıyor; ayrı tam ekran editöre geçiliyor.
class EventLayoutStep extends ConsumerStatefulWidget {
  const EventLayoutStep({
    super.key,
    required this.event,
    required this.stepIndex,
    required this.stepCount,
    required this.onCompleted,
    required this.onBack,
  });

  final EventDetail event;
  final int stepIndex;
  final int stepCount;
  final VoidCallback onCompleted;
  final VoidCallback onBack;

  @override
  ConsumerState<EventLayoutStep> createState() => _EventLayoutStepState();
}

class _EventLayoutStepState extends ConsumerState<EventLayoutStep> {
  TableKind _kind = TableKind.seated;
  int _tableCount = 10;
  int _seatCount = 6;
  int _minPeople = 3;
  int _maxPeople = 8;

  /// Seçilen mod; henüz seçilmediyse kurulu düzenden okunuyor.
  LayoutMode? _mode;

  bool _isSaving = false;
  String? _errorMessage;

  /// Manuel düzene geçip editörü açar (M5).
  ///
  /// Otomatik modda kurulmuş masalar korunuyor — sunucu onları ızgaraya
  /// diziyor, organizatör sürükleyerek düzeltiyor.
  Future<void> _openEditor({required bool alreadyManual}) async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      if (!alreadyManual) {
        await ref.read(eventActionsProvider(widget.event.id)).buildManualLayout(
              gridWidth: _defaultGridWidth,
              gridHeight: _defaultGridHeight,
            );
      }
      if (!mounted) return;
      context.goNamed(
        LayoutEditorScreen.routeName,
        pathParameters: {'eventId': '${widget.event.id}'},
      );
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _buildLayout() async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      final seated = _kind == TableKind.seated;
      await ref.read(eventActionsProvider(widget.event.id)).buildAutoLayout(
            kind: _kind,
            tableCount: _tableCount,
            seatCount: seated ? _seatCount : null,
            minPeople: seated ? null : _minPeople,
            maxPeople: seated ? null : _maxPeople,
          );
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _openRegistration() async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      await ref.read(eventActionsProvider(widget.event.id)).openRegistration();
      widget.onCompleted();
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final event =
        ref.watch(eventDetailProvider(widget.event.id)).asData?.value ?? widget.event;
    final layout = ref.watch(eventLayoutProvider(widget.event.id));
    final current = layout.asData?.value;
    final mode = _mode ?? current?.mode ?? LayoutMode.auto;

    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: 'Salon düzeni',
      description: mode == LayoutMode.auto
          ? 'Masaları oluştur. Numaralandırma 1\'den başlayarak yapılır.'
          : 'Salonu ızgara üzerinde kur. Masaları sürükleyerek yerleştir.',
      isSaving: _isSaving,
      errorMessage: _errorMessage,
      onBack: widget.onBack,
      // Kayıtları açmak salon düzeni gerektiriyor (M4, Bölüm 10). Düğme
      // kapalıyken de asıl kapı sunucuda: uç düzen yoksa reddediyor.
      onNext: event.canOpenRegistration ? _openRegistration : null,
      nextLabel: event.status == EventStatus.draft
          ? 'Kayıtları aç'
          : 'Etkinliğe dön',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SegmentedButton<LayoutMode>(
            segments: const [
              ButtonSegment(
                value: LayoutMode.auto,
                label: Text('Otomatik'),
                icon: Icon(Icons.format_list_numbered),
              ),
              ButtonSegment(
                value: LayoutMode.manual,
                label: Text('Manuel'),
                icon: Icon(Icons.grid_view_outlined),
              ),
            ],
            selected: {mode},
            onSelectionChanged: _isSaving
                ? null
                : (selection) => setState(() => _mode = selection.first),
          ),
          const SizedBox(height: AppSpacing.lg),
          if (mode == LayoutMode.auto)
            ..._autoControls(event)
          else
            _ManualCard(
              layout: current,
              enabled: !_isSaving,
              onOpen: () =>
                  _openEditor(alreadyManual: current?.mode == LayoutMode.manual),
            ),
          const SizedBox(height: AppSpacing.lg),
          switch (layout) {
            AsyncLoading() => const LoadingView(),
            AsyncError() => ErrorView(
                message: 'Salon düzeni yüklenemedi.',
                onRetry: () =>
                    ref.invalidate(eventLayoutProvider(widget.event.id)),
              ),
            AsyncData(value: null) => const EmptyView(
                icon: Icons.grid_view_outlined,
                message: 'Henüz salon düzeni kurulmadı.',
              ),
            AsyncData(:final value) => _LayoutSummary(
                layout: value!,
                capacity: event.capacitySummary,
              ),
          },
        ],
      ),
    );
  }

  /// Otomatik modun denetimleri.
  List<Widget> _autoControls(EventDetail event) {
    return [
      const _NumberingNote(),
      const SizedBox(height: AppSpacing.md),
      SegmentedButton<TableKind>(
        segments: const [
          ButtonSegment(
            value: TableKind.seated,
            label: Text('Oturmalı'),
            icon: Icon(Icons.event_seat_outlined),
          ),
          ButtonSegment(
            value: TableKind.standing,
            label: Text('Ayaklı'),
            icon: Icon(Icons.table_bar_outlined),
          ),
        ],
        selected: {_kind},
        onSelectionChanged: _isSaving
            ? null
            : (selection) => setState(() => _kind = selection.first),
      ),
      const SizedBox(height: AppSpacing.md),
      _Stepper(
        label: 'Masa sayısı',
        value: _tableCount,
        minimum: 1,
        maximum: 200,
        enabled: !_isSaving,
        onChanged: (value) => setState(() => _tableCount = value),
      ),
      if (_kind == TableKind.seated)
        _Stepper(
          label: 'Masa başına sandalye',
          value: _seatCount,
          minimum: 2,
          maximum: 20,
          enabled: !_isSaving,
          onChanged: (value) => setState(() => _seatCount = value),
        )
      else ...[
        _Stepper(
          label: 'En az kişi (hedef)',
          value: _minPeople,
          minimum: 2,
          maximum: 20,
          enabled: !_isSaving,
          onChanged: (value) => setState(() {
            _minPeople = value;
            if (_maxPeople < value) _maxPeople = value;
          }),
        ),
        _Stepper(
          label: 'En fazla kişi',
          value: _maxPeople,
          minimum: _minPeople,
          maximum: 30,
          enabled: !_isSaving,
          onChanged: (value) => setState(() => _maxPeople = value),
        ),
      ],
      const SizedBox(height: AppSpacing.md),
      FilledButton.tonalIcon(
        onPressed: _isSaving ? null : _buildLayout,
        icon: const Icon(Icons.grid_view_outlined),
        label: Text(
          event.hasLayout ? 'Masaları yeniden oluştur' : 'Masaları oluştur',
        ),
      ),
    ];
  }
}

/// Varsayılan ızgara — sunucudaki değerlerle aynı (Bölüm 12'de kapatılan karar).
const int _defaultGridWidth = 24;
const int _defaultGridHeight = 16;

/// Manuel moda geçiş kartı.
///
/// Geçiş kendiliğinden olmuyor: mevcut masalar korunacak ama bu yine de bir
/// değişiklik, organizatör düğmeye basarak onaylıyor.
class _ManualCard extends StatelessWidget {
  const _ManualCard({
    required this.layout,
    required this.enabled,
    required this.onOpen,
  });

  final EventLayout? layout;
  final bool enabled;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final alreadyManual = layout?.mode == LayoutMode.manual;
    final keptTables = alreadyManual ? 0 : (layout?.tables.length ?? 0);

    return Card(
      margin: EdgeInsets.zero,
      color: colors.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Salonu ızgara üzerinde kur',
              style: theme.textTheme.titleSmall,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              alreadyManual
                  ? '${layout!.gridWidth}×${layout!.gridHeight} hücrelik ızgara '
                      'kurulu. Masaları sürükleyerek yerleştir, sahne ve büfe '
                      'gibi işaretler ekle.'
                  : keptTables > 0
                      ? 'Kurulu $keptTables masa korunacak: numaraları ve '
                          'kapasiteleri aynı kalır, ızgaraya sırayla dizilir. '
                          'Sonra sürükleyerek yerlerini düzeltebilirsin.'
                      : 'Boş bir ızgara açılır. Araç çubuğundan masa seçip '
                          'tuvale dokunarak salonu kurarsın.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            FilledButton.tonalIcon(
              onPressed: enabled ? onOpen : null,
              icon: const Icon(Icons.open_in_full),
              label: Text(alreadyManual ? 'Salonu düzenle' : 'Manuel düzeni kur'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Otomatik modda kroki olmadığını hatırlatan not.
///
/// Şartname M5 bu metni açıkça istiyor: mod, organizatörün gerçek hayatta
/// masalara numara koyacağı varsayımına dayanıyor.
class _NumberingNote extends StatelessWidget {
  const _NumberingNote();

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
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline, color: colors.onSurfaceVariant),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              'Katılımcılar masa numarasıyla yerlerini bulacak. '
              'Salonda masalara numara koymayı unutmayın.',
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}

/// Oluşan masalar ve kapasite karşılaştırması.
class _LayoutSummary extends StatelessWidget {
  const _LayoutSummary({required this.layout, required this.capacity});

  final EventLayout layout;
  final CapacitySummary capacity;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _CapacityCard(capacity: capacity),
        const SizedBox(height: AppSpacing.md),
        Text('Masalar', style: theme.textTheme.titleSmall),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            for (final table in layout.tables)
              Chip(
                avatar: CircleAvatar(
                  backgroundColor: theme.colorScheme.primaryContainer,
                  child: Text(
                    '${table.number}',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onPrimaryContainer,
                    ),
                  ),
                ),
                label: Text(table.label ?? '${table.capacity} kişilik'),
              ),
          ],
        ),
      ],
    );
  }
}

/// Kontenjan ile salon kapasitesinin karşılaştırması (M4).
///
/// Kontenjan kapasiteyi aşarsa uyarı çıkar ama **engel değildir** — organizatör
/// gelmeyecekleri hesaba katıyor olabilir.
class _CapacityCard extends StatelessWidget {
  const _CapacityCard({required this.capacity});

  final CapacitySummary capacity;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final warn = capacity.exceedsSeating;

    return Card(
      margin: EdgeInsets.zero,
      color: warn ? colors.errorContainer : colors.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  warn ? Icons.warning_amber_outlined : Icons.check_circle_outline,
                  color: warn ? colors.onErrorContainer : colors.onSurfaceVariant,
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    '${capacity.tableCount} masa · '
                    '${capacity.seatingCapacity} kişilik salon',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color:
                          warn ? colors.onErrorContainer : colors.onSurfaceVariant,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              warn
                  ? 'Kontenjan ${capacity.capacity} kişi ama salon '
                      '${capacity.seatingCapacity} kişilik. Herkes aynı anda '
                      'oturamayabilir — gelmeyecekleri hesaba katıyorsan sorun değil.'
                  : 'Kontenjan ${capacity.capacity} kişi; salon yeterli.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: warn ? colors.onErrorContainer : colors.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Stepper extends StatelessWidget {
  const _Stepper({
    required this.label,
    required this.value,
    required this.minimum,
    required this.maximum,
    required this.enabled,
    required this.onChanged,
  });

  final String label;
  final int value;
  final int minimum;
  final int maximum;
  final bool enabled;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        children: [
          Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyLarge)),
          IconButton.outlined(
            onPressed:
                enabled && value > minimum ? () => onChanged(value - 1) : null,
            icon: const Icon(Icons.remove),
            tooltip: '$label azalt',
          ),
          SizedBox(
            width: 56,
            child: Text(
              '$value',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          IconButton.outlined(
            onPressed:
                enabled && value < maximum ? () => onChanged(value + 1) : null,
            icon: const Icon(Icons.add),
            tooltip: '$label artır',
          ),
        ],
      ),
    );
  }
}
