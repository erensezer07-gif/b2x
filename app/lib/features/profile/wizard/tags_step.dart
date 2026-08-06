import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/state_views.dart';
import '../models.dart';
import '../profile_controller.dart';
import 'wizard_step.dart';

/// Etiketin profildeki yönü.
enum TagDirection { offered, sought }

/// Adım 3 ve 4 — ne sunuyorum / ne arıyorum (şartname M2, Bölüm 6).
///
/// İki adım **aynı bileşeni** kullanıyor, çünkü iki liste de **aynı etiket
/// havuzundan** seçiliyor. Şartname bunu açıkça istiyor: *"A'nın sunduğu ile
/// B'nin aradığı aynı etikete denk geliyorsa eşleşme var demektir. İki ayrı
/// liste olursa karşılaştırma yapılamaz."*
///
/// En az üç etiket gerekiyor (M2); altındayken ileri düğmesi kapalı ve kaç
/// tane kaldığı yazıyor.
class TagsStep extends ConsumerStatefulWidget {
  const TagsStep({
    super.key,
    required this.profile,
    required this.direction,
    required this.stepIndex,
    required this.stepCount,
    required this.onCompleted,
    required this.onBack,
  });

  final Profile profile;
  final TagDirection direction;
  final int stepIndex;
  final int stepCount;
  final VoidCallback onCompleted;
  final VoidCallback onBack;

  static const minimumTags = 3;

  @override
  ConsumerState<TagsStep> createState() => _TagsStepState();
}

class _TagsStepState extends ConsumerState<TagsStep> {
  late Set<int> _selected;
  bool _isSaving = false;
  String? _errorMessage;

  bool get _isOffering => widget.direction == TagDirection.offered;

  @override
  void initState() {
    super.initState();
    final existing =
        _isOffering ? widget.profile.offeredTags : widget.profile.soughtTags;
    _selected = existing.map((tag) => tag.id).toSet();
  }

  Future<void> _saveAndContinue() async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      await ref.read(profileControllerProvider.notifier).save({
        if (_isOffering)
          'offered_tag_ids': _selected.toList()
        else
          'sought_tag_ids': _selected.toList(),
      });
      widget.onCompleted();
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final categories = ref.watch(tagCategoriesProvider);
    final remaining = TagsStep.minimumTags - _selected.length;

    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: _isOffering ? 'Ne sunuyorsun?' : 'Ne arıyorsun?',
      description: _isOffering
          ? 'Şirketinin sunduğu hizmet ve ürünleri seç. Bunları arayan kişilerle '
              'eşleştirileceksin.'
          : 'İhtiyacın olanları seç. Bunları sunan kişilerle eşleştirileceksin.',
      isSaving: _isSaving,
      errorMessage: _errorMessage,
      onBack: widget.onBack,
      onNext: remaining <= 0 ? _saveAndContinue : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _SelectionCounter(
            selectedCount: _selected.length,
            remaining: remaining,
          ),
          const SizedBox(height: AppSpacing.md),
          switch (categories) {
            AsyncLoading() => const Padding(
                padding: EdgeInsets.all(AppSpacing.xl),
                child: LoadingView(message: 'Etiketler yükleniyor'),
              ),
            AsyncError(:final error) => ErrorView(
                message: error is ApiException
                    ? error.message
                    : 'Etiket listesi yüklenemedi.',
                onRetry: () => ref.invalidate(tagCategoriesProvider),
              ),
            AsyncData(:final value) when value.isEmpty => const EmptyView(
                message: 'Etiket havuzu boş görünüyor. '
                    'Organizatörle iletişime geçebilirsin.',
              ),
            AsyncData(:final value) => _CategoryList(
                categories: value,
                selected: _selected,
                enabled: !_isSaving,
                onToggled: (tagId) => setState(() {
                  if (!_selected.remove(tagId)) _selected.add(tagId);
                }),
              ),
          },
        ],
      ),
    );
  }
}

/// Kaç etiket seçildi, kaç tane daha gerekiyor.
class _SelectionCounter extends StatelessWidget {
  const _SelectionCounter({required this.selectedCount, required this.remaining});

  final int selectedCount;
  final int remaining;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final satisfied = remaining <= 0;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: satisfied
            ? theme.colorScheme.surfaceContainerHighest
            : theme.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(AppSpacing.sm),
      ),
      child: Row(
        children: [
          Icon(
            satisfied ? Icons.check_circle_outline : Icons.info_outline,
            color: satisfied
                ? theme.colorScheme.onSurfaceVariant
                : theme.colorScheme.onErrorContainer,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              satisfied
                  ? '$selectedCount etiket seçtin'
                  : 'En az ${TagsStep.minimumTags} etiket gerekli — '
                      '$remaining tane daha seç',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: satisfied
                    ? theme.colorScheme.onSurfaceVariant
                    : theme.colorScheme.onErrorContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Kategorileri gezilebilir panel listesi olarak gösterir.
///
/// Şartname Bölüm 6: *"Kullanıcı kategorileri gezerek seçer, serbest metin
/// yazamaz."*
class _CategoryList extends StatelessWidget {
  const _CategoryList({
    required this.categories,
    required this.selected,
    required this.enabled,
    required this.onToggled,
  });

  final List<TagCategory> categories;
  final Set<int> selected;
  final bool enabled;
  final ValueChanged<int> onToggled;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (final category in categories)
          Card(
            margin: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: ExpansionTile(
              title: Text(category.name),
              subtitle: _CategorySubtitle(
                selectedCount:
                    category.tags.where((tag) => selected.contains(tag.id)).length,
              ),
              // İçinde seçim varsa kategori açık başlar: kullanıcı geri
              // döndüğünde ne seçtiğini araması gerekmesin.
              initiallyExpanded:
                  category.tags.any((tag) => selected.contains(tag.id)),
              childrenPadding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.md,
              ),
              children: [
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.sm,
                  children: [
                    for (final tag in category.tags)
                      FilterChip(
                        label: Text(tag.name),
                        selected: selected.contains(tag.id),
                        onSelected: enabled ? (_) => onToggled(tag.id) : null,
                      ),
                  ],
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _CategorySubtitle extends StatelessWidget {
  const _CategorySubtitle({required this.selectedCount});

  final int selectedCount;

  @override
  Widget build(BuildContext context) {
    if (selectedCount == 0) return const SizedBox.shrink();
    return Text('$selectedCount seçili');
  }
}
