// Etkinlik keşfi ve başvuru — arayüz testleri (şartname M3, Bölüm 10).
//
// Kabul kriteri: *"Eksik profille etkinliğe başvurulamıyor ve eksiğin ne olduğu
// yazıyor."* Sunucu eksikleri İngilizce anahtar olarak gönderiyor; Türkçe cümle
// burada kuruluyor. Bu çevirinin kopması sessiz bir hata olurdu — kullanıcı
// "Eksik bilgi" yazan bir liste görür.

import 'package:b2x/core/api/api_exception.dart';
import 'package:b2x/features/events/models.dart';
import 'package:b2x/features/events/schedule.dart';
import 'package:b2x/features/profile/models.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

/// Sunucudan gelmiş gibi bir hata yanıtı üretir.
ApiException failureWith(dynamic body, {int status = 400}) {
  return ApiException.from(
    DioException(
      requestOptions: RequestOptions(path: '/events/1/registration'),
      response: Response<dynamic>(
        requestOptions: RequestOptions(path: '/events/1/registration'),
        statusCode: status,
        data: body,
      ),
    ),
  );
}

Map<String, dynamic> discoverJson({
  int remaining = 5,
  bool isOpen = true,
  Map<String, dynamic>? mine,
  String? deadline,
}) {
  return {
    'id': 1,
    'name': 'İhracat Forumu',
    'cover_url': null,
    'starts_at': '2026-11-12T09:00:00Z',
    'venue_name': 'Fuar Merkezi',
    'slot_count': 6,
    'capacity': 10,
    'remaining_capacity': remaining,
    'registration_deadline': deadline,
    'is_open': isOpen,
    'my_registration': mine,
  };
}

