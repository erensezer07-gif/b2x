import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/app_theme.dart';
import '../models.dart';

/// Kaydetme sonucunu bildiren geri çağrı.
///
/// Hata **mesaj olarak** dönüyor, fırlatılmıyor: panel onu kendi içinde
/// gösteriyor. Paylaşılan duruma yazılsaydı ekran komple hata görünümüne
/// düşer, girilen değerler kaybolurdu.
typedef SaveChanges = Future<String?> Function(Map<String, dynamic> changes);

typedef DeleteItem = Future<String?> Function();

/// Masa düzenleme paneli (şartname M5).
///
/// *"Masaya dokununca panel açılır. Değiştirilebilenler: numara, sandalye
/// sayısı, etiket, silme."*
///
/// *"Kaydetme: düzen otomatik kaydedilir. Organizatör 'kaydet' aramak zorunda
/// kalmaz."* Her değişiklik kısa bir duraklamadan sonra sunucuya gidiyor.
Future<void> showTableSheet({
  required BuildContext context,
  required EventTable table,
  required SaveChanges onSave,
  required DeleteItem onDelete,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (context) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: _TableSheet(table: table, onSave: onSave, onDelete: onDelete),
    ),
  );
}

/// Alan bloğu düzenleme paneli (M5).
Future<void> showAreaSheet({
  required BuildContext context,
  required LayoutArea area,
  required SaveChanges onSave,
  required DeleteItem onDelete,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (context) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
      child: _AreaSheet(area: area, onSave: onSave, onDelete: onDelete),
    ),
  );
}

/// Yeni alan bloğunun etiketini sorar.
///
/// *"Sahne, giriş, büfe gibi işaretler."* Hazır etiketler yalnızca öneri —
/// veri modelinde tip alanı yok, organizatör istediğini yazabiliyor.
Future<String?> askAreaLabel(BuildContext context) {
  return showDialog<String>(
    context: context,
    builder: (context) => const _AreaLabelDialog(),
  );
}

const _presetAreaLabels = ['Sahne', 'Giriş', 'Büfe', 'Kayıt Masası'];

/// Geri alınamayan silme için onay.
Future<bool> confirmRemoval(BuildContext context, String what) async {
  final answer = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('$what silinsin mi?'),
      content: const Text('Bu işlem geri alınamaz.'),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Vazgeç'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Sil'),
        ),
      ],
    ),
  );
  return answer ?? false;
}

// --- Masa paneli -------------------------------------------------------------

class _TableSheet extends StatefulWidget {
  const _TableSheet({
    required this.table,
    required this.onSave,
    required this.onDelete,
  });

  final EventTable table;
  final SaveChanges onSave;
  final DeleteItem onDelete;

  @override
  State<_TableSheet> createState() => _TableSheetState();
}

class _TableSheetState extends State<_TableSheet> {
  late final TextEditingController _number =
      TextEditingController(text: '${widget.table.number}');
  late final TextEditingController _label =
      TextEditingController(text: widget.table.label ?? '');

  late int _seatCount = widget.table.seatCount ?? 6;
  late int _minPeople = widget.table.minPeople ?? 3;
  late int _maxPeople = widget.table.maxPeople ?? 8;

  final _saver = _DebouncedSaver();

  String? _numberError;
  String? _generalError;
  bool _saving = false;
  bool _removing = false;

  bool get _seated => widget.table.kind == TableKind.seated;

  @override
  void dispose() {
    // Panel kapanırken bekleyen kaydetme hemen gönderiliyor: organizatör
    // "kaydet" aramadığı gibi, kapattığı için de veri kaybetmemeli. Gönderim
    // `_send`'ten geçmiyor — o ekranı güncellemeye çalışırdı, ekran kapanıyor.
    final pending = _saver.takePending();
    if (pending != null) unawaited(widget.onSave(pending));
    _number.dispose();
    _label.dispose();
    super.dispose();
  }

  void _queue(Map<String, dynamic> changes) {
    setState(() {
      _numberError = null;
      _generalError = null;
    });
    _saver.schedule(changes, _send);
  }

  /// Hatayı doğru alanın altına koyar.
  ///
  /// Birikmiş bir yığında numara varsa çakışma neredeyse kesin ondandır:
  /// sandalye sayısı ve etiket çakışmaz. Uyarı numaranın altında çıkmalı,
  /// organizatör düzelteceği yeri görsün (M5).
  Future<void> _send(Map<String, dynamic> changes) async {
    if (mounted) setState(() => _saving = true);
    final error = await widget.onSave(changes);
    if (!mounted) return;
    setState(() {
      _saving = false;
      if (changes.containsKey('number')) {
        _numberError = error;
      } else {
        _generalError = error;
      }
    });
  }

