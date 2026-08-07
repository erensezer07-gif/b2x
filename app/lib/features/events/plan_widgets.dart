/// Plan önizleme ekranının parçaları (şartname M7).
///
/// Ayrı dosyada: `plan_screen.dart` takas mantığını tutuyor, buradakiler saf
/// görünüm. Testler bileşenleri tek tek kurabiliyor.
library;

import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import 'models.dart';

/// Tur seçici (M7: *"slot seçici üstte"*).
///
/// Yatay kaydırmalı: sekiz turlu bir etkinlikte sekiz sekme dar ekrana
/// sığmazdı, `TabBar` de metni okunmaz hâle getirirdi.
class SlotSelector extends StatelessWidget {
  const SlotSelector({
    super.key,
    required this.slotCount,
    required this.selected,
    required this.onSelect,
  });

  final int slotCount;
  final int selected;

  /// `null` ise seçici kapalı — takas sürerken tur değiştirilmemeli.
  final void Function(int)? onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: AppSpacing.buttonHeight + AppSpacing.md,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
        itemCount: slotCount,
        separatorBuilder: (context, index) => const SizedBox(width: AppSpacing.sm),
        itemBuilder: (context, index) {
          final number = index + 1;
          return Center(
            child: ChoiceChip(
              label: Text('$number. Tur'),
              selected: number == selected,
              onSelected: onSelect == null ? null : (_) => onSelect!(number),
            ),
          );
        },
      ),
    );
  }
}

/// Takasın nerede olduğunu söyleyen şerit.
///
/// Seçim görünmez bir durum olamaz: kullanıcı bir kişiye dokunduktan sonra
/// "şimdi ne olacak" sorusunun cevabı ekranda yazmalı.
class SwapHint extends StatelessWidget {
  const SwapHint({super.key, required this.selected, required this.onCancel});

  final String? selected;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final active = selected != null;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: active ? colors.primaryContainer : colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.sm),
      ),
      child: Row(
        children: [
          Icon(
            active ? Icons.swap_horiz : Icons.touch_app_outlined,
            size: AppSpacing.lg,
            color: active ? colors.onPrimaryContainer : colors.onSurfaceVariant,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              active
                  ? '$selected seçildi. Yerini değiştirmek için başka birine '
                      'ya da boş bir masaya dokun.'
                  : 'Yer değiştirmek için önce bir kişiye dokun.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: active ? colors.onPrimaryContainer : colors.onSurfaceVariant,
              ),
            ),
          ),
          if (active)
            TextButton(onPressed: onCancel, child: const Text('Vazgeç')),
        ],
      ),
    );
  }
}

/// Takas sonrası uyarılar (M7).
///
/// *"Organizatör uyarıya rağmen devam edebilir — ama ne yaptığını bilerek
/// yapar."* Takas zaten yapıldı; bu şerit ne olduğunu söylüyor, geri almıyor.
class SwapWarningBanner extends StatelessWidget {
  const SwapWarningBanner({
    super.key,
    required this.warnings,
    required this.onDismiss,
  });

