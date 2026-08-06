import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../core/api/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/widgets/state_views.dart';
import 'event_controller.dart';
import 'models.dart';
import 'public_event_screen.dart';
import 'schedule.dart';

/// Katılımcının giriş kodu (şartname M10).
///
/// *"Her kabul edilmiş katılımcı için benzersiz bir kod üretilir. Katılımcı
/// bunu uygulamada QR olarak görür. İnternet olmasa bile görüntülenebilmeli —
/// ekran görüntüsü alınabilir olmalı."*
///
/// Bu yüzden QR **istemcide çiziliyor**: sunucudan görsel çekmek internet
/// gerektirirdi. Kod metin olarak da yazılıyor — kamera okumazsa organizatör
/// elle girebilsin.
class QrScreen extends ConsumerWidget {
  const QrScreen({super.key, required this.eventId});

  static const routeName = 'myQr';
  static const routePath = '/kesfet/:eventId/giris-kodum';

  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final code = ref.watch(myQrProvider(eventId));

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
        title: const Text('Giriş kodum'),
      ),
      body: switch (code) {
        AsyncError(:final error) => ErrorView(
            message: error is ApiException ? error.message : 'Kod yüklenemedi.',
            onRetry: () => ref.invalidate(myQrProvider(eventId)),
          ),
        AsyncData(:final value) => _Code(code: value),
        _ => const LoadingView(message: 'Kodun hazırlanıyor'),
      },
    );
  }
}

class _Code extends StatelessWidget {
  const _Code({required this.code});

  final MyQrCode code;

  /// QR'ın kenarı.
  ///
  /// Büyük tutuluyor: kapıda telefon uzaktan okutuluyor ve ekran parlaklığı
  /// düşük olabilir.
  static const _size = 260.0;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        if (code.checkedIn) ...[
          Card(
            margin: EdgeInsets.zero,
            color: colors.primaryContainer,
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Row(
                children: [
                  Icon(Icons.check_circle, color: colors.onPrimaryContainer),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text(
                      'Girişin yapıldı · ${formatTime(code.checkedInAt!)}',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colors.onPrimaryContainer,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
        ],
        Center(
          child: Container(
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: BoxDecoration(
              // QR okuyucular koyu zeminde zorlanıyor; kod her temada beyaz
              // zemin üzerinde çiziliyor.
              color: Colors.white,
              borderRadius: BorderRadius.circular(AppSpacing.sm),
            ),
            child: QrImageView(
              data: code.qrCode,
              size: _size,
              backgroundColor: Colors.white,
              // Ekran görüntüsü sıkıştırıldığında bile okunabilsin.
              errorCorrectionLevel: QrErrorCorrectLevel.M,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        Text(
          'Girişte bu kodu okut.',
          textAlign: TextAlign.center,
          style: theme.textTheme.bodyMedium,
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Ekran görüntüsü alabilirsin; kod internet olmadan da görünür.',
          textAlign: TextAlign.center,
          style: theme.textTheme.bodySmall?.copyWith(color: colors.onSurfaceVariant),
        ),
        const SizedBox(height: AppSpacing.lg),
        // Kamera okumazsa organizatör kodu elle girebilsin.
        SelectableText(
          code.qrCode,
          textAlign: TextAlign.center,
          style: theme.textTheme.bodySmall?.copyWith(
            color: colors.onSurfaceVariant,
            fontFamily: 'monospace',
          ),
        ),
      ],
    );
  }
}
