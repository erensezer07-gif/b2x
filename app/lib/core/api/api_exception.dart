import 'package:dio/dio.dart';

/// Kullanıcıya gösterilebilir hata.
///
/// Sunucu Türkçe mesaj döndürüyorsa o kullanılır; döndürmüyorsa (ağ kopması,
/// beklenmedik durum kodu) burada Türkçesi üretilir. Ekranlar `DioException`
/// görmemeli: teknik ayrıntı kullanıcıya bir şey anlatmıyor.
class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.statusCode,
    this.missingForApplication = const [],
  });

  final String message;
  final int? statusCode;

  /// Başvuruyu engelleyen eksik profil alanlarının İngilizce anahtarları.
  ///
  /// Yalnızca etkinliğe başvuru reddedildiğinde dolu gelir (M3). Türkçe cümle
  /// burada kurulmuyor: aynı anahtarların çevirisi profil ekranında zaten var
  /// (`ProfileRequirement`), iki yerde iki farklı metin olmasın.
  final List<String> missingForApplication;

  /// Oturum düştü mü — yönlendirmenin giriş ekranına dönmesi gerekiyor mu.
  bool get isUnauthorised => statusCode == 401;

  @override
  String toString() => 'ApiException($statusCode): $message';

  /// `DioException`'ı kullanıcıya gösterilebilir bir hataya çevirir.
  factory ApiException.from(DioException error) {
    final response = error.response;

    if (response == null) {
      return ApiException(_messageForTransport(error.type));
    }

    return ApiException(
      _detailOf(response.data) ?? _messageForStatus(response.statusCode),
      statusCode: response.statusCode,
      missingForApplication: _missingFieldsOf(response.data),
    );
  }

  /// Yapılandırılmış hatadaki eksik alan listesi.
  static List<String> _missingFieldsOf(dynamic data) {
    if (data is! Map) return const [];
    final detail = data['detail'];
    if (detail is! Map) return const [];
    final missing = detail['missing_for_application'];
    if (missing is! List) return const [];
    return missing.whereType<String>().toList();
  }

  static String _messageForTransport(DioExceptionType type) {
    switch (type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'Sunucu yanıt vermedi. Bağlantını kontrol edip tekrar dene.';
      case DioExceptionType.connectionError:
        return 'Sunucuya ulaşılamıyor. İnternet bağlantını kontrol et.';
      case DioExceptionType.cancel:
        return 'İstek iptal edildi.';
      default:
        return 'Beklenmeyen bir sorun oluştu.';
    }
  }

  static String _messageForStatus(int? statusCode) {
    if (statusCode == null) return 'Beklenmeyen bir sorun oluştu.';
    if (statusCode == 401) return 'Oturumun sona erdi. Tekrar giriş yap.';
    if (statusCode == 403) return 'Bu işlem için yetkin yok.';
    if (statusCode == 404) return 'Aradığın kayıt bulunamadı.';
    if (statusCode >= 500) return 'Sunucuda bir sorun oluştu. Az sonra tekrar dene.';
    return 'İstek işlenemedi.';
  }

  /// FastAPI'nin `detail` alanını okur.
  ///
  /// Üç biçim geliyor: elle atılan hatalarda düz metin, doğrulama hatalarında
  /// alan alan liste, bazı uçlarda yapılandırılmış nesne. Listede ilk mesaj
  /// gösteriliyor — kullanıcıya aynı anda beş hata basmak yardımcı olmuyor.
  static String? _detailOf(dynamic data) {
    if (data is! Map) return null;
    final detail = data['detail'];

    if (detail is String && detail.isNotEmpty) {
      return _frameworkDefaults.contains(detail) ? null : detail;
    }

    // Yapılandırılmış hata (örneğin eksik profil): insan okuyacak kısım
    // `message` alanında, geri kalanı arayüzün işleyeceği veri.
    if (detail is Map && detail['message'] is String) {
      return detail['message'] as String;
    }

    if (detail is List && detail.isNotEmpty) {
      final first = detail.first;
      if (first is Map && first['msg'] is String) {
        return _translateValidationMessage(first['msg'] as String);
      }
    }
    return null;
  }

  /// Sunucunun **bizim yazmadığımız** hata metinleri.
  ///
  /// Kendi yazdığımız her mesaj Türkçe. Bunlar FastAPI'nin varsayılanları:
  /// tanımadığı bir yola istek gelince `detail` alanına HTTP durumunun
  /// İngilizce adını koyuyor. Olduğu gibi gösterilirse Türkçe arayüzde
  /// "Not Found" yazan kırmızı bir kutu çıkıyor (Bölüm 0: arayüz Türkçe).
  /// Bu listeye düşen mesaj yok sayılıp durum koduna göre Türkçesi üretiliyor.
  static const _frameworkDefaults = {
    'Bad Request',
    'Unauthorized',
    'Forbidden',
    'Not Found',
    'Method Not Allowed',
    'Conflict',
    'Unprocessable Entity',
    'Unprocessable Content',
    'Too Many Requests',
    'Internal Server Error',
    'Service Unavailable',
  };

  /// Pydantic'in İngilizce doğrulama mesajlarını Türkçeleştirir.
  ///
  /// Sunucu bu metinleri üretiyor ve çevirmiyor; arayüz dili Türkçe olmak
  /// zorunda (şartname Bölüm 0). Tanımadığımız mesaj olduğu gibi geçmez,
  /// genel bir cümleye düşer — kullanıcı İngilizce bir uyarı görmemeli.
  static String _translateValidationMessage(String message) {
    if (message.contains('valid email')) {
      return 'Geçerli bir e-posta adresi gir.';
    }
    if (message.contains('at least') && message.contains('characters')) {
      return 'Şifre en az 8 karakter olmalı.';
    }
    return 'Girdiğin bilgilerde bir sorun var.';
  }
}