  final List<SwapWarning> warnings;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      color: colors.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.warning_amber_outlined, color: colors.onSurfaceVariant),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text('Takas yapıldı, ama dikkat',
                      style: theme.textTheme.titleSmall),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  tooltip: 'Uyarıları kapat',
                  onPressed: onDismiss,
                ),
              ],
            ),
            for (final warning in warnings)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                child: Text(
                  '• ${warning.message}',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Takasın hiç yapılamadığı durum.
///
/// Uyarıdan ayrı bir şerit: uyarıda takas oldu, burada olmadı. İkisini aynı
/// kutuya koymak organizatörü yanıltırdı.
class SwapErrorBanner extends StatelessWidget {
  const SwapErrorBanner({
    super.key,
    required this.message,
    required this.onDismiss,
  });

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

/// Bir masa ve oturanları (M7).
///
/// Boş masa da çiziliyor: organizatör boş sandalyeye taşıyabilmeli.
class TableCard extends StatelessWidget {
  const TableCard({
    super.key,
    required this.table,
    required this.selectedAssignmentId,
    required this.onTapTable,
    required this.onTapPerson,
    required this.onTogglePin,
  });

  final SeatedTable table;
  final int? selectedAssignmentId;

  /// `null` ise masaya taşıma kapalı — elde seçili kimse yok.
  final VoidCallback? onTapTable;

  final void Function(SeatedPerson) onTapPerson;
  final void Function(SeatedPerson) onTogglePin;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.md,
              AppSpacing.sm,
              AppSpacing.sm,
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(table.title, style: theme.textTheme.titleSmall),
                ),
                Text(
                  '${table.occupants.length}/${table.capacity}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    // Kapasite aşıldıysa sayı kendisi söylesin.
                    color: table.occupants.length > table.capacity
                        ? colors.error
                        : colors.onSurfaceVariant,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                QualityBadge(
                  quality: table.quality,
                  occupantCount: table.occupants.length,
                ),
              ],
            ),
          ),
          if (table.isEmpty)
            _EmptySeats(onTap: onTapTable)
          else
            for (final person in table.occupants)
              _PersonRow(
                person: person,
                selected: person.assignmentId == selectedAssignmentId,
                onTap: () => onTapPerson(person),
                onTogglePin: () => onTogglePin(person),
              ),
          // Dolu olmayan masaya da taşınabilmeli.
          if (!table.isEmpty && !table.isFull && onTapTable != null)
            _AddHere(onTap: onTapTable!),
        ],
      ),
    );
  }
}

/// Masa kalite rozeti (M7: *"sayı değil, üç seviye"*).
///
/// Dördüncü bir hâl var: **tek kişilik masa.** Sunucu ona kalite vermiyor —
/// skor en zayıf ikili bağ (9.4), tek kişide bağ yok. Ama rozete "Boş" yazmak
/// yanlış olurdu, masada biri oturuyor. Ayrı bir etiket alıyor ve kusur rengiyle
/// çiziliyor: tek kişilik masa 9.5'in kesin kuralını çiğniyor.
class QualityBadge extends StatelessWidget {
  const QualityBadge({
    super.key,
    required this.quality,
    this.occupantCount = 0,
  });

  final TableQuality quality;
  final int occupantCount;

  @override
  Widget build(BuildContext context) {
    final palette = AppQualityColors.of(context);
    final lonely = quality == TableQuality.empty && occupantCount > 0;

    final color = switch (quality) {
      TableQuality.good => palette.good,
      TableQuality.fair => palette.fair,
      TableQuality.weak => palette.weak,
      TableQuality.empty => lonely ? palette.weak : palette.empty,
    };

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(AppSpacing.sm),
        border: Border.all(color: color),
      ),
      child: Text(
        lonely ? 'Tek kişi' : quality.label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(color: color),
      ),
    );
  }
}

class _PersonRow extends StatelessWidget {
  const _PersonRow({
    required this.person,
    required this.selected,
    required this.onTap,
    required this.onTogglePin,
  });

