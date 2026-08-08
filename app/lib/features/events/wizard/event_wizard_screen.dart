import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/widgets/state_views.dart';
import '../event_controller.dart';
import '../event_list_screen.dart';
import '../models.dart';
import 'basics_step.dart';
import 'capacity_step.dart';
import 'layout_step.dart';
import 'schedule_step.dart';

/// Etkinlik oluşturma sihirbazı (şartname M4).
///
/// *"Organizatörün adım adım ilerlediği bir sihirbaz."* Sıra: temel bilgiler →
/// program → kontenjan → salon düzeni.
///
/// *"Etkinlik taslak olarak kaydedilebilir, sonra devam edilebilir."* Her adım
/// kendi verisini kaydediyor; durum sunucuda, uygulamada değil.
class EventWizardScreen extends ConsumerStatefulWidget {
  const EventWizardScreen({super.key, required this.eventId});

  static const routeName = 'eventWizard';
  static const routePath = '/etkinlikler/:eventId';

  final int eventId;

  @override
  ConsumerState<EventWizardScreen> createState() => _EventWizardScreenState();
}

class _EventWizardScreenState extends ConsumerState<EventWizardScreen> {
  static const _stepCount = 4;

  int _stepIndex = 0;

  void _next() {
    if (_stepIndex + 1 >= _stepCount) {
      _leave();
      return;
    }
    setState(() => _stepIndex++);
  }

  void _back() {
    if (_stepIndex == 0) {
      _leave();
      return;
    }
    setState(() => _stepIndex--);
  }

  /// Sihirbazdan çıkar ve listeyi tazeler.
  ///
  /// Kartta ad, tur sayısı ve durum rozeti görünüyor; sihirbazda değişen her
  /// şey oraya yansımalı. Tazeleme beklenmiyor — gezinme gecikmesin, liste
  /// kendi yükleme durumunu gösterir.
  void _leave() {
    ref.read(eventActionsProvider(widget.eventId)).refreshList();
    context.goNamed(EventListScreen.routeName);
  }

  @override
  Widget build(BuildContext context) {
    final event = ref.watch(eventDetailProvider(widget.eventId));

    return switch (event) {
      AsyncLoading() => const Scaffold(
          body: LoadingView(message: 'Etkinlik yükleniyor'),
        ),
      AsyncError(:final error) => Scaffold(
          appBar: AppBar(
            leading: IconButton(
              icon: const Icon(Icons.arrow_back),
              tooltip: 'Etkinliklere dön',
              onPressed: () => context.goNamed(EventListScreen.routeName),
            ),
          ),
          body: ErrorView(
            message:
                error is ApiException ? error.message : 'Etkinlik yüklenemedi.',
            onRetry: () =>
                ref.invalidate(eventDetailProvider(widget.eventId)),
          ),
        ),
      AsyncData(:final value) => _buildStep(value),
    };
  }

  Widget _buildStep(EventDetail event) {
    final stepWidget = switch (_stepIndex) {
      0 => EventBasicsStep(
          key: const ValueKey('event-basics'),
          event: event,
          stepIndex: 0,
          stepCount: _stepCount,
          onCompleted: _next,
        ),
      1 => EventScheduleStep(
          key: const ValueKey('event-schedule'),
          event: event,
          stepIndex: 1,
          stepCount: _stepCount,
          onCompleted: _next,
          onBack: _back,
        ),
      2 => EventCapacityStep(
          key: const ValueKey('event-capacity'),
          event: event,
          stepIndex: 2,
          stepCount: _stepCount,
          onCompleted: _next,
          onBack: _back,
        ),
      _ => EventLayoutStep(
          key: const ValueKey('event-layout'),
          event: event,
          stepIndex: 3,
          stepCount: _stepCount,
          onCompleted: _next,
          onBack: _back,
        ),
    };

    if (event.status == EventStatus.draft) {
      return stepWidget;
    }

    return Column(
      children: [
        MaterialBanner(
          content: const Text(
            'Bu etkinliğin kayıtları açıldığı için bilgileri değiştirilemez.',
          ),
          leading: const Icon(Icons.lock_outline),
          backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
          actions: const [SizedBox.shrink()],
        ),
        Expanded(child: stepWidget),
      ],
    );
  }
}
