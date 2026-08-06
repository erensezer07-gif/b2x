import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'event_controller.dart';
import 'matching_screen.dart';
import 'models.dart';
import 'my_plan_widgets.dart';
import 'schedule.dart';

/// Organizatörün check-in ekranı (şartname M10).
///
/// *"Organizatörün ekranında kamera açılır, girişte katılımcıların kodları
/// okutulur. Okunan kişi 'geldi' olarak işaretlenir, ekranda adı ve fotoğrafı
/// belirir."*
///
/// **Elle arama her zaman açık.** *"Telefonu bozulan, kodu bulamayan kişi
/// listeden bulunup elle işaretlenebilir."* Kamera bir kolaylık; kamerası
/// olmayan bir cihazda da check-in yapılabiliyor.
class CheckInScreen extends ConsumerStatefulWidget {
  const CheckInScreen({super.key, required this.eventId});

  static const routeName = 'eventCheckIn';
  static const routePath = '/etkinlikler/:eventId/giris';

  final int eventId;

  @override
  ConsumerState<CheckInScreen> createState() => _CheckInScreenState();
}

class _CheckInScreenState extends ConsumerState<CheckInScreen> {
  static const _typingDelay = Duration(milliseconds: 350);

  /// Aynı kodun kamera tarafından saniyede onlarca kez okunmasını engelliyor.
  static const _rescanDelay = Duration(seconds: 3);

  final _searchController = TextEditingController();
  Timer? _typing;

  String? _search;
  bool _cameraOn = false;
  bool _busy = false;
  String? _error;

  /// Son okunan kişi — *"ekranda adı ve fotoğrafı belirir."*
  ScanResult? _last;

  /// Son okunan kod ve zamanı; aynı kodun tekrar tekrar işlenmesini önlüyor.
  String? _lastCode;
  DateTime? _lastScanAt;

  AttendanceQuery get _query => AttendanceQuery(widget.eventId, search: _search);

  @override
  void dispose() {
    _typing?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    _typing?.cancel();
    _typing = Timer(_typingDelay, () {
      if (!mounted) return;
      setState(() => _search = value.trim().isEmpty ? null : value.trim());
    });
  }