  Future<void> _remove() async {
    if (!await confirmRemoval(context, '${widget.table.number} numaralı masa')) {
      return;
    }
    if (!mounted) return;

    setState(() => _removing = true);
    final error = await widget.onDelete();
    if (!mounted) return;

    if (error == null) {
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      _removing = false;
      _generalError = error;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return _SheetBody(
      title: '${widget.table.number} numaralı masa',
      subtitle: widget.table.kind.label,
      saving: _saving,
      children: [
        TextField(
          controller: _number,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          enabled: !_removing,
          decoration: InputDecoration(
            labelText: 'Masa numarası',
            errorText: _numberError,
            helperText: 'Katılımcılar masalarını numarayla buluyor.',
          ),
          onChanged: (value) {
            final parsed = int.tryParse(value);
            if (parsed == null || parsed < 1) return;
            _queue({'number': parsed});
          },
        ),
        const SizedBox(height: AppSpacing.md),
        if (_seated)
          _SheetStepper(
            label: 'Sandalye sayısı',
            value: _seatCount,
            minimum: 2,
            maximum: 50,
            enabled: !_removing,
            onChanged: (value) {
              setState(() => _seatCount = value);
              _queue({'seat_count': value});
            },
          )
        else ...[
          _SheetStepper(
            label: 'En az kişi (hedef)',
            value: _minPeople,
            minimum: 2,
            maximum: 50,
            enabled: !_removing,
            onChanged: (value) {
              setState(() {
                _minPeople = value;
                if (_maxPeople < value) _maxPeople = value;
              });
              _queue({'min_people': _minPeople, 'max_people': _maxPeople});
            },
          ),
          _SheetStepper(
            label: 'En fazla kişi',
            value: _maxPeople,
            minimum: _minPeople,
            maximum: 50,
            enabled: !_removing,
            onChanged: (value) {
              setState(() => _maxPeople = value);
              _queue({'max_people': value});
            },
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        TextField(
          controller: _label,
          enabled: !_removing,
          decoration: const InputDecoration(
            labelText: 'Etiket (isteğe bağlı)',
            hintText: 'Sponsor Masası',
          ),
          onChanged: (value) => _queue({'label': value.trim()}),
        ),
        if (_generalError != null) ...[
          const SizedBox(height: AppSpacing.md),
          Text(
            _generalError!,
            style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.error),
          ),
        ],
        const SizedBox(height: AppSpacing.lg),
        OutlinedButton.icon(
          onPressed: _removing ? null : _remove,
          icon: const Icon(Icons.delete_outline),
          label: const Text('Masayı sil'),
          style: OutlinedButton.styleFrom(foregroundColor: theme.colorScheme.error),
        ),
      ],
    );
  }
}

// --- Alan bloğu paneli -------------------------------------------------------

class _AreaSheet extends StatefulWidget {
  const _AreaSheet({
    required this.area,
    required this.onSave,
    required this.onDelete,
  });

  final LayoutArea area;
  final SaveChanges onSave;
  final DeleteItem onDelete;

  @override
  State<_AreaSheet> createState() => _AreaSheetState();
}

class _AreaSheetState extends State<_AreaSheet> {
  late final TextEditingController _label =
      TextEditingController(text: widget.area.label);
  late int _width = widget.area.width;
  late int _height = widget.area.height;

  final _saver = _DebouncedSaver();

  String? _error;
  bool _saving = false;
  bool _removing = false;

  @override
  void dispose() {
    final pending = _saver.takePending();
    if (pending != null) unawaited(widget.onSave(pending));
    _label.dispose();
    super.dispose();
  }

  void _queue(Map<String, dynamic> changes) {
    setState(() => _error = null);
    _saver.schedule(changes, _send);
  }

  Future<void> _send(Map<String, dynamic> changes) async {
    if (mounted) setState(() => _saving = true);
    final error = await widget.onSave(changes);
    if (!mounted) return;
    setState(() {
      _saving = false;
      _error = error;
    });
  }

  Future<void> _remove() async {
    if (!await confirmRemoval(context, '“${widget.area.label}” alanı')) return;
    if (!mounted) return;

    setState(() => _removing = true);
    final error = await widget.onDelete();
    if (!mounted) return;

    if (error == null) {
      Navigator.of(context).pop();
      return;
    }
    setState(() {
      _removing = false;
      _error = error;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return _SheetBody(
      title: widget.area.label,
      subtitle: 'Alan bloğu — eşleştirmeye girmez',
      saving: _saving,
      children: [
        TextField(
          controller: _label,
          enabled: !_removing,
          decoration: const InputDecoration(labelText: 'Etiket'),
          onChanged: (value) {
            final trimmed = value.trim();
            if (trimmed.isEmpty) return;
            _queue({'label': trimmed});
          },
        ),
        const SizedBox(height: AppSpacing.md),
        _SheetStepper(
          label: 'Genişlik (hücre)',
          value: _width,
          minimum: 1,
          maximum: 60,
          enabled: !_removing,
          onChanged: (value) {
            setState(() => _width = value);
            _queue({'width': value});
          },
        ),
        _SheetStepper(
          label: 'Yükseklik (hücre)',
          value: _height,
          minimum: 1,
          maximum: 60,
          enabled: !_removing,
          onChanged: (value) {
            setState(() => _height = value);
            _queue({'height': value});
          },
        ),
        if (_error != null) ...[
          const SizedBox(height: AppSpacing.md),
          Text(
            _error!,
            style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.error),
          ),
        ],
        const SizedBox(height: AppSpacing.lg),
        OutlinedButton.icon(
          onPressed: _removing ? null : _remove,
          icon: const Icon(Icons.delete_outline),
          label: const Text('Alanı sil'),
          style: OutlinedButton.styleFrom(foregroundColor: theme.colorScheme.error),
        ),
      ],
    );
  }
}

// --- Yeni alan bloğu ---------------------------------------------------------

class _AreaLabelDialog extends StatefulWidget {
  const _AreaLabelDialog();

  @override
  State<_AreaLabelDialog> createState() => _AreaLabelDialogState();
}

class _AreaLabelDialogState extends State<_AreaLabelDialog> {
  final _label = TextEditingController(text: _presetAreaLabels.first);

  @override
  void dispose() {
    _label.dispose();
    super.dispose();
  }

  void _submit() {
    final value = _label.text.trim();
    if (value.isEmpty) return;
    Navigator.of(context).pop(value);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Alan bloğu'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: AppSpacing.sm,
            children: [
              for (final preset in _presetAreaLabels)
                ActionChip(
                  label: Text(preset),
                  onPressed: () => setState(() => _label.text = preset),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _label,
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Etiket'),
            onSubmitted: (_) => _submit(),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Vazgeç'),
        ),
        FilledButton(onPressed: _submit, child: const Text('Ekle')),
      ],
    );
  }
}

// --- Ortak parçalar ----------------------------------------------------------

/// Panellerin ortak çerçevesi: başlık, kaydetme göstergesi, içerik.
class _SheetBody extends StatelessWidget {
  const _SheetBody({
    required this.title,
    required this.subtitle,
    required this.saving,
    required this.children,
  });

  final String title;
  final String subtitle;
  final bool saving;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        0,
        AppSpacing.lg,
        AppSpacing.lg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: theme.textTheme.titleLarge),
                    Text(
                      subtitle,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              // Otomatik kaydetme sessiz olmamalı: organizatör değişikliğin
              // gittiğini görsün. Gösterge yalnızca kaydederken kuruluyor —
              // saydamlığı sıfırlanmış bir gösterge boşuna tik atardı.
              SizedBox(
                width: AppSpacing.md,
                height: AppSpacing.md,
                child: saving ? const CircularProgressIndicator(strokeWidth: 2) : null,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          ...children,
        ],
      ),
    );
  }
}

