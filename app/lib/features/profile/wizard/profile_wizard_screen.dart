import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/widgets/state_views.dart';
import '../models.dart';
import '../profile_controller.dart';
import '../profile_screen.dart';
import 'basics_step.dart';
import 'company_step.dart';
import 'photo_step.dart';
import 'tags_step.dart';

/// Profil sihirbazı (şartname M2).
///
/// *"Kayıttan sonra profil sihirbazı açılır. Adım adım ilerler, her adım
/// kaydedilir, kullanıcı yarıda bırakıp sonra devam edebilir."*
///
/// Sıra şartnamedeki sıra: temel bilgiler → şirket ve sektör → ne sunuyorum →
/// ne arıyorum → fotoğraf.
///
/// Adım durumu sunucuda tutuluyor, burada değil: her adım kendi verisini
/// kaydettiği için uygulama kapansa bile ilerleme kaybolmuyor.
class ProfileWizardScreen extends ConsumerStatefulWidget {
  const ProfileWizardScreen({super.key});

  static const routeName = 'profileWizard';
  static const routePath = '/profil/sihirbaz';

  @override
  ConsumerState<ProfileWizardScreen> createState() => _ProfileWizardScreenState();
}

class _ProfileWizardScreenState extends ConsumerState<ProfileWizardScreen> {
  static const _stepCount = 5;

  int _stepIndex = 0;
  bool _resumed = false;

  void _next() {
    if (_stepIndex + 1 >= _stepCount) {
      // Sihirbaz bitince ana kabuğa dönülür; kullanıcı profilini oradan da
      // görebilir, ama asıl işi etkinlikler sekmesinde.
      context.goNamed(ProfileScreen.routeName);
      return;
    }
    setState(() => _stepIndex++);
  }

  void _back() => setState(() => _stepIndex = (_stepIndex - 1).clamp(0, _stepCount - 1));

  /// Kullanıcının kaldığı adımı bulur.
  ///
  /// Yarıda bırakıp döndüğünde baştan başlamak yerine ilk eksik adıma
  /// gidiyoruz (M2). Tamamlanmış bir profilde son adımda açılıyor — oradan
  /// bitirip özete geçebilsin.
  int _firstIncompleteStep(Profile profile) {
    if ((profile.fullName ?? '').trim().isEmpty) return 0;
    if (profile.company == null || profile.sector == null) return 1;
    if (profile.offeredTags.length < TagsStep.minimumTags) return 2;
    if (profile.soughtTags.length < TagsStep.minimumTags) return 3;
    return 4;
  }

  @override
  Widget build(BuildContext context) {
    final profileState = ref.watch(profileControllerProvider);

    return switch (profileState) {
      AsyncLoading() => const Scaffold(
          body: LoadingView(message: 'Profilin yükleniyor'),
        ),
      AsyncError(:final error) => Scaffold(
          body: ErrorView(
            message: error is ApiException
                ? error.message
                : 'Profilin yüklenemedi.',
            onRetry: () => ref.invalidate(profileControllerProvider),
          ),
        ),
      AsyncData(:final value) => _buildStep(value),
    };
  }

  Widget _buildStep(Profile profile) {
    // Kaldığı yere yalnızca ilk açılışta atlanıyor; sonrasında kullanıcının
    // gezinmesi geçerli.
    if (!_resumed) {
      _resumed = true;
      _stepIndex = _firstIncompleteStep(profile);
    }

    return switch (_stepIndex) {
      0 => BasicsStep(
          key: const ValueKey('step-basics'),
          profile: profile,
          stepIndex: 0,
          stepCount: _stepCount,
          onCompleted: _next,
        ),
      1 => CompanyStep(
          key: const ValueKey('step-company'),
          profile: profile,
          stepIndex: 1,
          stepCount: _stepCount,
          onCompleted: _next,
          onBack: _back,
        ),
      2 => TagsStep(
          key: const ValueKey('step-offered'),
          profile: profile,
          direction: TagDirection.offered,
          stepIndex: 2,
          stepCount: _stepCount,
          onCompleted: _next,
          onBack: _back,
        ),
      3 => TagsStep(
          key: const ValueKey('step-sought'),
          profile: profile,
          direction: TagDirection.sought,
          stepIndex: 3,
          stepCount: _stepCount,
          onCompleted: _next,
          onBack: _back,
        ),
      _ => PhotoStep(
          key: const ValueKey('step-photo'),
          profile: profile,
          stepIndex: 4,
          stepCount: _stepCount,
          onCompleted: _next,
          onBack: _back,
        ),
    };
  }
}
