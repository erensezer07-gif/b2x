/// Katılımcı plan ekranının parçaları (şartname M8).
///
/// Ayrı dosyada: ekranlar gezinmeyi ve durumu tutuyor, buradakiler saf
/// görünüm. Testler bileşenleri tek tek kurabiliyor.
///
/// **Hiçbirinde sayı yok.** M8: *"'Uyum: %62' gibi bir ifade kullanılmaz."*
/// Sunucu zaten skor göndermiyor; burada da hesaplanmıyor.
library;

import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../profile/models.dart';
import 'models.dart';
import 'schedule.dart';

/// Planın tek satırlık özeti.
class MyPlanHeadline extends StatelessWidget {
  const MyPlanHeadline({super.key, required this.plan});

  final MyPlan plan;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      color: colors.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            Icon(Icons.event_seat_outlined, color: colors.onPrimaryContainer),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Text(
                plan.meetingCount == 0
                    ? 'Bu etkinlikte sana masa ayrılmadı.'
                    : '${plan.seatedCount} turda ${plan.meetingCount} kişiyle '
                        'tanışacaksın.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: colors.onPrimaryContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Slot listesindeki bir satır (M8).
///
/// *"Slot numarası ve saati · masa numarası · kiminle oturacağı."*
class MySlotRow extends StatelessWidget {
  const MySlotRow({super.key, required this.slot, required this.onOpen});

  final MySlot slot;

  /// Boş turda `null` — açılacak bir detay yok.
  final VoidCallback? onOpen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        onTap: onOpen,
        borderRadius: BorderRadius.circular(AppSpacing.sm),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              SizedBox(
                width: 64,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${slot.slotNumber}. Tur', style: theme.textTheme.labelLarge),
                    Text(
                      formatTime(slot.startsAt),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      slot.tableTitle,
                      style: theme.textTheme.titleSmall?.copyWith(
                        color: slot.isFree ? colors.onSurfaceVariant : null,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      // M8: boş tur *"boş bırakılmaz, açıklama yazılır."*
                      slot.isFree
                          ? 'Bu turda serbestsin.'
                          : slot.tablemates
                              .map((mate) => '${mate.displayName} · ${mate.company ?? '—'}')
                              .join('\n'),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              if (onOpen != null)
                Icon(Icons.chevron_right, color: colors.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }
}

/// Tur detayının başlığı: *"masa numarası büyük ve net."* (M8)
class SlotHeadline extends StatelessWidget {
  const SlotHeadline({super.key, required this.slot});

  final MySlot slot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      color: colors.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          children: [
            Text(
              slot.tableTitle,
              textAlign: TextAlign.center,
              style: theme.textTheme.headlineMedium?.copyWith(
                color: colors.onPrimaryContainer,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              '${formatTime(slot.startsAt)} – ${formatTime(slot.endsAt)}',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colors.onPrimaryContainer,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Salon krokisi, katılımcının masası işaretli (M8).
///
/// **Kimin oturduğu çizilmiyor** — sunucu o bilgiyi bu uçtan hiç göndermiyor.
/// Kroki yalnızca "masam salonun neresinde" sorusunu cevaplıyor.
class VenueSketch extends StatelessWidget {
  const VenueSketch({super.key, required this.venue, required this.highlightTableId});

  /// Krokideki bir hücrenin kenarı.
  ///
  /// Editördeki `AppSpacing.gridCell`'den küçük: burada sürükleme yok,
  /// salonun tamamı bir bakışta görünmeli.
  static const cell = 28.0;

  final Venue venue;
  final int? highlightTableId;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final width = (venue.gridWidth ?? 0) * cell;
    final height = (venue.gridHeight ?? 0) * cell;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Salonda yerin', style: theme.textTheme.titleSmall),
        const SizedBox(height: AppSpacing.sm),
        // Geniş salon dar ekrana sığmaz; yatay kaydırma kroki için yeterli.
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Container(
            width: width,
            height: height,
            decoration: BoxDecoration(
              color: colors.surfaceContainerLowest,
              border: Border.all(color: colors.outlineVariant),
              borderRadius: BorderRadius.circular(AppSpacing.sm),
            ),
            child: Stack(
              children: [
                for (final area in venue.areas)
                  Positioned(
                    left: area.gridX * cell,
                    top: area.gridY * cell,
                    width: area.width * cell,
                    height: area.height * cell,
                    child: Container(
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: colors.surfaceContainerHighest,
                        border: Border.all(color: colors.outlineVariant),
                      ),
                      child: Text(
                        area.label,
                        textAlign: TextAlign.center,
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ),
                for (final table in venue.tables.where((item) => item.isPlaced))
                  Positioned(
                    left: table.gridX! * cell,
                    top: table.gridY! * cell,
                    width: cell,
                    height: cell,
                    child: _TableDot(
                      number: table.number,
                      mine: table.id == highlightTableId,
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _TableDot extends StatelessWidget {
  const _TableDot({required this.number, required this.mine});

  final int number;
  final bool mine;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Container(
      margin: const EdgeInsets.all(2),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: mine ? colors.primary : colors.surfaceContainerHigh,
        shape: BoxShape.circle,
        border: Border.all(color: mine ? colors.primary : colors.outlineVariant),
      ),
      child: Text(
        '$number',
        style: theme.textTheme.labelSmall?.copyWith(
          color: mine ? colors.onPrimary : colors.onSurfaceVariant,
        ),
      ),
    );
  }
}

/// Masa arkadaşı kartı ve eşleşme gerekçesi (M8).
class TablemateCard extends StatelessWidget {
  const TablemateCard({super.key, required this.mate, required this.onOpen});

  final Tablemate mate;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final sentences = mate.sentences;

    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        onTap: onOpen,
        borderRadius: BorderRadius.circular(AppSpacing.sm),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  PersonAvatar(photoUrl: mate.photoUrl, name: mate.displayName),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(mate.displayName, style: theme.textTheme.titleSmall),
                        if (mate.title != null)
                          Text(
                            mate.title!,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: colors.onSurfaceVariant,
                            ),
                          ),
                        if (mate.company != null)
                          Text(mate.company!, style: theme.textTheme.bodyMedium),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: colors.onSurfaceVariant),
                ],
              ),
              if (sentences.isNotEmpty) ...[
                const Divider(height: AppSpacing.lg),
                for (final sentence in sentences)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.link,
                          size: AppSpacing.md,
                          color: colors.primary,
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Text(sentence, style: theme.textTheme.bodySmall),
                        ),
                      ],
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Fotoğraf yoksa baş harf.
class PersonAvatar extends StatelessWidget {
  const PersonAvatar({super.key, required this.photoUrl, required this.name, this.radius = 24});

  final String? photoUrl;
  final String name;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final initial = name.trim().isEmpty ? '?' : name.trim().characters.first.toUpperCase();

    return CircleAvatar(
      radius: radius,
      backgroundColor: colors.surfaceContainerHighest,
      // Görsel gelmezse harf kalıyor; ekran çökmemeli.
      foregroundImage: photoUrl == null ? null : NetworkImage(photoUrl!),
      child: Text(initial, style: TextStyle(color: colors.onSurfaceVariant)),
    );
  }
}

/// Masa arkadaşının tam profili (M8).
class TablemateProfileView extends StatelessWidget {
  const TablemateProfileView({super.key, required this.profile});

  final TablemateProfile profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        Center(
          child: PersonAvatar(
            photoUrl: profile.photoUrl,
            name: profile.displayName,
            radius: 44,
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        Text(
          profile.displayName,
          textAlign: TextAlign.center,
          style: theme.textTheme.headlineSmall,
        ),
        if (profile.title != null)
          Text(
            profile.title!,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyMedium?.copyWith(color: colors.onSurfaceVariant),
          ),
        if (profile.company != null)
          Text(
            profile.company!.name,
            textAlign: TextAlign.center,
            style: theme.textTheme.titleSmall,
          ),

        const SizedBox(height: AppSpacing.lg),
        _Facts(profile: profile),

        if (profile.bio != null && profile.bio!.trim().isNotEmpty) ...[
          const SizedBox(height: AppSpacing.lg),
          Text('Hakkında', style: theme.textTheme.titleSmall),
          const SizedBox(height: AppSpacing.sm),
          Text(profile.bio!, style: theme.textTheme.bodyMedium),
        ],

        const SizedBox(height: AppSpacing.lg),
        _TagSection(title: 'Sunduğu', tags: profile.offeredTags),
        const SizedBox(height: AppSpacing.md),
        _TagSection(title: 'Aradığı', tags: profile.soughtTags),
      ],
    );
  }
}

class _Facts extends StatelessWidget {
  const _Facts({required this.profile});

  final TablemateProfile profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    final rows = <(IconData, String)>[
      if (profile.sector != null) (Icons.category_outlined, profile.sector!.name),
      if (profile.city != null && profile.city!.isNotEmpty)
        (Icons.place_outlined, profile.city!),
      if (profile.website != null && profile.website!.isNotEmpty)
        (Icons.language, profile.website!),
      if (profile.linkedinUrl != null && profile.linkedinUrl!.isNotEmpty)
        (Icons.work_outline, profile.linkedinUrl!),
    ];

    if (rows.isEmpty) return const SizedBox.shrink();

    return Column(
      children: [
        for (final (icon, text) in rows)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
            child: Row(
              children: [
                Icon(icon, size: AppSpacing.lg, color: colors.onSurfaceVariant),
                const SizedBox(width: AppSpacing.sm),
                Expanded(child: Text(text, style: theme.textTheme.bodyMedium)),
              ],
            ),
          ),
      ],
    );
  }
}

class _TagSection extends StatelessWidget {
  const _TagSection({required this.title, required this.tags});

  final String title;
  final List<Tag> tags;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: theme.textTheme.titleSmall),
        const SizedBox(height: AppSpacing.sm),
        if (tags.isEmpty)
          Text(
            'Belirtilmemiş.',
            style: theme.textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant),
          )
        else
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            children: [
              for (final tag in tags)
                Chip(label: Text(tag.name), visualDensity: VisualDensity.compact),
            ],
          ),
      ],
    );
  }
}