class _SheetStepper extends StatelessWidget {
  const _SheetStepper({
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
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        children: [
          Expanded(child: Text(label, style: theme.textTheme.bodyLarge)),
          IconButton.outlined(
            onPressed: enabled && value > minimum ? () => onChanged(value - 1) : null,
            icon: const Icon(Icons.remove),
            tooltip: '$label azalt',
          ),
          SizedBox(
            width: 56,
            child: Text(
              '$value',
              textAlign: TextAlign.center,
              style: theme.textTheme.titleMedium,
            ),
          ),
          IconButton.outlined(
            onPressed: enabled && value < maximum ? () => onChanged(value + 1) : null,
            icon: const Icon(Icons.add),
            tooltip: '$label artır',
          ),
        ],
      ),
    );
  }
}

/// Otomatik kaydetmenin zamanlayıcısı.
///
/// Her tuş vuruşunda istek atmak hem sunucuyu yorar hem de yarım yazılmış bir
/// numarayı ("1" → "12") çakışma sanıp gereksiz uyarı verir. Kısa bir
/// duraklama beklenip son hâli gönderiliyor.
///
/// Bekleyen değişiklikler **birikiyor**, birbirini ezmiyor: sandalye sayısını
/// artırıp hemen etiket yazan organizatör ilk değişikliğini kaybetmemeli.
/// Şartname *"organizatör 'kaydet' aramak zorunda kalmaz"* diyor — kaydetmediği
/// için veri kaybetmesi bunun tersi olurdu.
class _DebouncedSaver {
  static const _pause = Duration(milliseconds: 600);

  Timer? _timer;
  final Map<String, dynamic> _changes = {};
  Future<void> Function(Map<String, dynamic>)? _send;

  void schedule(
    Map<String, dynamic> changes,
    Future<void> Function(Map<String, dynamic>) send,
  ) {
    _changes.addAll(changes);
    _send = send;
    _timer?.cancel();
    _timer = Timer(_pause, _run);
  }

  /// Biriken değişiklikleri alır ve zamanlayıcıyı durdurur.
  ///
  /// Panel kapanırken kullanılıyor: bekleyen değişiklik gitmeli ama gönderim
  /// artık ekranı güncellemeye çalışmamalı — ekran yok.
  Map<String, dynamic>? takePending() {
    _timer?.cancel();
    _timer = null;
    if (_changes.isEmpty) return null;
    final batch = Map<String, dynamic>.from(_changes);
    _changes.clear();
    return batch;
  }

  void _run() {
    final batch = takePending();
    final send = _send;
    if (batch != null && send != null) unawaited(send(batch));
  }
}
