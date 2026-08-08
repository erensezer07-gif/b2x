import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'discover_tab.dart';
import 'event_controller.dart';
import 'matching_screen.dart';
import 'models.dart';
import 'registrations_screen.dart';
import 'schedule.dart';
import 'wizard/event_wizard_screen.dart';

/// Etkinlikler sekmesi — iki yaprak (şartname M3, M4).
///
/// **Keşfet** başvurulabilecek etkinlikler, **Düzenlediklerim** kullanıcının
/// kendi oluşturdukları.
///
/// Ayrı bir alt sekme açılmadı: Bölüm 7 *"rol kullanıcıya değil, etkinliğe göre
/// belirlenir"* diyor. Alt çubukta "Katılımcı" ve "Organizatör" ayrımı yapmak
/// olmayan bir rol kavramı uydururdu; aynı sekmenin iki yaprağı doğru okuma.
///
/// Kayan "Yeni etkinlik" düğmesi yalnızca Düzenlediklerim yaprağında: Keşfet'te
/// listelenen etkinlikler başkasının, oraya oluşturma düğmesi koymak kafa
/// karıştırırdı.
class EventListScreen extends ConsumerStatefulWidget {
  const EventListScreen({super.key});

  static const routeName = 'events';
  static const routePath = '/etkinlikler';

  @override
  ConsumerState<EventListScreen> createState() => _EventListScreenState();
}

class _EventListScreenState extends ConsumerState<EventListScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 2, vsync: this)
    ..addListener(() => setState(() {}));

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final onOwnEvents = _tabs.index == 1;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Etkinlikler'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [
            Tab(text: 'Keşfet'),
            Tab(text: 'Düzenlediklerim'),
          ],
        ),
      ),
      floatingActionButton: onOwnEvents
          ? FloatingActionButton.extended(
              onPressed: () => _createDraft(context, ref),
              icon: const Icon(Icons.add),
              label: const Text('Yeni etkinlik'),
            )
          : null,
      body: TabBarView(
        controller: _tabs,
        children: const [DiscoverTab(), _MyEventsTab()],
      ),
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

/// Düzenlediklerim yaprağı — organizatörün kendi etkinlikleri (M4).
class _MyEventsTab extends ConsumerWidget {
  const _MyEventsTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(myEventsProvider);

    return switch (events) {
      AsyncLoading() => const LoadingView(message: 'Etkinliklerin yükleniyor'),
      AsyncError(:final error) => ErrorView(
          message: error is ApiException ? error.message : 'Etkinlikler yüklenemedi.',
          onRetry: () => ref.invalidate(myEventsProvider),
        ),
      AsyncData(:final value) when value.isEmpty => const EmptyView(
          icon: Icons.event_outlined,
          message: 'Henüz etkinlik oluşturmadın.\n'
              'Sağ alttaki düğmeyle başlayabilirsin.',
        ),
      AsyncData(:final value) => RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(myEventsProvider);
            ref.invalidate(discoverEventsProvider);
          },
          child: _EventList(events: value),
        ),
    };
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

class _EventCard extends ConsumerWidget {
  const _EventCard({required this.event});

  final EventSummary event;

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Etkinliği sil?'),
        content: Text(
          '"${event.name}" etkinliğini silmek istediğine emin misin? Bu işlem geri alınamaz.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Vazgeç'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Sil'),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      final messenger = ScaffoldMessenger.of(context);
      try {
        await ref.read(eventActionsProvider(event.id)).deleteEvent();
        messenger.showSnackBar(
          const SnackBar(content: Text('Etkinlik silindi.')),
        );
      } on ApiException catch (error) {
        messenger.showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
              if (event.status == EventStatus.draft) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Kayıtlar açılınca Keşfet\'te listelenir',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
            ],
          ),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Sil',
              onPressed: () => _confirmDelete(context, ref),
            ),
            if (event.status != EventStatus.draft) ...[
              IconButton(
                icon: const Icon(Icons.how_to_reg_outlined),
                tooltip: 'Başvurular',
                onPressed: () => context.goNamed(
                  RegistrationsScreen.routeName,
                  pathParameters: {'eventId': '${event.id}'},
                ),
              ),
              IconButton(
                icon: const Icon(Icons.auto_awesome_outlined),
                tooltip: 'Eşleştirme',
                onPressed: () => context.goNamed(
                  MatchingScreen.routeName,
                  pathParameters: {'eventId': '${event.id}'},
                ),
              ),
            ] else
              const Icon(Icons.chevron_right),
          ],
        ),
        onTap: () => context.goNamed(
          EventWizardScreen.routeName,
          pathParameters: {'eventId': '${event.id}'},
        ),
      ),
    );
  }

  String _describe(EventSummary event) {
    final place = event.venueName;

    return [
      '${formatDate(event.startsAt)} · ${formatTime(event.startsAt)}',
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
