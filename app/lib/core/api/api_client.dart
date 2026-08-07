import 'package:dio/dio.dart';

import '../auth/token_storage.dart';
import 'api_exception.dart';

/// Sunucuyla konuşan tek yer.
///
/// ## Sessiz yenileme (şartname M1, Bölüm 10)
///
/// *"Süresi dolan jeton arka planda sessizce yenilenir, kullanıcı tekrar giriş
/// yapmak zorunda kalmaz."*
///
/// Bir istek 401 alırsa araya girici yenileme jetonuyla yeni bir erişim jetonu
/// alır ve **aynı isteği tekrarlar**. Kullanıcı hiçbir şey görmez. Yenileme de
/// başarısız olursa jetonlar silinir ve hata yüzeye çıkar; yönlendirme giriş
/// ekranına döner.
///
/// Eşzamanlı isteklerin hepsi aynı anda 401 alabilir. Yenileme **tek seferlik**
/// tutuluyor: ilk istek yenilemeyi başlatır, diğerleri aynı sonucu bekler.
/// Olmasaydı her istek ayrı bir yenileme tetikler ve sunucuya gereksiz yük
/// binerdi.
class ApiClient {
  ApiClient({
    required String baseUrl,
    required TokenStorage tokenStorage,
    void Function()? onSessionLost,
  })  : _tokenStorage = tokenStorage,
        _onSessionLost = onSessionLost,
        _dio = Dio(_optionsFor(baseUrl)),
        _refreshDio = Dio(_optionsFor(baseUrl)) {
    _dio.interceptors.add(
      InterceptorsWrapper(onRequest: _attachToken, onError: _recoverFromExpiry),
    );
  }

  final TokenStorage _tokenStorage;

  /// Sessiz yenileme de tutmadığında çağrılır — oturum gerçekten bitti.
  final void Function()? _onSessionLost;
  final Dio _dio;

  /// Yenileme isteği kendi istemcisiyle gidiyor: araya girici ona da takılsaydı
  /// yenileme başarısız olduğunda sonsuz döngü oluşurdu.
  final Dio _refreshDio;

  Future<bool>? _refreshInFlight;

  static const _retriedKey = 'b2x_retried';

  /// Yenileme denemesi bu uçlarda yapılmaz: 401 zaten "kimlik doğru değil"
  /// demek, tazelemek bir şeyi düzeltmez.
  static const _tokenlessPaths = {'/auth/login', '/auth/register', '/auth/refresh'};

  static BaseOptions _optionsFor(String baseUrl) => BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 20),
        contentType: Headers.jsonContentType,
        // Durum kodunu biz yorumluyoruz; dio'nun kendi eşiği yeterli.
        validateStatus: (status) => status != null && status < 400,
      );

  Future<void> _attachToken(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (!_tokenlessPaths.contains(options.path)) {
      final token = await _tokenStorage.readAccessToken();
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }

  Future<void> _recoverFromExpiry(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final options = error.requestOptions;
    final isExpired = error.response?.statusCode == 401;
    final alreadyRetried = options.extra[_retriedKey] == true;

    if (!isExpired || alreadyRetried || _tokenlessPaths.contains(options.path)) {
      return handler.next(error);
    }

    final refreshed = await _refreshSession();
    if (!refreshed) {
      await _tokenStorage.clear();
      // Jeton silindi ama uygulama hâlâ oturumu açık sanıyor. Haber
      // verilmezse kullanıcı her ekranda hata görür ve çıkışı elle bulmadan
      // hiçbir şey yapamaz — yenileme jetonunun ömrü dolduğunda olan tam
      // olarak bu.
      _onSessionLost?.call();
      return handler.next(error);
    }

    options.extra[_retriedKey] = true;
    final token = await _tokenStorage.readAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }

    // `FormData` bir akıştır ve ilk gönderimde tüketilir; olduğu gibi tekrar
    // gönderilirse sunucuya boş gövde gider. Klonlamak dosya yüklemesinin de
    // sessiz yenilemeden faydalanmasını sağlıyor.
    if (options.data is FormData) {
      options.data = (options.data as FormData).clone();
    }

    try {
      handler.resolve(await _dio.fetch(options));
    } on DioException catch (retryFailure) {
      handler.next(retryFailure);
    }
  }

  /// Yenilemeyi tek seferlik yapar; eşzamanlı çağrılar aynı sonucu bekler.
  Future<bool> _refreshSession() {
    return _refreshInFlight ??= _performRefresh().whenComplete(() {
      _refreshInFlight = null;
    });
  }

  Future<bool> _performRefresh() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    if (refreshToken == null) return false;

    try {
      final response = await _refreshDio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );
      final data = response.data;
      if (data == null) return false;

      await _tokenStorage.save(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String,
      );
      return true;
    } on DioException {
      return false;
    }
  }

  // --- İstekler ---------------------------------------------------------

  Future<Map<String, dynamic>> getObject(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    return _guard(() async {
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: query,
      );
      return response.data ?? <String, dynamic>{};
    });
  }

  Future<List<dynamic>> getList(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    return _guard(() async {
      final response = await _dio.get<List<dynamic>>(path, queryParameters: query);
      return response.data ?? <dynamic>[];
    });
  }

  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    return _guard(() async {
      final response = await _dio.post<Map<String, dynamic>>(path, data: body);
      return response.data ?? <String, dynamic>{};
    });
  }

  Future<Map<String, dynamic>> patch(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    return _guard(() async {
      final response = await _dio.patch<Map<String, dynamic>>(path, data: body);
      return response.data ?? <String, dynamic>{};
    });
  }

  Future<Map<String, dynamic>> put(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    return _guard(() async {
      final response = await _dio.put<Map<String, dynamic>>(path, data: body);
      return response.data ?? <String, dynamic>{};
    });
  }

  Future<Map<String, dynamic>> delete(String path) async {
    return _guard(() async {
      final response = await _dio.delete<Map<String, dynamic>>(path);
      return response.data ?? <String, dynamic>{};
    });
  }

  /// Çok parçalı form gönderir — dosya yükleme için.
  Future<Map<String, dynamic>> postForm(String path, FormData form) async {
    return _guard(() async {
      final response = await _dio.post<Map<String, dynamic>>(path, data: form);
      return response.data ?? <String, dynamic>{};
    });
  }

  /// Ağ katmanının hatalarını ekranların anlayacağı türe çevirir.
  Future<T> _guard<T>(Future<T> Function() request) async {
    try {
      return await request();
    } on DioException catch (error) {
      throw ApiException.from(error);
    }
  }
}
