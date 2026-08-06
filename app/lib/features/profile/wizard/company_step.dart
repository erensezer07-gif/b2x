import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/state_views.dart';
import '../models.dart';
import '../profile_controller.dart';
import 'wizard_step.dart';

/// Adım 2 — şirket ve sektör (şartname M2, Bölüm 6).
///
/// *"Kullanıcı yazarken mevcut şirketler önerilir, varsa seçer, yoksa yeni
/// oluşturulur."*
///
/// Bu adım eşleştirmenin en kritik kuralını besliyor: aynı şirketten iki kişi
/// aynı masaya oturamaz (9.5). Karşılaştırma serbest metinle değil şirket
/// kimliğiyle yapıldığı için kullanıcının mevcut kaydı seçmesi önemli —
/// tekilleştirmeyi sunucu da yapıyor ama öneri listesi kullanıcıyı doğru
/// kayda yönlendiriyor.
class CompanyStep extends ConsumerStatefulWidget {
  const CompanyStep({
    super.key,
    required this.profile,
    required this.stepIndex,
    required this.stepCount,
    required this.onCompleted,
    required this.onBack,
  });

  final Profile profile;
  final int stepIndex;
  final int stepCount;
  final VoidCallback onCompleted;
  final VoidCallback onBack;

  @override
  ConsumerState<CompanyStep> createState() => _CompanyStepState();
}

class _CompanyStepState extends ConsumerState<CompanyStep> {
  late final TextEditingController _companyName;
  Timer? _debounce;

  String _query = '';
  Company? _selectedCompany;
  int? _selectedSectorId;

  bool _isSaving = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _selectedCompany = widget.profile.company;
    _selectedSectorId = widget.profile.sector?.id;
    _companyName = TextEditingController(text: widget.profile.company?.name ?? '');
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _companyName.dispose();
    super.dispose();
  }

  /// Her tuş vuruşunda istek atmamak için kısa bir bekleme.
  void _onCompanyChanged(String value) {
    // Yazmaya devam edildiğinde önceki seçim geçersiz: kullanıcı başka bir
    // şirket arıyor olabilir.
    setState(() => _selectedCompany = null);

    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (mounted) setState(() => _query = value);
    });
  }

  bool get _canContinue =>
      _companyName.text.trim().isNotEmpty && _selectedSectorId != null;

  Future<void> _saveAndContinue() async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      // Listeden seçilmediyse şirket burada oluşturuluyor. Sunucu aynı şirketin
      // farklı yazımlarını tek kimliğe indirgediği için "yeni" dediğimiz kayıt
      // mevcut bir şirkete de denk gelebilir — çağıran için ikisi aynı.
      final company = _selectedCompany ??
          await ref
              .read(profileRepositoryProvider)
              .findOrCreateCompany(_companyName.text.trim());

      await ref.read(profileControllerProvider.notifier).save({
        'company_id': company.id,
        'sector_id': _selectedSectorId,
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
    final sectors = ref.watch(sectorsProvider);

    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: 'Şirketin ve sektörün',
      description:
          'Aynı şirketten iki kişi aynı masaya oturmaz. Bu yüzden şirketini '
          'listeden seçmen önemli.',
      isSaving: _isSaving,
      errorMessage: _errorMessage,
      onBack: widget.onBack,
      onNext: _canContinue ? _saveAndContinue : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _companyName,
            enabled: !_isSaving,
            textCapitalization: TextCapitalization.words,
            decoration: InputDecoration(
              labelText: 'Şirket adı',
              helperText: _selectedCompany == null
                  ? 'Yazmaya başla, kayıtlı şirketler önerilir'
                  : 'Kayıtlı şirket seçildi',
              suffixIcon: _selectedCompany == null
                  ? null
                  : const Icon(Icons.check_circle_outline),
            ),
            onChanged: (value) {
              _onCompanyChanged(value);
              setState(() {});
            },
          ),
          const SizedBox(height: AppSpacing.sm),
          _CompanySuggestions(
            query: _query,
            selected: _selectedCompany,
            onSelected: (company) {
              setState(() {
                _selectedCompany = company;
                _companyName.text = company.name;
                _query = '';
              });
            },
          ),
          const SizedBox(height: AppSpacing.lg),
          Text('Sektör', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpacing.sm),
          switch (sectors) {
            AsyncLoading() => const Padding(
                padding: EdgeInsets.all(AppSpacing.lg),
                child: LoadingView(),
              ),
            AsyncError(:final error) => ErrorView(
                message: error is ApiException
                    ? error.message
                    : 'Sektör listesi yüklenemedi.',
                onRetry: () => ref.invalidate(sectorsProvider),
              ),
            AsyncData(:final value) when value.isEmpty => const EmptyView(
                message: 'Sektör listesi boş görünüyor.',
              ),
            AsyncData(:final value) => _SectorPicker(
                sectors: value,
                selectedId: _selectedSectorId,
                enabled: !_isSaving,
                onSelected: (id) => setState(() => _selectedSectorId = id),
              ),
          },
        ],
      ),
    );
  }
}

/// Yazarken çıkan şirket önerileri.
class _CompanySuggestions extends ConsumerWidget {
  const _CompanySuggestions({
    required this.query,
    required this.selected,
    required this.onSelected,
  });

  final String query;
  final Company? selected;
  final ValueChanged<Company> onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Kullanıcı seçim yaptıysa liste kapanır.
    if (selected != null || query.trim().length < 2) {
      return const SizedBox.shrink();
    }

    final results = ref.watch(companySearchProvider(query));

    return switch (results) {
      AsyncLoading() => const LinearProgressIndicator(),
      // Arama başarısız olursa kullanıcı yine de devam edebilmeli: şirket
      // yazdığı adla oluşturulur. Bu yüzden hata sessizce yutuluyor.
      AsyncError() => const SizedBox.shrink(),
      AsyncData(:final value) when value.isEmpty => const _NewCompanyHint(),
      AsyncData(:final value) => Card(
          margin: EdgeInsets.zero,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final company in value)
                ListTile(
                  dense: true,
                  leading: const Icon(Icons.business_outlined),
                  title: Text(company.name),
                  onTap: () => onSelected(company),
                ),
            ],
          ),
        ),
    };
  }
}

class _NewCompanyHint extends StatelessWidget {
  const _NewCompanyHint();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        children: [
          Icon(
            Icons.add_circle_outline,
            size: 18,
            color: theme.colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              'Kayıtlı şirket bulunamadı. Devam edersen yazdığın adla oluşturulur.',
              style: theme.textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

class _SectorPicker extends StatelessWidget {
  const _SectorPicker({
    required this.sectors,
    required this.selectedId,
    required this.enabled,
    required this.onSelected,
  });

  final List<Sector> sectors;
  final int? selectedId;
  final bool enabled;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      children: [
        for (final sector in sectors)
          ChoiceChip(
            label: Text(sector.name),
            selected: selectedId == sector.id,
            onSelected: enabled ? (_) => onSelected(sector.id) : null,
          ),
      ],
    );
  }
}