  Future<void> _handleCode(String code) async {
    final now = DateTime.now();
    if (_busy) return;
    if (_lastCode == code &&
        _lastScanAt != null &&
        now.difference(_lastScanAt!) < _rescanDelay) {
      return;
    }
    _lastCode = code;
    _lastScanAt = now;

    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await ref.read(attendanceActionsProvider(widget.eventId)).scan(code);
      if (!mounted) return;
      setState(() {
        _last = result;
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

  Future<void> _mark(Attendee attendee, {required bool present}) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(attendanceActionsProvider(widget.eventId))
          .mark(attendee.registrationId, present: present);
      if (!mounted) return;
      setState(() => _busy = false);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _busy = false;
      });
    }
  }

  Future<void> _enterCodeByHand() async {
    final controller = TextEditingController();
    final code = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Kodu elle gir'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Giriş kodu'),
          onSubmitted: (value) => context.pop(value),
        ),
        actions: [
          TextButton(onPressed: () => context.pop(), child: const Text('Vazgeç')),
          FilledButton(
            onPressed: () => context.pop(controller.text),
            child: const Text('Oku'),
          ),
        ],
      ),
    );
    if (code != null && code.trim().isNotEmpty) {
      await _handleCode(code.trim());
    }
  }

  @override
  Widget build(BuildContext context) {
    final board = ref.watch(attendanceProvider(_query));

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
        title: const Text('Giriş'),
        actions: [
          IconButton(
            icon: Icon(_cameraOn ? Icons.videocam_off : Icons.qr_code_scanner),
            tooltip: _cameraOn ? 'Kamerayı kapat' : 'Kamerayı aç',
            onPressed: () => setState(() => _cameraOn = !_cameraOn),
          ),
          IconButton(
            icon: const Icon(Icons.keyboard),
            tooltip: 'Kodu elle gir',
            onPressed: _enterCodeByHand,
          ),
        ],
      ),
      body: switch (board) {
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Liste yüklenemedi.',
            onRetry: () => ref.invalidate(attendanceProvider(_query)),
          ),
        AsyncData(:final value) => _buildBody(value),
        _ => const LoadingView(message: 'Liste yükleniyor'),
      },
    );
  }

  Widget _buildBody(AttendanceBoard board) {
    return Column(
      children: [
        _Counter(board: board),
        if (_cameraOn) _Scanner(onCode: _handleCode),
        if (_busy) const LinearProgressIndicator(minHeight: 2),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            children: [
              if (_last != null) ...[
                _LastScan(
                  result: _last!,
                  onDismiss: () => setState(() => _last = null),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              if (_error != null) ...[
                _ErrorStrip(
                  message: _error!,
                  onDismiss: () => setState(() => _error = null),
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              TextField(
                controller: _searchController,
                onChanged: _onSearchChanged,
                decoration: const InputDecoration(
                  labelText: 'Ad veya şirket ara',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: board.attendees.isEmpty
              ? EmptyView(
                  icon: Icons.person_search_outlined,
                  message: _search == null
                      ? 'Bu etkinlikte kabul edilmiş katılımcı yok.'
                      : 'Bu aramaya uyan katılımcı yok.',
                )
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md,
                    0,
                    AppSpacing.md,
                    AppSpacing.md,
                  ),
                  itemCount: board.attendees.length,
                  itemBuilder: (context, index) {
                    final attendee = board.attendees[index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: AttendeeCard(
                        attendee: attendee,
                        busy: _busy,
                        onToggle: () => _mark(attendee, present: !attendee.present),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

/// *"Sayaç sürekli görünür: kaç kişi geldi, kaç kişi bekleniyor."* (M10)
class _Counter extends StatelessWidget {
  const _Counter({required this.board});

  final AttendanceBoard board;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Container(
      width: double.infinity,
      color: colors.primaryContainer,
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _Number(
            value: board.presentCount,
            label: 'Geldi',
            color: colors.onPrimaryContainer,
          ),
          _Number(
            value: board.expectedCount,
            label: 'Bekleniyor',
            color: colors.onPrimaryContainer,
          ),
        ],
      ),
    );
  }
}

class _Number extends StatelessWidget {
  const _Number({required this.value, required this.label, required this.color});

  final int value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        Text('$value', style: theme.textTheme.headlineMedium?.copyWith(color: color)),
        Text(label, style: theme.textTheme.bodySmall?.copyWith(color: color)),
      ],
    );
  }
}

/// Kamera. Kapatılabilir: kapıda pil ve gizlilik.
class _Scanner extends StatelessWidget {
  const _Scanner({required this.onCode});

  final void Function(String) onCode;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return SizedBox(
      height: 240,
      child: MobileScanner(
        onDetect: (capture) {
          for (final barcode in capture.barcodes) {
            final value = barcode.rawValue;
            if (value != null && value.trim().isNotEmpty) {
              onCode(value.trim());
              return;
            }
          }
        },
        // Kamera açılmazsa (izin yok, cihazda kamera yok) ekran çökmemeli;
        // elle arama zaten açık.
        errorBuilder: (context, error) => Container(
          color: colors.surfaceContainerHighest,
          alignment: Alignment.center,
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Text(
            'Kamera açılamadı. Aşağıdan elle arayarak işaretleyebilirsin.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
          ),
        ),
      ),
    );
  }
}

/// *"Okunan kişi geldi olarak işaretlenir, ekranda adı ve fotoğrafı belirir."*
class _LastScan extends StatelessWidget {
  const _LastScan({required this.result, required this.onDismiss});

  final ScanResult result;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final attendee = result.attendee;

    return Card(
      margin: EdgeInsets.zero,
      color: result.alreadyPresent
          ? colors.surfaceContainerHighest
          : colors.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            PersonAvatar(photoUrl: attendee.photoUrl, name: attendee.displayName, radius: 28),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(attendee.displayName, style: theme.textTheme.titleMedium),
                  if (attendee.company != null)
                    Text(attendee.company!, style: theme.textTheme.bodyMedium),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    result.alreadyPresent
                        ? 'Zaten girmişti · ${formatTime(attendee.checkedInAt!)}'
                        : 'Girişi yapıldı.',
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            IconButton(
              icon: const Icon(Icons.close),
              tooltip: 'Kapat',
              onPressed: onDismiss,
            ),
          ],
        ),
      ),
    );
  }
}

/// Listedeki bir katılımcı; dokununca geldi/gelmedi değişiyor.
class AttendeeCard extends StatelessWidget {
  const AttendeeCard({
    super.key,
    required this.attendee,
    required this.busy,
    required this.onToggle,
  });

  final Attendee attendee;
  final bool busy;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            PersonAvatar(photoUrl: attendee.photoUrl, name: attendee.displayName),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(attendee.displayName, style: theme.textTheme.titleSmall),
                  if (attendee.company != null)
                    Text(
                      attendee.company!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                  if (attendee.checkedInAt != null)
                    Text(
                      'Giriş ${formatTime(attendee.checkedInAt!)}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                ],
              ),
            ),
            // Geri alınabiliyor: yanlış kişi işaretlenmiş olabilir.
            if (attendee.present)
              TextButton.icon(
                onPressed: busy ? null : onToggle,
                icon: const Icon(Icons.check_circle, size: AppSpacing.md),
                label: const Text('Geldi'),
              )
            else
              OutlinedButton(
                onPressed: busy ? null : onToggle,
                child: const Text('Geldi işaretle'),
              ),
          ],
        ),
      ),
    );
  }
}

class _ErrorStrip extends StatelessWidget {
  const _ErrorStrip({required this.message, required this.onDismiss});

  final String message;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      color: colors.errorContainer,
      child: Padding(
        padding: const EdgeInsets.only(left: AppSpacing.md),
        child: Row(
          children: [
            Icon(Icons.block, color: colors.onErrorContainer),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                message,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.onErrorContainer,
                ),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.close),
              tooltip: 'Kapat',
              onPressed: onDismiss,
            ),
          ],
        ),
      ),
    );
  }
}
