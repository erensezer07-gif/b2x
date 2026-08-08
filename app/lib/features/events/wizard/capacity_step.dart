import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../profile/wizard/wizard_step.dart';
import '../event_controller.dart';
import '../models.dart';

/// Adım 3 — kontenjan (şartname M4).
///
/// *"Maksimum katılımcı sayısı, başvuru son tarihi, başvurular otomatik mi
/// kabul edilecek yoksa organizatör tek tek mi onaylayacak."*
class EventCapacityStep extends ConsumerStatefulWidget {
  const EventCapacityStep({
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
  ConsumerState<EventCapacityStep> createState() => _EventCapacityStepState();
}

class _EventCapacityStepState extends ConsumerState<EventCapacityStep> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _capacity;
  late bool _autoApprove;
  late int _requestQuota;
  DateTime? _deadline;

  bool _isSaving = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _capacity = TextEditingController(text: '${widget.event.capacity}');
    _autoApprove = widget.event.autoApproveRegistrations;
    _requestQuota = widget.event.requestQuota;
    _deadline = widget.event.registrationDeadline;
  }

  @override
  void dispose() {
    _capacity.dispose();
    super.dispose();
  }

  Future<void> _pickDeadline() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _deadline ?? widget.event.startsAt.subtract(const Duration(days: 7)),
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: widget.event.startsAt,
      helpText: 'Başvuru son tarihi',
    );
    if (picked != null) setState(() => _deadline = picked);
  }

  Future<void> _saveAndContinue() async {
    if (!_formKey.currentState!.validate()) return;

    final capacity = int.tryParse(_capacity.text.trim());
    if (capacity == null || capacity < 1) {
      setState(() => _errorMessage = 'Geçerli bir kontenjan gir.');
      return;
    }

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      await ref.read(eventActionsProvider(widget.event.id)).save({
        'capacity': capacity,
        'auto_approve_registrations': _autoApprove,
        'request_quota': _requestQuota,
        'registration_deadline': _deadline?.toUtc().toIso8601String(),
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
    final theme = Theme.of(context);

    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: 'Kontenjan ve başvurular',
      description: 'Kaç kişi katılabilir, başvurular nasıl kabul edilecek?',
      isSaving: _isSaving,
      errorMessage: _errorMessage,
      onBack: widget.onBack,
      onNext: _saveAndContinue,
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              controller: _capacity,
              enabled: !_isSaving,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Kontenjan *',
                suffixText: 'kişi',
                helperText: 'Salon kapasitesiyle karşılaştırması sonraki adımda',
              ),
              validator: (value) {
                final cap = int.tryParse((value ?? '').trim());
                if (cap == null || cap < 1) return 'Geçerli bir kontenjan gir (en az 1).';
                return null;
              },
            ),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton.icon(
            onPressed: _isSaving ? null : _pickDeadline,
            icon: const Icon(Icons.event_busy_outlined),
            label: Text(
              _deadline == null
                  ? 'Başvuru son tarihi seç'
                  : 'Son başvuru: ${_deadline!.day}.${_deadline!.month}.${_deadline!.year}',
            ),
          ),
          if (_deadline != null)
            TextButton(
              onPressed: _isSaving ? null : () => setState(() => _deadline = null),
              child: const Text('Son tarihi kaldır'),
            ),
          const SizedBox(height: AppSpacing.md),
          SwitchListTile(
            value: _autoApprove,
            onChanged: _isSaving ? null : (value) => setState(() => _autoApprove = value),
            contentPadding: EdgeInsets.zero,
            title: const Text('Başvuruları otomatik kabul et'),
            subtitle: Text(
              _autoApprove
                  ? 'Başvuranlar doğrudan katılımcı olur.'
                  : 'Her başvuruyu tek tek onaylarsın.',
              style: theme.textTheme.bodySmall,
            ),
          ),
          const Divider(height: AppSpacing.lg),
          Text('Görüşme talebi hakkı', style: theme.textTheme.titleSmall),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Her katılımcı bu kadar kişiye "görüşmek istiyorum" diyebilir. '
            'Sınır olmazsa herkes herkese talep atar ve tercihler anlamını yitirir.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: [
              Expanded(
                child: Slider(
                  value: _requestQuota.toDouble(),
                  min: 0,
                  max: 10,
                  divisions: 10,
                  label: '$_requestQuota',
                  onChanged: _isSaving
                      ? null
                      : (value) => setState(() => _requestQuota = value.round()),
                ),
              ),
              SizedBox(
                width: 56,
                child: Text(
                  '$_requestQuota',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.titleMedium,
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
