import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import '../profile/models.dart';
import '../profile/profile_controller.dart';
import 'event_controller.dart';
import 'models.dart';
import 'my_plan_widgets.dart';
import 'public_event_screen.dart';

/// Görüşme talepleri — katılımcı listesi (şartname M9).
///
/// *"Katılımcı, etkinliğe kabul edilmiş diğer katılımcıların listesini görür.
/// Arama ve sektöre göre filtreleme var."*
///
/// Liste tam profil açmıyor: ad, unvan, şirket, sektör. Tam profil yalnızca
/// aynı masaya düşen kişiler için (Bölüm 7) — kapı sunucuda.
///
/// **Kimin bana talep gönderdiği hiçbir yerde yok.** M9: *"Talep gönderildiği
/// kişiye bildirilmez."* Sunucuda öyle bir uç yazılmadı.
class ParticipantsScreen extends ConsumerStatefulWidget {
  const ParticipantsScreen({super.key, required this.eventId});

  static const routeName = 'eventParticipants';
  static const routePath = '/kesfet/:eventId/katilimcilar';

  final int eventId;

  @override
  ConsumerState<ParticipantsScreen> createState() => _ParticipantsScreenState();
}

class _ParticipantsScreenState extends ConsumerState<ParticipantsScreen> {
  /// Yazarken her tuşta istek atmamak için bekleme.
  static const _typingDelay = Duration(milliseconds: 350);

  final _searchController = TextEditingController();
  Timer? _typing;

  String? _search;
  int? _sectorId;

  /// Talepten sonra uçtan gelen taze liste — sağlayıcının değerini geçersiz
  /// kılıyor. Süzgeç değişince sıfırlanıyor (Aşama 8'deki takas kalıbı).
  ParticipantList? _fresh;

  bool _busy = false;
  String? _error;

