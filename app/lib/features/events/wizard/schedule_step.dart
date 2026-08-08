import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../profile/wizard/wizard_step.dart';
import '../event_controller.dart';
import '../models.dart';
import '../schedule.dart';

/// Adım 2 — program (şartname M4).
///
/// *"Slot süresi, mola süresi, slot sayısı. Girildikçe hesaplanan program anlık
/// gösterilir, bitiş saati görünür. Organizatör 'çok uzun sürüyor' diye anında
/// fark eder."*
///
/// Önizleme **istemcide** hesaplanıyor: her kaydırma hareketinde sunucuya gitmek
/// anlamsız olurdu. Kaydedilen programın doğrusu yine sunucudan geliyor; iki
/// tarafın formülü aynı senaryolarla test ediliyor.
class EventScheduleStep extends ConsumerStatefulWidget {
  const EventScheduleStep({
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
  ConsumerState<EventScheduleStep> createState() => _EventScheduleStepState();
}

class _EventScheduleStepState extends ConsumerState<EventScheduleStep> {
  late int _slotDuration;
  late int _breakDuration;
  late int _slotCount;

  bool _isSaving = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _slotDuration = widget.event.slotDurationMinutes;
    _breakDuration = widget.event.breakDurationMinutes;
    _slotCount = widget.event.slotCount;
  }

  Future<void> _saveAndContinue() async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      await ref.read(eventActionsProvider(widget.event.id)).save({
        'slot_duration_minutes': _slotDuration,
        'break_duration_minutes': _breakDuration,
        'slot_count': _slotCount,
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
    final preview = buildSchedule(
      startsAt: widget.event.startsAt,
      slotDurationMinutes: _slotDuration,
      breakDurationMinutes: _breakDuration,
      slotCount: _slotCount,
    );

    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: 'Program',
      description:
          'Kaç tur görüşme olacak, her tur ne kadar sürecek? Program aşağıda '
          'anında güncellenir.',
      isSaving: _isSaving,
      errorMessage: _errorMessage,
      onBack: widget.onBack,
      onNext: _saveAndContinue,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _NumberField(
            label: 'Tur sayısı',
            value: _slotCount,
            minimum: 1,
            maximum: 20,
            suffix: 'tur',
            enabled: !_isSaving,
            onChanged: (value) => setState(() => _slotCount = value),
          ),
          const SizedBox(height: AppSpacing.md),
          _NumberField(
            label: 'Tur süresi',
            value: _slotDuration,
            minimum: 1,
            maximum: 120,
            step: 1,
            suffix: 'dakika',
            enabled: !_isSaving,
            onChanged: (value) => setState(() => _slotDuration = value),
          ),
          const SizedBox(height: AppSpacing.md),
          _NumberField(
            label: 'Mola süresi',
            value: _breakDuration,
            minimum: 0,
            maximum: 60,
            step: 1,
            suffix: 'dakika',
            enabled: !_isSaving,
            onChanged: (value) => setState(() => _breakDuration = value),
          ),
          const SizedBox(height: AppSpacing.lg),
          _SchedulePreview(schedule: preview),
        ],
      ),
    );
  }
}

/// Artı-eksi düğmeli sayı alanı.
///
/// Klavye yerine düğme: mobilde sayı girmek zahmetli ve organizatör değerleri
/// deneyerek programın nasıl değiştiğine bakıyor.
class _NumberField extends StatelessWidget {
  const _NumberField({
    required this.label,
    required this.value,
    required this.minimum,
    required this.maximum,
    required this.suffix,
    required this.enabled,
    required this.onChanged,
    this.step = 1,
  });

  final String label;
  final int value;
  final int minimum;
  final int maximum;
  final int step;
  final String suffix;
  final bool enabled;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      children: [
        Expanded(child: Text(label, style: theme.textTheme.bodyLarge)),
        IconButton.outlined(
          onPressed: enabled && value > minimum
              ? () => onChanged((value - step).clamp(minimum, maximum))
              : null,
          icon: const Icon(Icons.remove),
          tooltip: '$label azalt',
        ),
        SizedBox(
          width: 96,
          child: Text(
            '$value $suffix',
            textAlign: TextAlign.center,
            style: theme.textTheme.titleMedium,
          ),
        ),
        IconButton.outlined(
          onPressed: enabled && value < maximum
              ? () => onChanged((value + step).clamp(minimum, maximum))
              : null,
          icon: const Icon(Icons.add),
          tooltip: '$label artır',
        ),
      ],
    );
  }
}

/// Hesaplanan programın önizlemesi.
class _SchedulePreview extends StatelessWidget {
  const _SchedulePreview({required this.schedule});

  final Schedule schedule;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Uzun programda liste ekranı doldurmasın; başı ve sonu yeterli.
    final showAll = schedule.slots.length <= 8;
    final visible = showAll
        ? schedule.slots
        : [...schedule.slots.take(3), ...schedule.slots.skip(schedule.slots.length - 2)];

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
                Text('Program', style: theme.textTheme.titleMedium),
                Text(
                  formatDuration(schedule.totalMinutes),
                  style: theme.textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            for (var index = 0; index < visible.length; index++) ...[
              if (!showAll && index == 3)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                  child: Text('⋮', style: theme.textTheme.bodyMedium),
                ),
              _SlotRow(slot: visible[index]),
            ],
            const Divider(height: AppSpacing.lg),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Bitiş', style: theme.textTheme.bodyLarge),
                Text(
                  formatTime(schedule.endsAt),
                  style: theme.textTheme.bodyLarge,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SlotRow extends StatelessWidget {
  const _SlotRow({required this.slot});

  final SlotTiming slot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text('Tur ${slot.number}', style: theme.textTheme.bodyMedium),
          Text(
            '${formatTime(slot.startsAt)} – ${formatTime(slot.endsAt)}',
            style: theme.textTheme.bodyMedium?.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}
