import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/config/app_config.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import '../profile/models.dart';
import '../profile/wizard/profile_wizard_screen.dart';
import 'discover_tab.dart';
import 'event_controller.dart';
import 'event_list_screen.dart';
import 'models.dart';
import 'my_plan_screen.dart';
import 'participants_screen.dart';
import 'qr_screen.dart';
import 'schedule.dart';

/// Katılımcının gördüğü etkinlik detayı ve başvuru akışı (şartname M3).
///
/// *"Detay ekranı: açıklama, program (slot saatleri hesaplanmış halde), yer
/// bilgisi, kaç kişi katılıyor, başvur butonu."*
///
/// Organizatörün sihirbazı ayrı bir ekran; burası herkesin gördüğü yüz.
class PublicEventScreen extends ConsumerStatefulWidget {
  const PublicEventScreen({super.key, required this.eventId});

  static const routeName = 'publicEvent';
  static const routePath = '/kesfet/:eventId';

  final int eventId;

  @override
  ConsumerState<PublicEventScreen> createState() => _PublicEventScreenState();
}

class _PublicEventScreenState extends ConsumerState<PublicEventScreen> {
  bool _busy = false;

  /// Başvuruyu engelleyen profil eksikleri.
  ///
  /// Paylaşılan duruma değil ekranın kendi state'ine yazılıyor: yönlendirme
  /// paylaşılan hatayı görüp kullanıcıyı başka sayfaya atardı (Aşama 3).
  List<ProfileRequirement> _missing = const [];
  String? _error;

  String? _resolveCoverUrl(String? url) {
    if (url == null || url.trim().isEmpty) return null;
    if (url.startsWith('http://localhost:8000') || url.startsWith('http://127.0.0.1:8000')) {
      final path = Uri.parse(url).path;
      return '${AppConfig.apiBaseUrl}$path';
    }
    return url;
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
      _missing = const [];
    });

    try {
      await action();
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _missing = error.missingForApplication.map(ProfileRequirement.fromKey).toList();
        // Eksik profil ayrı bir kutuda anlatılıyor; genel mesajı tekrar
        // göstermek aynı şeyi iki kez söylemek olurdu.
        _error = _missing.isEmpty ? error.message : null;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final event = ref.watch(publicEventProvider(widget.eventId));

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Keşfete dön',
          onPressed: () => context.goNamed(EventListScreen.routeName),
        ),
        title: const Text('Etkinlik'),
      ),
      body: switch (event) {
        AsyncLoading() => const LoadingView(message: 'Etkinlik yükleniyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Etkinlik yüklenemedi.',
            onRetry: () => ref.invalidate(publicEventProvider(widget.eventId)),
          ),
        AsyncData(:final value) => _buildDetail(value),
      },
    );
  }

  Widget _buildDetail(PublicEvent event) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final coverUrl = _resolveCoverUrl(event.coverUrl);

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        if (coverUrl != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(AppSpacing.sm),
            child: Image.network(
              coverUrl,
              height: 180,
              width: double.infinity,
              fit: BoxFit.cover,
              // Görsel gelmezse ekran çökmemeli; başlık zaten altında.
              errorBuilder: (context, _, _) => const SizedBox.shrink(),
            ),
          ),
        const SizedBox(height: AppSpacing.md),
        Text(event.name, style: theme.textTheme.headlineSmall),
        const SizedBox(height: AppSpacing.sm),
        RegistrationBadge(status: event.myRegistration?.status),
        const SizedBox(height: AppSpacing.md),

        _Facts(event: event),

        if (event.description != null && event.description!.trim().isNotEmpty) ...[
          const SizedBox(height: AppSpacing.lg),
          Text('Açıklama', style: theme.textTheme.titleSmall),
          const SizedBox(height: AppSpacing.sm),
          Text(event.description!, style: theme.textTheme.bodyMedium),
        ],

        const SizedBox(height: AppSpacing.lg),
        Text('Program', style: theme.textTheme.titleSmall),
        const SizedBox(height: AppSpacing.sm),
        _SchedulePreview(event: event),

        if (_missing.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.lg),
          _MissingProfileCard(missing: _missing),
        ],
        if (_error != null) ...[
          const SizedBox(height: AppSpacing.md),
          Text(
            _error!,
            style: theme.textTheme.bodyMedium?.copyWith(color: colors.error),
          ),
        ],

        // Kabul edilen katılımcı planına buradan giriyor (M8). Plan yayında
        // değilse ekran *"henüz hazırlanıyor"* diyor — kapı sunucuda.
        if (event.myRegistration?.status == RegistrationStatus.accepted) ...[
          const SizedBox(height: AppSpacing.lg),
          FilledButton.icon(
            onPressed: () => context.goNamed(
              MyPlanScreen.routeName,
              pathParameters: {'eventId': '${widget.eventId}'},
            ),
            icon: const Icon(Icons.event_seat_outlined),
            label: const Text('Oturma planım'),
          ),
          const SizedBox(height: AppSpacing.sm),
          // Görüşme talepleri (M9). Talepler kapandıysa ekran bunu söylüyor;
          // asıl kapı sunucuda.
          OutlinedButton.icon(
            onPressed: () => context.goNamed(
              ParticipantsScreen.routeName,
              pathParameters: {'eventId': '${widget.eventId}'},
            ),
            icon: const Icon(Icons.handshake_outlined),
            label: const Text('Kimlerle görüşmek istersin'),
          ),
          const SizedBox(height: AppSpacing.sm),
          // Girişte okutulacak kod (M10).
          OutlinedButton.icon(
            onPressed: () => context.goNamed(
              QrScreen.routeName,
              pathParameters: {'eventId': '${widget.eventId}'},
            ),
            icon: const Icon(Icons.qr_code_2),
            label: const Text('Giriş kodum'),
          ),
        ],

        const SizedBox(height: AppSpacing.lg),
        _ApplyButton(
          event: event,
          busy: _busy,
          onApply: () => _run(
            ref.read(registrationActionsProvider(widget.eventId)).apply,
          ),
          onWithdraw: () => _run(
            ref.read(registrationActionsProvider(widget.eventId)).withdraw,
          ),
        ),
      ],
    );
  }
}

