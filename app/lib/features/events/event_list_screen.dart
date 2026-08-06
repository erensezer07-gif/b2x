import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'event_controller.dart';
import 'models.dart';
import 'schedule.dart';
import 'wizard/event_wizard_screen.dart';

/// Organizatörün etkinlik listesi (şartname M4).
///
/// Şu an yalnızca kullanıcının **kendi oluşturduğu** etkinlikler görünüyor.
/// Başvurulabilecek etkinliklerin keşfi Aşama 6'nın konusu ve aynı sekmeye
/// eklenecek.
class EventListScreen extends ConsumerWidget {
  const EventListScreen({super.key});

  static const routeName = 'events';
  static const routePath = '/etkinlikler';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(myEventsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Etkinlikler')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _createDraft(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('Yeni etkinlik'),
      ),
      body: switch (events) {
        AsyncLoading() => const LoadingView(message: 'Etkinliklerin yükleniyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException
                ? error.message
                : 'Etkinlikler yüklenemedi.',
            onRetry: () => ref.invalidate(myEventsProvider),
          ),
        AsyncData(:final value) when value.isEmpty => const EmptyView(
            icon: Icons.event_outlined,
            message: 'Henüz etkinlik oluşturmadın.\n'
                'Sağ alttaki düğmeyle başlayabilirsin.',
          ),
        AsyncData(:final value) => RefreshIndicator(
            onRefresh: () async => ref.invalidate(myEventsProvider),
            child: _EventList(events: value),
          ),
      },
    );
  }

  /// Yeni taslak açar ve sihirbaza geçer.
  ///
  /// Etkinlik sunucuda hemen oluşuyor: sihirbazın her adımı kaydedebilsin ve
  /// kullanıcı yarıda bırakıp dönebilsin diye (M4).
  Future<void> _createDraft(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    final router = GoRouter.of(context);

    try {
      final draft = await ref.read(eventRepositoryProvider).createDraft(
            name: 'Yeni etkinlik',
            // Varsayılan bir tarih: organizatör ilk adımda değiştirecek.
            startsAt: DateTime.now().add(const Duration(days: 30)),
          );
      ref.invalidate(myEventsProvider);
      router.goNamed(
        EventWizardScreen.routeName,
        pathParameters: {'eventId': '${draft.id}'},
      );
    } on ApiException catch (error) {
      messenger.showSnackBar(SnackBar(content: Text(error.message)));
    }
  }
}

class _EventList extends StatelessWidget {
  const _EventList({required this.events});

  final List<EventSummary> events;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.md,
        AppSpacing.md,
        AppSpacing.md,
        // Kayan düğmenin son kartı örtmemesi için.
        AppSpacing.xl * 2,
      ),
      itemCount: events.length,
      itemBuilder: (context, index) => _EventCard(event: events[index]),
    );
  }
}

class _EventCard extends StatelessWidget {
  const _EventCard({required this.event});

  final EventSummary event;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: ListTile(
        contentPadding: const EdgeInsets.all(AppSpacing.md),
        title: Text(event.name, style: theme.textTheme.titleMedium),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: AppSpacing.xs),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_describe(event)),
              const SizedBox(height: AppSpacing.sm),
              _StatusBadge(status: event.status),
            ],
          ),
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: () => context.goNamed(
          EventWizardScreen.routeName,
          pathParameters: {'eventId': '${event.id}'},
        ),
      ),
    );
  }

  String _describe(EventSummary event) {
    final date = '${event.startsAt.day}.${event.startsAt.month}.${event.startsAt.year}';
    final time = formatTime(event.startsAt);
    final place = event.venueName;

    return [
      '$date · $time',
      if (place != null && place.isNotEmpty) place,
      '${event.slotCount} tur · ${event.capacity} kişi',
    ].join(' · ');
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});

  final EventStatus status;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    // Taslak dışındaki durumlar "yayında" hissi vermeli; taslak sessiz kalıyor.
    final (background, foreground) = switch (status) {
      EventStatus.draft => (colors.surfaceContainerHighest, colors.onSurfaceVariant),
      EventStatus.registrationOpen => (colors.primaryContainer, colors.onPrimaryContainer),
      EventStatus.registrationClosed => (colors.tertiaryContainer, colors.onTertiaryContainer),
      EventStatus.completed => (colors.surfaceContainerHighest, colors.onSurfaceVariant),
    };

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(AppSpacing.xs),
      ),
      child: Text(
        status.label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(color: foreground),
      ),
    );
  }
}