  ParticipantQuery get _query =>
      ParticipantQuery(widget.eventId, search: _search, sectorId: _sectorId);

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
      setState(() {
        _search = value.trim().isEmpty ? null : value.trim();
        _fresh = null;
      });
    });
  }

  void _onSectorChanged(int? sectorId) {
    setState(() {
      _sectorId = sectorId;
      _fresh = null;
    });
  }

  Future<void> _act(Future<ParticipantList> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final list = await action();
      if (!mounted) return;
      setState(() {
        _fresh = list;
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

  @override
  Widget build(BuildContext context) {
    final listing = ref.watch(participantsProvider(_query));
    final sectors = ref.watch(sectorsProvider);
    final view = _fresh ?? listing.asData?.value;

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Etkinliğe dön',
          onPressed: () => context.goNamed(
            PublicEventScreen.routeName,
            pathParameters: {'eventId': '${widget.eventId}'},
          ),
        ),
        title: const Text('Kimlerle görüşmek istersin'),
      ),
      body: switch (view) {
        null when listing is AsyncError => ErrorView(
            message: listing.error is ApiException
                ? (listing.error! as ApiException).message
                : 'Katılımcılar yüklenemedi.',
            onRetry: () => ref.invalidate(participantsProvider(_query)),
          ),
        null => const LoadingView(message: 'Katılımcılar yükleniyor'),
        final loaded => _buildBody(loaded, sectors.asData?.value ?? const []),
      },
    );
  }

  Widget _buildBody(ParticipantList list, List<Sector> sectors) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final actions = ref.read(requestActionsProvider(widget.eventId));

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            children: [
              _QuotaCard(list: list),
              const SizedBox(height: AppSpacing.md),
              TextField(
                controller: _searchController,
                onChanged: _onSearchChanged,
                decoration: const InputDecoration(
                  labelText: 'Ad veya şirket ara',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
              if (sectors.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.sm),
                _SectorFilter(
                  sectors: sectors,
                  selected: _sectorId,
                  onSelect: _busy ? null : _onSectorChanged,
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                _ErrorStrip(
                  message: _error!,
                  onDismiss: () => setState(() => _error = null),
                ),
              ],
            ],
          ),
        ),
        if (_busy) const LinearProgressIndicator(minHeight: 2),
        Expanded(
          child: list.participants.isEmpty
              ? EmptyView(
                  icon: Icons.person_search_outlined,
                  message: _search != null || _sectorId != null
                      ? 'Bu aramaya uyan katılımcı yok.'
                      : 'Bu etkinlikte henüz başka katılımcı yok.',
                )
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md,
                    0,
                    AppSpacing.md,
                    AppSpacing.md,
                  ),
                  itemCount: list.participants.length,
                  itemBuilder: (context, index) {
                    final person = list.participants[index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: _ParticipantCard(
                        person: person,
                        // Hak dolduysa yeni talep kapalı ama geri çekme açık.
                        canRequest: list.requestsOpen &&
                            (!list.exhausted || person.requested),
                        busy: _busy,
                        onRequest: () => _act(() => actions.send(person.registrationId)),
                        onWithdraw: () =>
                            _act(() => actions.withdraw(person.myRequestId!)),
                      ),
                    );
                  },
                ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Text(
              // M9'un birebir cümlesi.
              'Talepleriniz eşleştirmede öncelikli değerlendirilir, ancak '
              'karşılanacağı garanti edilmez.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Kalan hak ve talebin kapalı olup olmadığı.
class _QuotaCard extends StatelessWidget {
  const _QuotaCard({required this.list});

  final ParticipantList list;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final closed = !list.requestsOpen;

    return Card(
      margin: EdgeInsets.zero,
      color: closed ? colors.surfaceContainerHighest : colors.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            Icon(
              closed ? Icons.lock_clock : Icons.handshake_outlined,
              color: closed ? colors.onSurfaceVariant : colors.onPrimaryContainer,
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Text(
                closed
                    ? 'Görüşme talepleri kapandı. Gönderdiklerin planda '
                        'değerlendirilecek.'
                    : list.quotaSentence,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color:
                      closed ? colors.onSurfaceVariant : colors.onPrimaryContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectorFilter extends StatelessWidget {
  const _SectorFilter({
    required this.sectors,
    required this.selected,
    required this.onSelect,
  });

  final List<Sector> sectors;
  final int? selected;
  final void Function(int?)? onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: AppSpacing.buttonHeight,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: sectors.length + 1,
        separatorBuilder: (context, index) => const SizedBox(width: AppSpacing.sm),
        itemBuilder: (context, index) {
          if (index == 0) {
            return Center(
              child: ChoiceChip(
                label: const Text('Hepsi'),
                selected: selected == null,
                onSelected: onSelect == null ? null : (_) => onSelect!(null),
              ),
            );
          }
          final sector = sectors[index - 1];
          return Center(
            child: ChoiceChip(
              label: Text(sector.name),
              selected: selected == sector.id,
              onSelected: onSelect == null ? null : (_) => onSelect!(sector.id),
            ),
          );
        },
      ),
    );
  }
}

/// Listedeki bir katılımcı (M9: *"ad, unvan, şirket, sektör"*).
class _ParticipantCard extends StatelessWidget {
  const _ParticipantCard({
    required this.person,
    required this.canRequest,
    required this.busy,
    required this.onRequest,
    required this.onWithdraw,
  });

  final ParticipantRow person;
  final bool canRequest;
  final bool busy;
  final VoidCallback onRequest;
  final VoidCallback onWithdraw;

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
            PersonAvatar(photoUrl: person.photoUrl, name: person.displayName),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(person.displayName, style: theme.textTheme.titleSmall),
                  if (person.title != null)
                    Text(
                      person.title!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                  if (person.company != null)
                    Text(person.company!, style: theme.textTheme.bodyMedium),
                  if (person.sector != null)
                    Padding(
                      padding: const EdgeInsets.only(top: AppSpacing.xs),
                      child: Text(
                        person.sector!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            if (person.requested)
              TextButton.icon(
                onPressed: busy || !canRequest ? null : onWithdraw,
                icon: const Icon(Icons.check_circle, size: AppSpacing.md),
                label: const Text('İstedin'),
              )
            else
              OutlinedButton(
                onPressed: busy || !canRequest ? null : onRequest,
                child: const Text('Görüşmek isterim'),
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
