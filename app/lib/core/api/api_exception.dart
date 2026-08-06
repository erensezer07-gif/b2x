import 'package:dio/dio.dart';

/// Kullanıcıya gösterilebilir hata.
///
/// Sunucu Türkçe mesaj döndürüyorsa o kullanılır; döndürmüyorsa (ağ kopması,
/// beklenmedik durum kodu) burada Türkçesi üretilir. Ekranlar `DioException`
/// görmemeli: teknik ayrıntı kullanıcıya bir şey anlatmıyor.
class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

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

    final detail = _detailOf(response.data);
    if (detail != null) {
      return ApiException(detail, statusCode: response.statusCode);
    }

    return ApiException(
      _messageForStatus(response.statusCode),
      statusCode: response.statusCode,
    );
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
  /// İki biçim geliyor: elle atılan hatalarda düz metin, doğrulama hatalarında
  /// alan alan liste. İkincisinde ilk mesaj gösteriliyor — kullanıcıya aynı anda
  /// beş hata basmak yardımcı olmuyor.
  static String? _detailOf(dynamic data) {
    if (data is! Map) return null;
    final detail = data['detail'];

    if (detail is String && detail.isNotEmpty) return detail;

    if (detail is List && detail.isNotEmpty) {
      final first = detail.first;
      if (first is Map && first['msg'] is String) {
        return _translateValidationMessage(first['msg'] as String);
      }
    }
    return null;
  }

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
