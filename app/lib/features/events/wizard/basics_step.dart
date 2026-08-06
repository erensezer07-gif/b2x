import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../profile/wizard/wizard_step.dart';
import '../event_controller.dart';
import '../models.dart';
import '../schedule.dart';

/// Adım 1 — temel bilgiler (şartname M4).
///
/// *"Temel bilgiler: ad, açıklama, tarih, saat, yer, kapak görseli."*
class EventBasicsStep extends ConsumerStatefulWidget {
  const EventBasicsStep({
    super.key,
    required this.event,
    required this.stepIndex,
    required this.stepCount,
    required this.onCompleted,
  });

  final EventDetail event;
  final int stepIndex;
  final int stepCount;
  final VoidCallback onCompleted;

  @override
  ConsumerState<EventBasicsStep> createState() => _EventBasicsStepState();
}

class _EventBasicsStepState extends ConsumerState<EventBasicsStep> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _description;
  late final TextEditingController _venue;
  late final TextEditingController _address;

  late DateTime _startsAt;
  bool _isSaving = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.event.name);
    _description = TextEditingController(text: widget.event.description ?? '');
    _venue = TextEditingController(text: widget.event.venueName ?? '');
    _address = TextEditingController(text: widget.event.address ?? '');
    _startsAt = widget.event.startsAt;
  }

  @override
  void dispose() {
    _name.dispose();
    _description.dispose();
    _venue.dispose();
    _address.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _startsAt,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 730)),
      helpText: 'Etkinlik tarihi',
    );
    if (picked == null) return;

    setState(() {
      _startsAt = DateTime(
        picked.year,
        picked.month,
        picked.day,
        _startsAt.hour,
        _startsAt.minute,
      );
    });
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(_startsAt),
      helpText: 'Başlangıç saati',
    );
    if (picked == null) return;

    setState(() {
      _startsAt = DateTime(
        _startsAt.year,
        _startsAt.month,
        _startsAt.day,
        picked.hour,
        picked.minute,
      );
    });
  }

  Future<void> _pickCover() async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      final picked = await ImagePicker().pickImage(
        source: ImageSource.gallery,
        maxWidth: 1600,
        maxHeight: 900,
        imageQuality: 85,
      );
      if (picked == null) return;

      final bytes = await picked.readAsBytes();
      await ref.read(eventActionsProvider(widget.event.id)).uploadCover(
            bytes: bytes,
            filename: picked.name,
            contentType: _contentTypeOf(picked.name, picked.mimeType),
          );
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _saveAndContinue() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      await ref.read(eventActionsProvider(widget.event.id)).save({
        'name': _name.text.trim(),
        'description': _emptyToNull(_description.text),
        'starts_at': _startsAt.toUtc().toIso8601String(),
        'venue_name': _emptyToNull(_venue.text),
        'address': _emptyToNull(_address.text),
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
    // Kapak yüklendikten sonra güncel hâli denetleyiciden geliyor.
    final event =
        ref.watch(eventDetailProvider(widget.event.id)).asData?.value ?? widget.event;

    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: 'Etkinlik bilgileri',
      description: 'Katılımcıların göreceği temel bilgiler.',
      isSaving: _isSaving,
      errorMessage: _errorMessage,
      onNext: _saveAndContinue,
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              controller: _name,
              enabled: !_isSaving,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Etkinlik adı'),
              validator: (value) =>
                  (value ?? '').trim().isEmpty ? 'Etkinlik adı gerekli.' : null,
            ),
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _isSaving ? null : _pickDate,
                    icon: const Icon(Icons.calendar_today_outlined),
                    label: Text(
                      '${_startsAt.day}.${_startsAt.month}.${_startsAt.year}',
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _isSaving ? null : _pickTime,
                    icon: const Icon(Icons.schedule_outlined),
                    label: Text(formatTime(_startsAt)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            TextFormField(
              controller: _venue,
              enabled: !_isSaving,
              decoration: const InputDecoration(
                labelText: 'Yer',
                hintText: 'İzmir Fuar Alanı',
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            TextFormField(
              controller: _address,
              enabled: !_isSaving,
              maxLines: 2,
              decoration: const InputDecoration(labelText: 'Adres'),
            ),
            const SizedBox(height: AppSpacing.md),
            TextFormField(
              controller: _description,
              enabled: !_isSaving,
              maxLines: 4,
              maxLength: 1000,
              decoration: const InputDecoration(labelText: 'Açıklama'),
            ),
            const SizedBox(height: AppSpacing.md),
            _CoverPicker(
              coverUrl: event.coverUrl,
              enabled: !_isSaving,
              onPick: _pickCover,
              onRemove: () =>
                  ref.read(eventActionsProvider(widget.event.id)).removeCover(),
            ),
          ],
        ),
      ),
    );
  }
}

class _CoverPicker extends StatelessWidget {
  const _CoverPicker({
    required this.coverUrl,
    required this.enabled,
    required this.onPick,
    required this.onRemove,
  });

  final String? coverUrl;
  final bool enabled;
  final VoidCallback onPick;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Kapak görseli', style: theme.textTheme.titleSmall),
        const SizedBox(height: AppSpacing.sm),
        AspectRatio(
          aspectRatio: 16 / 9,
          child: Container(
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(AppSpacing.sm),
              image: coverUrl == null
                  ? null
                  : DecorationImage(
                      image: NetworkImage(coverUrl!),
                      fit: BoxFit.cover,
                      // Adres kırıksa simge kalır, ekran çökmez.
                      onError: (_, _) {},
                    ),
            ),
            child: coverUrl != null
                ? null
                : Center(
                    child: Icon(
                      Icons.image_outlined,
                      size: AppSpacing.xl,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: enabled ? onPick : null,
                icon: const Icon(Icons.photo_library_outlined),
                label: Text(coverUrl == null ? 'Görsel seç' : 'Değiştir'),
              ),
            ),
            if (coverUrl != null) ...[
              const SizedBox(width: AppSpacing.sm),
              TextButton(
                onPressed: enabled ? onRemove : null,
                child: const Text('Kaldır'),
              ),
            ],
          ],
        ),
      ],
    );
  }
}

String? _emptyToNull(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}

String _contentTypeOf(String filename, String? reported) {
  if (reported != null && reported.startsWith('image/')) return reported;

  final lower = filename.toLowerCase();
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}
