import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../models.dart';
import '../profile_controller.dart';
import 'wizard_step.dart';

/// Adım 5 — profil fotoğrafı (şartname M2).
///
/// Son adım ve **atlanabilir**: fotoğraf başvuru için zorunlu değil, yalnızca
/// tamamlanma yüzdesine giriyor. Masadaki kişiler birbirini tanısın diye
/// öneriliyor (M8).
class PhotoStep extends ConsumerStatefulWidget {
  const PhotoStep({
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

  /// Sunucudaki sınırla aynı; buradaki kontrol kullanıcıya anında geri bildirim
  /// vermek için, güvenlik sınırı değil.
  static const maxBytes = 5 * 1024 * 1024;

  @override
  ConsumerState<PhotoStep> createState() => _PhotoStepState();
}

class _PhotoStepState extends ConsumerState<PhotoStep> {
  bool _isBusy = false;
  String? _errorMessage;

  Future<void> _pickAndUpload() async {
    setState(() {
      _isBusy = true;
      _errorMessage = null;
    });

    try {
      final picked = await ImagePicker().pickImage(
        source: ImageSource.gallery,
        // Kaynakta küçültmek hem yükleme süresini hem de sunucudaki boyut
        // sınırına takılma ihtimalini azaltıyor.
        maxWidth: 1024,
        maxHeight: 1024,
        imageQuality: 85,
      );
      if (picked == null) return;

      final bytes = await picked.readAsBytes();
      if (bytes.length > PhotoStep.maxBytes) {
        setState(() => _errorMessage = 'Fotoğraf en fazla 5 MB olabilir.');
        return;
      }

      await ref.read(profileControllerProvider.notifier).uploadPhoto(
            bytes: bytes,
            filename: picked.name,
            contentType: _contentTypeOf(picked.name, picked.mimeType),
          );
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
  }

  Future<void> _remove() async {
    setState(() {
      _isBusy = true;
      _errorMessage = null;
    });

    try {
      await ref.read(profileControllerProvider.notifier).removePhoto();
    } on ApiException catch (error) {
      if (mounted) setState(() => _errorMessage = error.message);
    } finally {
      if (mounted) setState(() => _isBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // Yükleme sonrası güncel profil denetleyiciden geliyor; parametreyle gelen
    // kopya bayat kalabilir.
    final profile =
        ref.watch(profileControllerProvider).asData?.value ?? widget.profile;
    final hasPhoto = profile.photoUrl != null;

    return WizardStepScaffold(
      stepIndex: widget.stepIndex,
      stepCount: widget.stepCount,
      title: 'Profil fotoğrafın',
      description:
          'Masandaki kişiler seni tanısın. İstersen bu adımı atlayıp sonra '
          'ekleyebilirsin.',
      isSaving: _isBusy,
      errorMessage: _errorMessage,
      onBack: widget.onBack,
      onNext: widget.onCompleted,
      nextLabel: hasPhoto ? 'Bitir' : 'Fotoğrafsız bitir',
      child: Column(
        children: [
          _PhotoPreview(photoUrl: profile.photoUrl),
          const SizedBox(height: AppSpacing.lg),
          OutlinedButton.icon(
            onPressed: _isBusy ? null : _pickAndUpload,
            icon: const Icon(Icons.photo_library_outlined),
            label: Text(hasPhoto ? 'Fotoğrafı değiştir' : 'Fotoğraf seç'),
          ),
          if (hasPhoto)
            TextButton.icon(
              onPressed: _isBusy ? null : _remove,
              icon: const Icon(Icons.delete_outline),
              label: const Text('Fotoğrafı kaldır'),
            ),
        ],
      ),
    );
  }
}

class _PhotoPreview extends StatelessWidget {
  const _PhotoPreview({required this.photoUrl});

  final String? photoUrl;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return CircleAvatar(
      radius: 64,
      backgroundColor: colors.surfaceContainerHighest,
      foregroundImage: photoUrl == null ? null : NetworkImage(photoUrl!),
      // Görsel yüklenemezse (adres kırık, ağ yok) baş harf yerine simge kalır.
      onForegroundImageError: photoUrl == null ? null : (_, _) {},
      child: Icon(
        Icons.person_outline,
        size: 56,
        color: colors.onSurfaceVariant,
      ),
    );
  }
}

/// Dosyanın MIME türünü belirler.
///
/// `image_picker` web'de `mimeType` veriyor ama mobilde çoğu zaman boş
/// bırakıyor; o durumda uzantıdan çıkarılıyor. Sunucu yalnızca üç tür kabul
/// ediyor, bilinmeyen uzantı JPEG sayılıyor — reddi sunucu veriyor.
String _contentTypeOf(String filename, String? reported) {
  if (reported != null && reported.startsWith('image/')) return reported;

  final lower = filename.toLowerCase();
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.webp')) return 'image/webp';
  return 'image/jpeg';
}