  final SeatedPerson person;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onTogglePin;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Material(
      color: selected ? colors.primaryContainer : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          child: Row(
            children: [
              Icon(
                selected ? Icons.radio_button_checked : Icons.person_outline,
                size: AppSpacing.lg,
                color: selected ? colors.onPrimaryContainer : colors.onSurfaceVariant,
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(person.displayName, style: theme.textTheme.bodyMedium),
                    if (person.company != null)
                      Text(
                        person.company!,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: selected
                              ? colors.onPrimaryContainer
                              : colors.onSurfaceVariant,
                        ),
                      ),
                  ],
                ),
              ),
              IconButton(
                icon: Icon(
                  person.isPinned ? Icons.push_pin : Icons.push_pin_outlined,
                  color: person.isPinned ? colors.primary : colors.onSurfaceVariant,
                ),
                tooltip: person.isPinned
                    ? 'Sabitlemeyi kaldır'
                    : 'Sabitle — motor tekrar çalışsa da burada kalır',
                onPressed: onTogglePin,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Boş masanın gövdesi. Dokunulunca seçili kişi buraya taşınıyor.
class _EmptySeats extends StatelessWidget {
  const _EmptySeats({required this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          0,
          AppSpacing.md,
          AppSpacing.md,
        ),
        child: Row(
          children: [
            Icon(
              Icons.chair_outlined,
              size: AppSpacing.lg,
              color: colors.onSurfaceVariant,
            ),
            const SizedBox(width: AppSpacing.sm),
            Text(
              onTap == null ? 'Bu masa boş.' : 'Boş — buraya taşımak için dokun.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Yarı dolu masanın altındaki "buraya taşı" satırı.
class _AddHere extends StatelessWidget {
  const _AddHere({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.xs,
          AppSpacing.md,
          AppSpacing.md,
        ),
        child: Row(
          children: [
            Icon(Icons.add, size: AppSpacing.lg, color: colors.primary),
            const SizedBox(width: AppSpacing.sm),
            Text(
              'Buraya taşı',
              style: theme.textTheme.bodySmall?.copyWith(color: colors.primary),
            ),
          ],
        ),
      ),
    );
  }
}

/// Özet paneli (M7).
///
/// *"En az görüşme alan kişinin sayısı"* en önemli sayı: ortalama iyi görünen
/// bir plan tek bir kişiyi ortada bırakmış olabilir. Bu yüzden en üstte ve
/// vurgulu.
class PlanSummaryPanel extends StatelessWidget {
  const PlanSummaryPanel({super.key, required this.plan, this.onOpenSlot});

  final PlanSummary plan;

  /// Karşılanmayan bir talepten ilgili tura gitmek için (M9).
  final void Function(int slotNumber)? onOpenSlot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _Figure(
                  label: 'En az görüşme',
                  value: '${plan.minMeetingsPerPerson ?? 0}',
                  highlight: true,
                ),
                _Figure(
                  label: 'Toplam görüşme',
                  value: '${plan.totalMeetings ?? 0}',
                ),
                _Figure(
                  label: 'Masaya oturan',
                  value: '${plan.participantCount}',
                ),
                if (plan.totalRequests > 0)
                  _Figure(
                    label: 'Karşılanan talep',
                    value: '${plan.satisfiedRequests}/${plan.totalRequests}',
                  ),
              ],
            ),
            if (plan.unmetMutual.isNotEmpty) ...[
              const Divider(height: AppSpacing.lg),
              UnmetRequestsSection(
                unmet: plan.unmetMutual,
                oneWay: plan.unmetOneWay,
                onOpenSlot: onOpenSlot,
              ),
            ] else if (plan.unmetOneWay.isNotEmpty) ...[
              const Divider(height: AppSpacing.lg),
              UnmetRequestsSection(
                unmet: const [],
                oneWay: plan.unmetOneWay,
                onOpenSlot: onOpenSlot,
              ),
            ],
            if (plan.unmatched.isNotEmpty) ...[
              const Divider(height: AppSpacing.lg),
              Text(
                'Hiç eşleşmeyen ${plan.unmatched.length} kişi',
                style: theme.textTheme.titleSmall?.copyWith(color: colors.error),
              ),
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  for (final name in plan.unmatched)
                    Chip(
                      label: Text(name),
                      visualDensity: VisualDensity.compact,
                    ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Bu kişiler hiçbir turda masaya oturmadı. Boş sandalyelere '
                'elle yerleştirebilirsin.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
              ),
            ],
            // Gelmeyenler yukarıdaki sayıların hiçbirine girmiyor (M7), ama
            // yok da sayılmıyorlar: kaç kişi olduğu burada yazıyor. İkisi
            // karışırsa "en az görüşme" gelmeyenlerin sıfırına düşer ve
            // "hiç eşleşmeyen" listesi salonda olmayan insanları gösterir.
            if (plan.absentCount > 0) ...[
              const Divider(height: AppSpacing.lg),
              Text(
                '${plan.absentCount} kişi gelmedi',
                style: theme.textTheme.titleSmall,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Yukarıdaki sayılar onları içermiyor.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Figure extends StatelessWidget {
  const _Figure({
    required this.label,
    required this.value,
    this.highlight = false,
  });

  final String label;
  final String value;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: theme.textTheme.headlineSmall?.copyWith(
              color: highlight ? colors.primary : null,
            ),
          ),
          Text(
            label,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}


/// Karşılanmayan talepler (şartname M9, organizatör görünümü).
///
/// *"Karşılanmış bir talebin operasyonel karşılığı yoktur."* Bu yüzden yalnızca
/// karşılanmayanlar geliyor ve iki grup ayrı duruyor:
///
/// * **Karşılıklı** — ikisi de birbirini istemiş, motor yine de aynı masaya
///   koyamamış. M9 buna "neredeyse kesin eşleşme" diyor; kaçırıldıysa gerçek
///   bir kusur. Her satırdan takas ekranına gidiliyor.
/// * **Tek taraflı** — kapalı bir listede, bilgi olarak. Zorlanması
///   **önerilmiyor**: karşı taraf için değerli olduğu belli değil ve zorlamak
///   onun planını bozar.
class UnmetRequestsSection extends StatelessWidget {
  const UnmetRequestsSection({
    super.key,
    required this.unmet,
    required this.oneWay,
    required this.onOpenSlot,
  });

  final List<UnmetRequest> unmet;
  final List<UnmetRequest> oneWay;
  final void Function(int slotNumber)? onOpenSlot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (unmet.isNotEmpty) ...[
          Row(
            children: [
              Icon(Icons.warning_amber_outlined, color: colors.error),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  'Karşılanmayan ${unmet.length} karşılıklı talep',
                  style: theme.textTheme.titleSmall?.copyWith(color: colors.error),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'İkisi de birbirini istemiş ama aynı masaya düşmemiş. '
            'Elle düzeltilebilir.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final item in unmet) _UnmetRow(item: item, onOpenSlot: onOpenSlot),
        ],
        if (oneWay.isNotEmpty) ...[
          if (unmet.isNotEmpty) const SizedBox(height: AppSpacing.sm),
          Theme(
            // Açılır listenin kendi çizgileri panelin içinde fazla duruyor.
            data: theme.copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: EdgeInsets.zero,
              title: Text(
                'Karşılanmayan ${oneWay.length} tek taraflı talep',
                style: theme.textTheme.titleSmall,
              ),
              subtitle: Text(
                'Zorlanması önerilmez: karşı taraf için değerli olduğu belli '
                'değil.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
              ),
              children: [
                for (final item in oneWay)
                  _UnmetRow(item: item, onOpenSlot: onOpenSlot),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _UnmetRow extends StatelessWidget {
  const _UnmetRow({required this.item, required this.onOpenSlot});

  final UnmetRequest item;
  final void Function(int slotNumber)? onOpenSlot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final slot = item.fixableSlot;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        children: [
          Expanded(child: Text(item.pair, style: theme.textTheme.bodyMedium)),
          if (slot != null && onOpenSlot != null)
            TextButton(
              onPressed: () => onOpenSlot!(slot),
              child: Text('$slot. Tur'),
            )
          else
            Text(
              // İkisi hiçbir turda birlikte oturmuyor: takasla düzeltilecek
              // bir yer yok, önce birinin masaya oturması gerekiyor.
              'Düzeltilecek tur yok',
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
        ],
      ),
    );
  }
}

/// Yeri değişenler (şartname M10, 9.8).
///
/// *"Yeni versiyon organizatöre gösterilir, kimin yeri değişti listelenir,
/// organizatör onaylayınca yayına geçer."*
///
/// 9.8'in sözü burada ölçülüyor: *"gerekmedikçe kimseyi kıpırdatma."* Liste
/// kısaysa mod çalışıyor demektir.
class SeatChangesPanel extends StatelessWidget {
  const SeatChangesPanel({super.key, required this.changes});

  final PlanChanges changes;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    if (changes.isEmpty) {
      return Card(
        margin: EdgeInsets.zero,
        color: colors.surfaceContainerHighest,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              Icon(Icons.done_all, color: colors.onSurfaceVariant),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Text(
                  'Kimsenin yeri değişmedi.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.compare_arrows, color: colors.primary),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    '${changes.movedPeople} kişinin yeri değişti',
                    style: theme.textTheme.titleSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Önceki versiyona göre. Diğer herkes yerinde kaldı.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            for (final change in changes.changes)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                child: Row(
                  children: [
                    SizedBox(
                      width: 56,
                      child: Text(
                        '${change.slotNumber}. Tur',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(change.name, style: theme.textTheme.bodyMedium),
                    ),
                    Text(
                      change.description,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colors.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