void main() {
  group('başvuru hatası', () {
    test('eksik profil alanları hatadan okunabiliyor', () {
      final error = failureWith(
        {
          'detail': {
            'message': 'Profilin başvuru için yeterli değil.',
            'missing_for_application': ['full_name', 'company', 'offered_tags'],
          },
        },
        status: 422,
      );

      expect(error.message, 'Profilin başvuru için yeterli değil.');
      expect(error.missingForApplication, ['full_name', 'company', 'offered_tags']);
    });

    test('eksikler Türkçe etikete çevriliyor', () {
      // Kabul kriterinin görünen yüzü: kullanıcı neyin eksik olduğunu okumalı.
      final labels = ['full_name', 'company', 'sector', 'offered_tags', 'sought_tags']
          .map((key) => ProfileRequirement.fromKey(key).label)
          .toList();

      expect(labels, [
        'Ad soyad',
        'Şirket',
        'Sektör',
        'En az üç "sunuyorum" etiketi',
        'En az üç "arıyorum" etiketi',
      ]);
    });

    test('tanınmayan anahtar arayüzü çökertmiyor', () {
      final error = failureWith(
        {
          'detail': {
            'message': 'Eksik.',
            'missing_for_application': ['gelecekte_eklenen_alan'],
          },
        },
        status: 422,
      );

      final requirement = ProfileRequirement.fromKey(error.missingForApplication.single);
      expect(requirement, ProfileRequirement.unknown);
      expect(requirement.label, 'Eksik bilgi');
    });

    test('sunucunun Türkçe mesajı olduğu gibi geçiyor', () {
      final error = failureWith({'detail': 'Kontenjan doldu.'}, status: 409);
      expect(error.message, 'Kontenjan doldu.');
      expect(error.missingForApplication, isEmpty);
    });

    test('FastAPI varsayılanı Türkçesine düşüyor', () {
      // Arayüz Türkçe (Bölüm 0). Tanınmayan bir yola istek gidince FastAPI
      // `detail` alanına "Not Found" koyuyor; kullanıcı bunu görmemeli.
      final error = failureWith({'detail': 'Not Found'}, status: 404);
      expect(error.message, 'Aradığın kayıt bulunamadı.');
    });

    test('bağlantı kopmasının Türkçesi var', () {
      final error = ApiException.from(
        DioException(
          requestOptions: RequestOptions(path: '/events/discover'),
          type: DioExceptionType.connectionError,
        ),
      );
      expect(error.message, contains('Sunucuya ulaşılamıyor'));
    });
  });

  group('keşif kartı', () {
    test('sunucu yanıtı eksiksiz okunuyor', () {
      final card = DiscoverEvent.fromJson(
        discoverJson(mine: {
          'id': 4,
          'status': 'accepted',
          'applied_at': '2026-08-01T10:00:00Z',
        }),
      );

      expect(card.name, 'İhracat Forumu');
      expect(card.venueName, 'Fuar Merkezi');
      expect(card.remainingCapacity, 5);
      expect(card.myRegistration!.status, RegistrationStatus.accepted);
      expect(card.myRegistration!.status.label, 'Kabul edildi');
    });

    test('başvurmamış kullanıcının kaydı boş', () {
      final card = DiscoverEvent.fromJson(discoverJson());
      expect(card.myRegistration, isNull);
      expect(card.closedReason, isNull);
    });

    test('kontenjan dolunca sebep yazılıyor', () {
      // Kapalı etkinlik listeden düşmüyor; kart nedenini söylüyor (M3).
      final card = DiscoverEvent.fromJson(discoverJson(remaining: 0, isOpen: false));
      expect(card.isFull, isTrue);
      expect(card.closedReason, 'Kontenjan doldu');
    });

    test('son tarih geçince sebep yazılıyor', () {
      final card = DiscoverEvent.fromJson(
        discoverJson(remaining: 3, isOpen: false, deadline: '2020-01-01T00:00:00Z'),
      );
      expect(card.closedReason, 'Son başvuru tarihi geçti');
    });

    test('başvurmuş kullanıcıya kapalılık sebebi gösterilmiyor', () {
      // Rozet zaten "Kabul edildi" diyor; üstüne "kontenjan doldu" yazmak
      // kullanıcıyı yerinden şüpheye düşürürdü.
      final card = DiscoverEvent.fromJson(
        discoverJson(
          remaining: 0,
          isOpen: false,
          mine: {'id': 4, 'status': 'accepted', 'applied_at': '2026-08-01T10:00:00Z'},
        ),
      );
      expect(card.closedReason, isNull);
    });
  });

  group('etkinlik detayı', () {
    test('program ve katılımcı sayısı okunuyor', () {
      final event = PublicEvent.fromJson({
        'id': 1,
        'name': 'İhracat Forumu',
        'description': 'Açıklama',
        'cover_url': null,
        'starts_at': '2026-11-12T09:00:00Z',
        'venue_name': 'Fuar Merkezi',
        'address': 'Yenikapı',
        'slot_duration_minutes': 30,
        'break_duration_minutes': 10,
        'slot_count': 2,
        'schedule': [
          {
            'number': 1,
            'starts_at': '2026-11-12T09:00:00Z',
            'ends_at': '2026-11-12T09:30:00Z',
          },
          {
            'number': 2,
            'starts_at': '2026-11-12T09:40:00Z',
            'ends_at': '2026-11-12T10:10:00Z',
          },
        ],
        'ends_at': '2026-11-12T10:10:00Z',
        'total_minutes': 70,
        'capacity': 10,
        'remaining_capacity': 7,
        'accepted_count': 3,
        'registration_deadline': null,
        'is_open': true,
        'my_registration': null,
      });

      expect(event.schedule.length, 2);
      expect(event.acceptedCount, 3);
      expect(event.totalMinutes, 70);
      expect(event.myRegistration, isNull);
    });
  });

  group('başvuru listesi', () {
    Map<String, dynamic> summaryJson({int accepted = 0, int remaining = 10}) => {
          'registrations': [
            {
              'id': 9,
              'status': 'pending',
              'applied_at': '2026-08-01T10:00:00Z',
              'applicant': {
                'full_name': 'Ayşe Yılmaz',
                'title': 'Kurucu',
                'photo_url': null,
                'company': {'id': 2, 'name': 'Yılmaz Yazılım'},
                'sector': {'id': 1, 'name': 'Bilişim ve yazılım'},
              },
            },
          ],
          'pending_count': 1,
          'accepted_count': accepted,
          'rejected_count': 0,
          'capacity': 10,
          'remaining_capacity': remaining,
        };

    test('başvuran profiliyle birlikte okunuyor', () {
      final summary = RegistrationSummary.fromJson(summaryJson());
      final row = summary.registrations.single;

      expect(row.status, RegistrationStatus.pending);
      expect(row.applicant.displayName, 'Ayşe Yılmaz');
      expect(row.applicant.subtitle, 'Kurucu · Yılmaz Yazılım');
      expect(row.applicant.sector!.name, 'Bilişim ve yazılım');
    });

    test('adı girilmemiş başvuran boş satır göstermiyor', () {
      final json = summaryJson();
      (json['registrations'] as List).first['applicant'] = {
        'full_name': null,
        'title': null,
        'photo_url': null,
        'company': null,
        'sector': null,
      };

      final applicant = RegistrationSummary.fromJson(json).registrations.single.applicant;
      expect(applicant.displayName, 'Adı girilmemiş');
      expect(applicant.subtitle, isEmpty);
    });

    test('kontenjan dolduğunda işaretleniyor', () {
      expect(RegistrationSummary.fromJson(summaryJson()).isFull, isFalse);
      expect(
        RegistrationSummary.fromJson(summaryJson(accepted: 10, remaining: 0)).isFull,
        isTrue,
      );
    });
  });

  group('tarih biçimi', () {
    test('ay adı yazılıyor', () {
      // `12.11.2026` ile `11.12.2026` bir bakışta karışıyor; etkinlik kartında
      // bu pahalı bir hata.
      expect(formatDate(DateTime(2026, 11, 12)), '12 Kasım 2026');
      expect(formatDate(DateTime(2026, 1, 1)), '1 Ocak 2026');
      expect(formatDate(DateTime(2026, 12, 31)), '31 Aralık 2026');
    });
  });
}
