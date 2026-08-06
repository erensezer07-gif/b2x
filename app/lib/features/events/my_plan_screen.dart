import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'event_controller.dart';
import 'models.dart';
import 'my_plan_widgets.dart';
import 'public_event_screen.dart';
import 'schedule.dart';

/// Katılımcının kendi oturma planı (şartname M8).
///
/// *"Katılımcının tüm slotları sırayla. Her satır: slot numarası ve saati,
/// masa numarası, kiminle oturacağı."*
///
/// Plan yayınlanmadan hiçbir şey görünmüyor — kapı sunucuda, bu ekran yalnızca
/// bekleme cümlesini yazıyor (Bölüm 7).
class MyPlanScreen extends ConsumerWidget {
  const MyPlanScreen({super.key, required this.eventId});

  static const routeName = 'myPlan';
  static const routePath = '/kesfet/:eventId/planim';

  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final plan = ref.watch(myPlanProvider(eventId));

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Etkinliğe dön',
          onPressed: () => context.goNamed(
            PublicEventScreen.routeName,
            pathParameters: {'eventId': '$eventId'},
          ),
        ),
        title: const Text('Oturma planım'),
      ),
      body: switch (plan) {
        AsyncLoading() => const LoadingView(message: 'Planın yükleniyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Plan yüklenemedi.',
            onRetry: () => ref.invalidate(myPlanProvider(eventId)),
          ),
        AsyncData(:final value) => _Body(eventId: eventId, plan: value),
      },
    );
  }
}

class _Body extends ConsumerWidget {
  const _Body({required this.eventId, required this.plan});

  final int eventId;
  final MyPlan plan;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // M8'in birebir cümlesi. Hata değil, bekleme durumu.
    if (!plan.isPublished) {
      return const EmptyView(
        icon: Icons.hourglass_empty,
        message: 'Oturma planınız henüz hazırlanıyor.\n'
            'Hazır olduğunda burada göreceksiniz.',
      );
    }

    if (plan.slots.isEmpty) {
      return const EmptyView(
        icon: Icons.event_busy_outlined,
        message: 'Bu etkinlikte hiç tur yok.',
      );
    }

    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(myPlanProvider(eventId)),
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          MyPlanHeadline(plan: plan),
          const SizedBox(height: AppSpacing.md),
          for (final slot in plan.slots)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: MySlotRow(
                slot: slot,
                onOpen: slot.isFree
                    ? null
                    : () => context.goNamed(
                          MySlotScreen.routeName,
                          pathParameters: {
                            'eventId': '$eventId',
                            'slot': '${slot.slotNumber}',
                          },
                        ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Bir turun ayrıntısı (M8).
///
/// *"Masa numarası büyük ve net. Manuel düzen varsa krokide masanın yeri
/// işaretli. Masadaki her kişi için kart ve eşleşme gerekçesi."*
class MySlotScreen extends ConsumerWidget {
  const MySlotScreen({super.key, required this.eventId, required this.slotNumber});

  static const routeName = 'mySlot';
  static const routePath = '/kesfet/:eventId/planim/:slot';

  final int eventId;
  final int slotNumber;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final plan = ref.watch(myPlanProvider(eventId));
    final venue = ref.watch(venueProvider(eventId));

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Plana dön',
          onPressed: () => context.goNamed(
            MyPlanScreen.routeName,
            pathParameters: {'eventId': '$eventId'},
          ),
        ),
        title: Text('$slotNumber. Tur'),
      ),
      body: switch (plan) {
        AsyncLoading() => const LoadingView(message: 'Tur yükleniyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Tur yüklenemedi.',
            onRetry: () => ref.invalidate(myPlanProvider(eventId)),
          ),
        AsyncData(:final value) => _slotBody(context, value, venue.asData?.value),
      },
    );
  }

  Widget _slotBody(BuildContext context, MyPlan plan, Venue? venue) {
    final slot = plan.slots.where((item) => item.slotNumber == slotNumber).firstOrNull;
    if (slot == null || !plan.isPublished) {
      return const EmptyView(
        icon: Icons.help_outline,
        message: 'Bu tur planında yok.',
      );
    }
    if (slot.isFree) {
      return EmptyView(
        icon: Icons.free_breakfast_outlined,
        message: 'Bu turda serbestsin.\n'
            '${formatTime(slot.startsAt)}–${formatTime(slot.endsAt)} arası '
            'dilediğin gibi dolaşabilirsin.',
      );
    }

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        SlotHeadline(slot: slot),
        if (venue != null && venue.hasSketch) ...[
          const SizedBox(height: AppSpacing.md),
          VenueSketch(venue: venue, highlightTableId: slot.tableId),
        ],
        const SizedBox(height: AppSpacing.lg),
        Text(
          'Masa arkadaşların',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: AppSpacing.sm),
        for (final mate in slot.tablemates)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: TablemateCard(
              mate: mate,
              onOpen: () => context.goNamed(
                TablemateScreen.routeName,
                pathParameters: {
                  'eventId': '$eventId',
                  'registrationId': '${mate.registrationId}',
                },
              ),
            ),
          ),
      ],
    );
  }
}

/// Masa arkadaşının tam profili (M8).
///
/// *"Ancak sadece aynı masada oturduğu kişilerin profilini görebilir."* Kapı
/// sunucuda: masa arkadaşı olmayan biri istenirse 404 dönüyor ve bu ekran
/// hata görünümüne düşüyor.
class TablemateScreen extends ConsumerWidget {
  const TablemateScreen({
    super.key,
    required this.eventId,
    required this.registrationId,
  });

  static const routeName = 'tablemate';
  static const routePath = '/kesfet/:eventId/kisi/:registrationId';

  final int eventId;
  final int registrationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final query = TablemateQuery(eventId, registrationId);
    final profile = ref.watch(tablemateProvider(query));

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Geri',
          onPressed: () => context.pop(),
        ),
        title: const Text('Profil'),
      ),
      body: switch (profile) {
        AsyncLoading() => const LoadingView(message: 'Profil yükleniyor'),
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Profil yüklenemedi.',
            onRetry: () => ref.invalidate(tablemateProvider(query)),
          ),
        AsyncData(:final value) => TablemateProfileView(profile: value),
      },
    );
  }
}
