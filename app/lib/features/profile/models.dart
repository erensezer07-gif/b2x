/// Profil ve taksonomi modelleri (şartname M2, Bölüm 6).
///
/// Sunucudan gelen JSON'un Dart karşılığı. Alan adları İngilizce (Bölüm 0);
/// kullanıcıya gösterilecek Türkçe metinler ekranlarda kurulur.
library;

class Company {
  const Company({required this.id, required this.name});

  factory Company.fromJson(Map<String, dynamic> json) =>
      Company(id: json['id'] as int, name: json['name'] as String);

  final int id;
  final String name;
}

class Sector {
  const Sector({required this.id, required this.name});

  factory Sector.fromJson(Map<String, dynamic> json) =>
      Sector(id: json['id'] as int, name: json['name'] as String);

  final int id;
  final String name;
}

class Tag {
  const Tag({required this.id, required this.name});

  factory Tag.fromJson(Map<String, dynamic> json) =>
      Tag(id: json['id'] as int, name: json['name'] as String);

  final int id;
  final String name;
}

/// Etiket kategorisi ve altındaki etiketler.
///
/// "Ne sunuyorum" ve "ne arıyorum" **aynı havuzdan** seçilir (Bölüm 6): iki ayrı
/// liste olsaydı sinerji hesabı karşılaştırma yapamazdı.
class TagCategory {
  const TagCategory({required this.id, required this.name, required this.tags});

  factory TagCategory.fromJson(Map<String, dynamic> json) => TagCategory(
        id: json['id'] as int,
        name: json['name'] as String,
        tags: (json['tags'] as List<dynamic>)
            .map((item) => Tag.fromJson(item as Map<String, dynamic>))
            .toList(),
      );

  final int id;
  final String name;
  final List<Tag> tags;
}

/// Başvuruyu engelleyen eksik alanlar.
///
/// Sunucu İngilizce anahtar döndürüyor (`full_name`, `company`, ...); Türkçe
/// cümleyi burası kuruyor. Şartname M2: *"Eksikse başvuru butonu çalışmaz ve
/// neyin eksik olduğu yazılır."*
enum ProfileRequirement {
  fullName('full_name', 'Ad soyad'),
  company('company', 'Şirket'),
  sector('sector', 'Sektör'),
  offeredTags('offered_tags', 'En az üç "sunuyorum" etiketi'),
  soughtTags('sought_tags', 'En az üç "arıyorum" etiketi'),
  unknown('', 'Eksik bilgi');

  const ProfileRequirement(this.key, this.label);

  final String key;
  final String label;

  static ProfileRequirement fromKey(String key) {
    return ProfileRequirement.values.firstWhere(
      (item) => item.key == key,
      // Sunucu ileride yeni bir anahtar eklerse arayüz çökmemeli.
      orElse: () => ProfileRequirement.unknown,
    );
  }
}

/// Kullanıcının kendi profili.
class Profile {
  const Profile({
    this.fullName,
    this.title,
    this.city,
    this.bio,
    this.photoUrl,
    this.website,
    this.linkedinUrl,
    this.company,
    this.sector,
    this.offeredTags = const [],
    this.soughtTags = const [],
    this.completionPercent = 0,
    this.missingForApplication = const [],
    this.canApply = false,
  });

  factory Profile.fromJson(Map<String, dynamic> json) {
    List<Tag> tags(String key) => (json[key] as List<dynamic>)
        .map((item) => Tag.fromJson(item as Map<String, dynamic>))
        .toList();

    return Profile(
      fullName: json['full_name'] as String?,
      title: json['title'] as String?,
      city: json['city'] as String?,
      bio: json['bio'] as String?,
      photoUrl: json['photo_url'] as String?,
      website: json['website'] as String?,
      linkedinUrl: json['linkedin_url'] as String?,
      company: json['company'] == null
          ? null
          : Company.fromJson(json['company'] as Map<String, dynamic>),
      sector: json['sector'] == null
          ? null
          : Sector.fromJson(json['sector'] as Map<String, dynamic>),
      offeredTags: tags('offered_tags'),
      soughtTags: tags('sought_tags'),
      completionPercent: json['completion_percent'] as int,
      missingForApplication: (json['missing_for_application'] as List<dynamic>)
          .map((item) => ProfileRequirement.fromKey(item as String))
          .toList(),
      canApply: json['can_apply'] as bool,
    );
  }

  final String? fullName;
  final String? title;
  final String? city;
  final String? bio;
  final String? photoUrl;
  final String? website;
  final String? linkedinUrl;
  final Company? company;
  final Sector? sector;
  final List<Tag> offeredTags;
  final List<Tag> soughtTags;

  /// Tamamlanma yüzdesi — yalnızca bilgilendirir, hiçbir şeyi engellemez (M2).
  final int completionPercent;

  /// Başvuruyu engelleyen eksikler. Boşsa [canApply] doğru olur.
  final List<ProfileRequirement> missingForApplication;
  final bool canApply;
}