/// Tarih, yer, kontenjan, katılımcı sayısı.
class _Facts extends StatelessWidget {
  const _Facts({required this.event});

  final PublicEvent event;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    final rows = <(IconData, String)>[
      (
        Icons.calendar_today_outlined,
        '${formatDate(event.startsAt)} · ${formatTime(event.startsAt)}–${formatTime(event.endsAt)}',
      ),
      if (event.venueName != null && event.venueName!.isNotEmpty)
        (Icons.place_outlined, [event.venueName, event.address].nonNulls.join('\n')),
      (
        Icons.forum_outlined,
        '${event.slotCount} tur · tur başına ${event.slotDurationMinutes} dakika',
      ),
      (
        Icons.people_outline,
        event.acceptedCount == 0
            ? 'Henüz katılımcı yok · ${event.capacity} kişilik'
            : '${event.acceptedCount} kişi katılıyor · ${event.capacity} kişilik',
      ),
      if (event.registrationDeadline != null)
        (
          Icons.event_busy_outlined,
          'Son başvuru: ${formatDate(event.registrationDeadline!)}',
        ),
    ];

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final (icon, text) in rows)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
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

/// Hesaplanmış slot saatleri (M3).
class _SchedulePreview extends StatelessWidget {
  const _SchedulePreview({required this.event});

  final PublicEvent event;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Uzun programda liste ekranı doldurmasın; başı ve sonu yeterli.
    final all = event.schedule;
    final showAll = all.length <= 8;
    final visible = showAll ? all : [...all.take(3), ...all.skip(all.length - 2)];

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          children: [
            for (var index = 0; index < visible.length; index++) ...[
              if (!showAll && index == 3)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                  child: Text('⋮', style: theme.textTheme.bodyMedium),
                ),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Tur ${visible[index].number}',
                        style: theme.textTheme.bodyMedium),
                    Text(
                      '${formatTime(visible[index].startsAt)} – '
                      '${formatTime(visible[index].endsAt)}',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ],
                ),
              ),
            ],
            const Divider(height: AppSpacing.lg),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Toplam', style: theme.textTheme.bodyLarge),
                Text(formatDuration(event.totalMinutes),
                    style: theme.textTheme.bodyLarge),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Eksik profil uyarısı (M2, Bölüm 10).
///
/// *"Eksikse başvuru butonu çalışmaz ve neyin eksik olduğu yazılır."*
/// Eksiklerin Türkçe adları `ProfileRequirement`'tan geliyor — profil
/// ekranıyla aynı metinler, iki yerde iki farklı cümle olmasın.
class _MissingProfileCard extends StatelessWidget {
  const _MissingProfileCard({required this.missing});

  final List<ProfileRequirement> missing;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      color: colors.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(Icons.person_off_outlined, color: colors.onErrorContainer),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    'Başvurmak için profilini tamamla',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: colors.onErrorContainer,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            for (final item in missing)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Text(
                  '• ${item.label}',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.onErrorContainer,
                  ),
                ),
              ),
            const SizedBox(height: AppSpacing.sm),
            FilledButton.tonalIcon(
              onPressed: () => context.goNamed(ProfileWizardScreen.routeName),
              icon: const Icon(Icons.edit_outlined),
              label: const Text('Profili tamamla'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Başvuru düğmesi — duruma göre değişir.
class _ApplyButton extends StatelessWidget {
  const _ApplyButton({
    required this.event,
    required this.busy,
    required this.onApply,
    required this.onWithdraw,
  });

  final PublicEvent event;
  final bool busy;
  final VoidCallback onApply;
  final VoidCallback onWithdraw;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status = event.myRegistration?.status;

    if (busy) {
      return const Center(child: CircularProgressIndicator());
    }

    // Başvurusu olan geri çekebilir — kabul edilmiş olsa bile. Katılamayacağını
    // anlayan kişinin yeri boşalmalı (M3).
    if (status == RegistrationStatus.pending || status == RegistrationStatus.accepted) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            status == RegistrationStatus.pending
                ? 'Başvurun organizatörün onayını bekliyor.'
                // Planın hazır olup olmadığını bu ekran bilmiyor: kapı
                // sunucuda, cevabı "Oturma planım" veriyor. Burada söz vermek
                // yanlış olurdu — plan yayına alındıktan sonra da "yayınlanınca
                // görünecek" yazıyordu.
                : 'Başvurun kabul edildi.',
            style: theme.textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton.icon(
            onPressed: onWithdraw,
            icon: const Icon(Icons.undo),
            label: const Text('Başvurumu geri çek'),
            style: OutlinedButton.styleFrom(foregroundColor: theme.colorScheme.error),
          ),
        ],
      );
    }

    if (status == RegistrationStatus.rejected) {
      return Text(
        'Bu etkinliğe başvurun kabul edilmedi.',
        style: theme.textTheme.bodyMedium,
        textAlign: TextAlign.center,
      );
    }

    // Düğme kapalıyken de asıl kapı sunucuda: uç kapalı etkinliği reddediyor.
    return FilledButton.icon(
      onPressed: event.isOpen ? onApply : null,
      icon: const Icon(Icons.how_to_reg),
      label: Text(event.isOpen ? 'Başvur' : 'Başvurular kapalı'),
    );
  }
}
