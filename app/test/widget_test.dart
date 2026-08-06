// B2X — arayüz testleri.
//
// Testler `--dart-define=API_BASE_URL` olmadan çalışır, dolayısıyla uygulama
// yapılandırma eksik ekranını gösterir. Bu da bir davranış: sunucu adresi
// verilmediğinde kullanıcı boş bir ekranla karşılaşmamalı.

import 'package:b2x/core/widgets/state_views.dart';
import 'package:b2x/features/auth/password_strength.dart';
import 'package:b2x/features/profile/models.dart';
import 'package:b2x/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('uygulama açılışı', () {
    testWidgets('sunucu adresi verilmemişse kullanıcı uyarılır', (tester) async {
      await tester.pumpWidget(const ProviderScope(child: B2xApp()));
      await tester.pumpAndSettle();

      expect(find.textContaining('Sunucu adresi tanımlı değil'), findsOneWidget);
      expect(find.textContaining('API_BASE_URL'), findsOneWidget);
    });
  });

  group('şifre gücü', () {
    test('sekiz karakterin altı kabul edilmez', () {
      expect(PasswordStrength.of('kisa').isAcceptable, isFalse);
      expect(PasswordStrength.of('1234567').isAcceptable, isFalse);
      expect(PasswordStrength.of('12345678').isAcceptable, isTrue);
    });

    test('çeşitlilik arttıkça güç artar', () {
      final onlyLetters = PasswordStrength.of('abcdefgh');
      final mixed = PasswordStrength.of('abcdEfg1');
      final long = PasswordStrength.of('abcdEfg1!xyz');

      expect(onlyLetters, PasswordStrength.weak);
      expect(mixed, PasswordStrength.fair);
      expect(long, PasswordStrength.strong);
    });

    test('Türkçe büyük harfler çeşitlilik sayılır', () {
      // "Ğ" ASCII aralığında değil; düzenli ifade onu büyük harf saymazsa
      // Türkçe şifreler haksız yere zayıf görünürdü.
      expect(PasswordStrength.of('ğüşiöçab'), PasswordStrength.weak);
      expect(PasswordStrength.of('ĞÜŞİÖÇab'), PasswordStrength.fair);
    });

    test('her seviyenin Türkçe bir etiketi var', () {
      for (final strength in PasswordStrength.values) {
        expect(strength.label, isNotEmpty);
      }
    });
  });

  group('üç durum bileşenleri', () {
    Widget wrap(Widget child) => MaterialApp(home: Scaffold(body: child));

    testWidgets('yükleniyor göstergesi çizilir', (tester) async {
      await tester.pumpWidget(wrap(const LoadingView(message: 'Yükleniyor')));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Yükleniyor'), findsOneWidget);
    });

    testWidgets('hata durumunda tekrar deneme yolu sunulur', (tester) async {
      var retried = false;
      await tester.pumpWidget(
        wrap(ErrorView(message: 'Bir şeyler ters gitti', onRetry: () => retried = true)),
      );

      expect(find.text('Bir şeyler ters gitti'), findsOneWidget);
      await tester.tap(find.text('Tekrar dene'));
      expect(retried, isTrue);
    });

    testWidgets('tekrar deneme yoksa düğme de yok', (tester) async {
      await tester.pumpWidget(wrap(const ErrorView(message: 'Hata')));
      expect(find.text('Tekrar dene'), findsNothing);
    });

    testWidgets('boş durum mesajı gösterilir', (tester) async {
      await tester.pumpWidget(wrap(const EmptyView(message: 'Henüz etkinlik yok')));
      expect(find.text('Henüz etkinlik yok'), findsOneWidget);
    });
  });

  group('profil modeli', () {
    Map<String, dynamic> profileJson({
      List<String> missing = const [],
      bool canApply = true,
    }) =>
        {
          'full_name': 'Ayşe Yılmaz',
          'title': 'Kurucu',
          'city': 'İzmir',
          'bio': null,
          'photo_url': null,
          'website': null,
          'linkedin_url': null,
          'company': {'id': 1, 'name': 'ABC Yazılım'},
          'sector': {'id': 2, 'name': 'Bilişim ve yazılım'},
          'offered_tags': [
            {'id': 10, 'name': 'Web yazılımı geliştirme'},
          ],
          'sought_tags': [
            {'id': 20, 'name': 'Melek yatırım'},
          ],
          'completion_percent': 67,
          'missing_for_application': missing,
          'can_apply': canApply,
        };

    test('sunucu yanıtı eksiksiz okunur', () {
      final profile = Profile.fromJson(profileJson());

      expect(profile.fullName, 'Ayşe Yılmaz');
      expect(profile.company?.name, 'ABC Yazılım');
      expect(profile.sector?.name, 'Bilişim ve yazılım');
      expect(profile.offeredTags.single.name, 'Web yazılımı geliştirme');
      expect(profile.soughtTags.single.name, 'Melek yatırım');
      expect(profile.completionPercent, 67);
      expect(profile.canApply, isTrue);
    });

    test('eksik alan anahtarları Türkçe etikete çevrilir', () {
      final profile = Profile.fromJson(
        profileJson(missing: ['full_name', 'offered_tags'], canApply: false),
      );

      expect(profile.canApply, isFalse);
      expect(
        profile.missingForApplication,
        [ProfileRequirement.fullName, ProfileRequirement.offeredTags],
      );
      // Kullanıcıya İngilizce anahtar gösterilmemeli (Bölüm 0).
      for (final requirement in profile.missingForApplication) {
        expect(requirement.label, isNot(contains('_')));
      }
    });

    test('bilinmeyen anahtar arayüzü çökertmez', () {
      // Sunucu ileride yeni bir zorunluluk eklerse eski istemci ayakta kalmalı.
      final profile = Profile.fromJson(
        profileJson(missing: ['gelecekte_eklenen_alan'], canApply: false),
      );

      expect(profile.missingForApplication, [ProfileRequirement.unknown]);
      expect(profile.missingForApplication.single.label, isNotEmpty);
    });

    test('her zorunluluğun Türkçe bir etiketi var', () {
      for (final requirement in ProfileRequirement.values) {
        expect(requirement.label, isNotEmpty);
      }
    });
  });
}
