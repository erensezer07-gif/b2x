/// Uygulamanın dışarıdan aldığı yapılandırma.
///
/// Şartname Bölüm 0: sunucu adresi koda gömülmez. Adres derleme sırasında
/// verilir:
///
/// ```
/// flutter run   --dart-define=API_BASE_URL=http://<yerel-ag-adresi>:8000
/// flutter build --dart-define=API_BASE_URL=https://<sunucu-adresi>
/// ```
///
/// Varsayılan değer bilerek yoktur. Buraya bir adres yazılsaydı, tanım
/// unutulduğunda uygulama sessizce yanlış bir sunucuya giderdi. Boş kalırsa
/// durum kullanıcıya açıkça söylenir.
class AppConfig {
  const AppConfig._();

  /// Sunucunun kök adresi. Tanımlanmamışsa boş dizedir.
  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL');

  /// Sunucu adresi verilmiş mi.
  static bool get isConfigured => apiBaseUrl.isNotEmpty;
}
