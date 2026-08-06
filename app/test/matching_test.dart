// Eşleştirme ekranı — arayüz testleri (şartname M6, 5.4).
//
// Sunucu uyarıları İngilizce anahtar olarak gönderiyor, Türkçe cümle burada
// kuruluyor. Çevirinin kopması sessiz bir hata olurdu: kullanıcı "Beklenmeyen
// bir durum var" yazan bir liste görür.

import 'package:b2x/features/events/models.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> checkJson({
  List<String> warnings = const [],
  bool canRun = true,
  int incomplete = 0,
}) {
  return {
    'accepted_count': 24,
    'table_count': 6,
    'seating_capacity': 30,
    'request_count': 0,
    'incomplete_profile_count': incomplete,
    'slot_count': 5,
    'requests_open': true,
    'warnings': warnings,
    'can_run': canRun,
  };
}

Map<String, dynamic> planJson({
  String jobStatus = 'done',
  String? jobError,
  bool withSummary = true,
  String status = 'draft',
  List<String> unmatched = const [],
}) {
  return {
    'id': 3,
    'version': 2,
    'status': status,
    'job_status': jobStatus,
    'job_error': jobError,
    'created_at': '2026-08-06T14:30:00Z',
    'published_at': status == 'published' ? '2026-08-06T15:00:00Z' : null,
    'seed': 42,
    'total_meetings': withSummary ? 96 : null,
    'min_meetings_per_person': withSummary ? 4 : null,
    'average_table_score': withSummary ? 0.2122 : null,
    'runtime_ms': withSummary ? 3286 : null,
    'assignment_count': withSummary ? 96 : 0,
    'participant_count': withSummary ? 24 : 0,
    'unmatched': unmatched,
    'satisfied_requests': 0,
    'total_requests': 0,
  };
}

void main() {
  group('iş durumu', () {
    test('bekleyen durumlar yoklamayı sürdürüyor', () {
      expect(JobStatus.queued.isPending, isTrue);
      expect(JobStatus.running.isPending, isTrue);
      expect(JobStatus.done.isPending, isFalse);
      expect(JobStatus.failed.isPending, isFalse);
    });

    test('her durumun Türkçe bir etiketi var', () {
      for (final status in JobStatus.values) {
        expect(status.label, isNotEmpty);
      }
    });

    test('tanınmayan durum arayüzü çökertmiyor', () {
      expect(JobStatus.fromKey('gelecekte_eklenen'), JobStatus.queued);
    });
  });

  group('kontrol listesi', () {
    test('sunucu yanıtı eksiksiz okunuyor', () {
      final check = MatchingCheck.fromJson(checkJson());

      expect(check.acceptedCount, 24);
      expect(check.tableCount, 6);
      expect(check.seatingCapacity, 30);
      expect(check.slotCount, 5);
      expect(check.canRun, isTrue);
      expect(check.warnings, isEmpty);
    });

    test('uyarılar Türkçe cümleye çevriliyor', () {
      final check = MatchingCheck.fromJson(
        checkJson(
          warnings: [
            'capacity_below_participants',
            'requests_still_open',
            'incomplete_profiles',
          ],
          incomplete: 3,
        ),
      );

      final messages = check.warnings.map((w) => w.message).toList();
      expect(messages[0], contains('kapasitesi katılımcı sayısından az'));
      expect(messages[1], contains('Görüşme talepleri hâlâ açık'));
      expect(messages[2], contains('profili eksik'));
      // Hiçbiri İngilizce anahtar sızdırmamalı (Bölüm 0).
      for (final message in messages) {
        expect(message, isNot(contains('_')));
      }
    });

    test('her uyarının Türkçe bir cümlesi var', () {
      for (final warning in MatchingWarning.values) {
        expect(warning.message, isNotEmpty);
      }
    });

    test('tanınmayan uyarı arayüzü çökertmiyor', () {
      final check = MatchingCheck.fromJson(
        checkJson(warnings: ['gelecekte_eklenen_uyari']),
      );
      expect(check.warnings.single, MatchingWarning.unknown);
      expect(check.warnings.single.message, isNotEmpty);
    });

    test('uyarı çalıştırmayı engellemiyor', () {
      // M6: *"Sorun varsa organizatör uyarılır ama çalıştırma engellenmez."*
      final check = MatchingCheck.fromJson(
        checkJson(warnings: ['capacity_below_participants'], canRun: true),
      );
      expect(check.warnings, isNotEmpty);
      expect(check.canRun, isTrue);
    });
  });

  group('plan özeti', () {
    test('bitmiş plan özetiyle okunuyor', () {
      final plan = PlanSummary.fromJson(planJson());

      expect(plan.version, 2);
      expect(plan.jobStatus, JobStatus.done);
      expect(plan.hasResult, isTrue);
      expect(plan.isPending, isFalse);
      expect(plan.totalMeetings, 96);
      expect(plan.minMeetingsPerPerson, 4);
      expect(plan.participantCount, 24);
      // Hesap bitse de plan taslak kalıyor (5.2).
      expect(plan.status, PlanStatus.draft);
      expect(plan.isPublished, isFalse);
    });

    test('yayındaki plan yayın zamanını taşıyor', () {
      final plan = PlanSummary.fromJson(planJson(status: 'published'));

      expect(plan.status, PlanStatus.published);
      expect(plan.isPublished, isTrue);
      expect(plan.publishedAt, isNotNull);
    });

    test('hiç eşleşmeyenler isimle geliyor', () {
      // M7 *"varsa kimler"* diyor: sayı organizatöre bir şey vermez.
      final plan = PlanSummary.fromJson(
        planJson(unmatched: ['Ayşe Yılmaz', 'Mehmet Demir']),
      );

      expect(plan.unmatched, ['Ayşe Yılmaz', 'Mehmet Demir']);
    });

    test('kuyruktaki planın özeti henüz boş', () {
      // Plan satırı iş kuyruğa girer girmez oluşuyor; motor sonra çalışıyor.
      final plan = PlanSummary.fromJson(
        planJson(jobStatus: 'queued', withSummary: false),
      );

      expect(plan.isPending, isTrue);
      expect(plan.hasResult, isFalse);
      expect(plan.totalMeetings, isNull);
      expect(plan.averageTableScore, isNull);
      expect(plan.assignmentCount, 0);
    });

    test('hatalı plan sebebini taşıyor', () {
      final plan = PlanSummary.fromJson(
        planJson(jobStatus: 'failed', jobError: 'motor çöktü', withSummary: false),
      );

      expect(plan.jobStatus, JobStatus.failed);
      expect(plan.isPending, isFalse);
      expect(plan.hasResult, isFalse);
      expect(plan.jobError, 'motor çöktü');
    });

    test('ondalıklı skor tam sayı gelse de okunuyor', () {
      // JSON'da 0.0 yerine 0 gelebilir; `as double` bunu çökertirdi.
      final json = planJson();
      json['average_table_score'] = 0;
      expect(PlanSummary.fromJson(json).averageTableScore, 0.0);
    });
  });
}
