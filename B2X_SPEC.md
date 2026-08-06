# B2X — Teknik Şartname

B2B etkinlik eşleştirme ve oturma planlama platformu.

Bu dosya projenin tek referans kaynağıdır. Kod yazmaya başlamadan önce ilgili bölüm okunur. Bir davranış burada tarif edilmemişse uydurulmaz, önce bu dosyaya eklenir.

---

## 0. Claude Code için çalışma kuralları

Bu bölüm diğer her şeyden önce gelir.

**Önce plan, sonra kod.** Bir modüle başlarken önce ne yapılacağı yazılır, onay alınır, sonra kod yazılır. Büyük dosyalar tek seferde üretilmez.

**Şartnamenin dışına çıkma.** Burada tarif edilmeyen bir özellik kendiliğinden eklenmez. "Bunu da eklesek iyi olur" diye düşünülen şeyler önce konuşulur.

**Motor sınırı kutsaldır.** `backend/engine/` klasörü FastAPI'yi, SQLAlchemy'yi, veritabanını, HTTP'yi bilmez. Sadece standart kütüphane ve NumPy kullanır. Bu klasördeki hiçbir dosya `from fastapi import ...` veya `from sqlalchemy import ...` içeremez. Bu kural delinirse projenin en değerli parçası test edilemez hale gelir.

**Hiçbir yere sabit değer gömme.** Sunucu adresi, veritabanı bilgisi, gizli anahtarlar, port numaraları — hepsi ortam değişkeninden okunur. Kodda `localhost` geçmez. Sebep: proje tamamlandığında başka bir makineye taşınacak, tek satır kod değişmeden çalışması gerekiyor.

**Her ekranda üç durum vardır.** Yükleniyor, hata, boş. Bunlar sonradan eklenmez, ekranla birlikte yazılır.

**Motor değişikliği testsiz kabul edilmez.** `backend/engine/` altında yapılan her değişiklikten sonra motor testleri çalıştırılır ve geçtiği görülür.

**Türkçe arayüz, İngilizce kod.** Kullanıcının gördüğü her metin Türkçe. Değişken, fonksiyon, tablo, sütun adları İngilizce.

### Terim kullanımı

Bu dosyada iki ayrı numaralandırma var, karıştırılmamalı:

- **Aşama** — projenin yapım sırası. Bölüm 11'de tanımlı, 0'dan 12'ye.
- **Adım** — eşleştirme algoritmasının içindeki işlem sırası. Bölüm 9.7'de tanımlı, 1'den 6'ya.

"Aşama 2" projenin motor yazma aşamasıdır. "Adım 2" algoritmanın sabit atama yerleştirme adımıdır.

---

## 1. Proje ne yapıyor

Bir kurumsal etkinlikte (zirve, fuar, iş forumu) katılımcıların birbiriyle tanışması genelde tesadüfe kalır. B2X bunu planlı hale getirir.

Organizatör etkinliği oluşturur, salon düzenini kurar, kayıtları açar. Katılımcılar profil doldurur ve başvurur. Kayıtlar kapanınca sistem, herkesin profilini karşılaştırıp **hangi slotta kimin hangi masada oturacağını** hesaplar. Katılımcı etkinlik günü telefonunu açar, her slot için masa numarasını ve o masadaki kişileri görür.

Ürünün değeri tek bir yerde toplanıyor: **eşleştirmenin kalitesi.** Geri kalan her şey bu kaliteyi teslim etmeye yarayan taşıyıcı yapıdır.

---

## 2. Kapsam

### MVP'de var

- Kullanıcı hesabı ve detaylı profil
- Etkinlik listeleme, detay görüntüleme, başvuru
- Etkinlik oluşturma (slot süresi, mola, kontenjan ayarları)
- Salon düzeni — otomatik mod ve manuel mod
- Eşleştirme motoru (tüm kısıtlar dahil)
- Organizatör plan önizleme ve elle düzeltme
- Katılımcının kendi oturma planını ve masa arkadaşlarını görmesi
- Eşleşme sebebinin gösterilmesi
- Katılımcıların birbirine görüşme talebi göndermesi
- QR ile etkinlik girişi ve gelmeyenlere göre planın yenilenmesi

### MVP'de yok

- **E-posta gönderimi** — dolayısıyla e-posta doğrulaması ve şifre sıfırlama da yok
- Push bildirimi
- Gerçek zamanlı sohbet
- Ödeme ve biletleme
- Etkinlik sonrası raporlama ve anket
- Çok kiracılı (multi-tenant) yapı
- iOS derlemesi — kod hazır olacak ama derleme yapılmayacak (Mac gerekiyor)

**E-posta kararının sonucu bilinçlidir:** MVP'de şifresini unutan kullanıcının kendi başına kurtarma yolu yoktur. Kontrollü bir etkinlik ortamında bu kabul edilebilir. E-posta altyapısı eklendiğinde doğrulama ve şifre sıfırlama birlikte gelecek.

---

## 3. Teknoloji

| Katman | Seçim |
|---|---|
| İstemci | Flutter (Android + Web derlenecek, iOS kodu hazır ama derlenmeyecek) |
| Durum yönetimi | Riverpod |
| Yönlendirme | go_router |
| Backend | Python 3.13 + FastAPI |
| Veritabanı | PostgreSQL 16 |
| ORM / migration | SQLAlchemy (async) + Alembic |
| Kuyruk | Redis + ARQ |
| Motor | Saf Python + NumPy |
| Kimlik | Kendi JWT sistemimiz |
| Dosya | Yerel diskte klasör (S3 arayüzüyle soyutlanmış) |
| Paketleme | Docker Compose |
| Test | pytest |

Python sürümü hem yerel geliştirmede hem Docker imajında **3.13** olacak. İki ortamın sürümü ayrışmamalı.

### Çalışma ortamı

Her şey geliştiricinin kendi makinesinde, Docker Compose ile ayağa kalkar. Tek komutla tüm sistem çalışır durumda olmalı.

Telefondan test için: Flutter uygulaması, bilgisayarın yerel ağ adresine bağlanacak şekilde yapılandırılabilir olmalı. Bu adres derleme sırasında dışarıdan verilir, koda gömülmez.

### Dosya depolama notu

Profil fotoğrafları MVP'de yerel bir klasöre yazılır. Ancak kod bunu doğrudan yapmaz — arada bir depolama arayüzü olur (yükle, sil, adres al). Böylece proje devredildiğinde bulut depolamaya geçmek tek dosya değiştirmekle olur.

### Klasör yapısı

```
b2x/
├─ backend/
│  ├─ app/           FastAPI uygulaması, API uçları, veritabanı
│  └─ engine/        Eşleştirme motoru (izole)
├─ app/              Flutter
├─ infra/            docker compose, ortam dosyası örneği
└─ docs/             kararlar, notlar, devir teslim dokümanı
```

---

## 4. Sözlük

Bu terimler kod içinde de aynen kullanılır. Eşanlamlı kelime uydurulmaz.

| Terim | Anlamı |
|---|---|
| **Etkinlik (Event)** | Bir organizatörün düzenlediği, birden çok slottan oluşan buluşma |
| **Slot** | Etkinlik içindeki tek bir görüşme turu. Herkes aynı anda masasında oturur, süre bitince kalkar |
| **Mola (Break)** | Slotlar arasındaki boşluk. Katılımcıların masa değiştirme süresi |
| **Salon Düzeni (Layout)** | Masaların yerleşimi. Otomatik veya manuel kurulur |
| **Masa (Table)** | Oturmalı veya ayaklı. Her masanın bir numarası vardır |
| **Katılımcı (Participant)** | Etkinliğe başvurup kabul edilmiş kullanıcı |
| **Atama (Assignment)** | "Şu katılımcı, şu slotta, şu masada" bilgisi |
| **Plan** | Bir etkinliğin tüm slotları için tüm atamaların bütünü. Versiyonlanır |
| **Sinerji (Synergy)** | İki katılımcı arasındaki uyum skoru |
| **Çapa Kişi (Anchor)** | Organizatörün bir masaya sabitlediği kişi (sponsor, yatırımcı) |
| **Talep (Request)** | Katılımcının "bu kişiyle görüşmek istiyorum" bildirimi |

---

## 5. Mimari ilkeler

### 5.1 Motor izoledir

Eşleştirme motoru bağımsız bir Python paketidir. Girdisi sade veri yapılarıdır, çıktısı sade veri yapılarıdır. Veritabanına bakmaz, kullanıcı kimliği bilmez, HTTP görmez.

Sebepleri:

1. **Test edilebilir.** Sentetik katılımcı üretip motoru terminalden çalıştırabilirsin. Uygulamayı açmadan yüzlerce senaryo denenebilir.
2. **Değiştirilebilir.** Skorlama mantığı değişince sadece motor dosyaları değişir, arayüz hiç etkilenmez.
3. **Taşınabilir.** Proje ileride farklı bir yapıya geçse bile motor aynen kalır.

### 5.2 Plan yaşayan bir nesnedir

Eşleştirme sonucu tek seferlik bir çıktı değildir. Organizatör düzeltir, check-in sonrası yenilenir. Bu yüzden plan **versiyonlanır.**

Bir etkinliğin birden çok plan versiyonu olabilir. Aynı anda sadece biri "yayında" olur. Eski versiyonlar silinmez, saklanır. İki versiyon arasındaki farkı hesaplayabilmek gerekir — "kimin yeri değişti" sorusunun cevabı buradan gelir.

**Plan görünürlüğünün tek kaynağı plan durumudur.** Etkinlik durumu bu soruya karışmaz. Katılımcının bir atamayı görüp göremeyeceği yalnızca ilgili plan versiyonunun "yayında" olup olmadığına bakılarak belirlenir.

### 5.3 Motor deterministiktir

Aynı girdi her zaman aynı çıktıyı üretir. Rastgelelik kullanılıyorsa tohum (seed) sabitlenir ve plan kaydıyla birlikte saklanır.

Bunun iki faydası var: hata ayıklarken sonucu tekrar üretebilirsin, ve organizatör "bu sonuç neden değişti?" dediğinde cevabın olur.

### 5.4 Motor arka planda çalışır

Eşleştirme hesaplaması uzun sürer. HTTP isteği içinde çalıştırılmaz. Organizatör "eşleştir" dediğinde iş kuyruğa atılır, ekranda durum gösterilir, bitince sonuç gelir.

İşin durumu takip edilebilir olmalı: kuyrukta / çalışıyor / bitti / hata.

---

## 6. Veri modeli

Tablolar ve içerikleri. Tip ve kısıt detayları uygulama sırasında netleşir, burada ne tutulduğu anlatılıyor.

### Kullanıcı (users)
Kimlik bilgileri: e-posta, şifre özeti, kayıt tarihi, hesap durumu.

E-posta benzersizdir ancak MVP'de doğrulanmaz. Doğrulama alanı şemada yer alabilir — ileride e-posta altyapısı eklendiğinde kullanılır, ama MVP akışında hiçbir yeri engellemez.

### Profil (profiles)
Kullanıcıya bağlı, sonradan düzenlenebilir. İçeriği:

- Ad soyad, unvan
- **Şirket adı** — eşleştirmede kritik, aşağıda açıklanıyor
- Sektör (listeden seçim)
- Şehir
- Kısa tanıtım metni
- Profil fotoğrafı
- **Ne yapıyorum / ne sunuyorum** — etiket listesi, çoklu seçim
- **Ne arıyorum** — etiket listesi, çoklu seçim
- İsteğe bağlı: web sitesi, LinkedIn

**Şirket adı hakkında kritik not:** Aynı şirketten iki kişinin aynı masaya oturmaması gerekiyor. Ama kullanıcılar şirket adını serbest metin girerse "ABC Yazılım", "ABC Yazılım A.Ş.", "abc yazilim" ayrı şirket sanılır ve kural işlemez.

Çözüm: şirket adı ayrı bir tabloda tutulur. Kullanıcı yazarken mevcut şirketler önerilir, varsa seçer, yoksa yeni oluşturulur. Karşılaştırma serbest metinle değil, şirket kimliğiyle yapılır.

**Etiketler hakkında:** "Ne sunuyorum" ve "ne arıyorum" **aynı etiket havuzundan** seçilir. Sinerji hesabının temeli bu — A'nın sunduğu ile B'nin aradığı aynı etikete denk geliyorsa eşleşme var demektir. İki ayrı liste olursa karşılaştırma yapılamaz.

Etiketler kategorilere ayrılır (örneğin: yazılım hizmetleri, finansman, üretim, lojistik, danışmanlık). Kullanıcı kategorileri gezerek seçer, serbest metin yazamaz.

### Etkinlik (events)
- Ad, açıklama, kapak görseli
- Organizatör (kullanıcı referansı)
- Tarih, başlangıç saati, yer adı, adres
- Slot süresi (dakika), mola süresi (dakika), slot sayısı
- Kontenjan
- Başvuru son tarihi
- Başvuru onay biçimi: otomatik kabul / organizatör tek tek onaylar (M4)
- **Durum:** taslak / kayıtlar açık / kayıtlar kapalı / tamamlandı
- Talep sistemi kapanış zamanı
- Katılımcı başına talep hakkı (M9, varsayılanı ortam dosyasından gelir)

Etkinlik durumu yalnızca **başvuru akışını** yönetir. Planın hazır olup olmadığı, yayınlanıp yayınlanmadığı buraya yazılmaz — o bilgi plan tablosunda durur.

### Salon düzeni (layouts)
Etkinliğe bağlı, tek kayıt.
- Mod: otomatik / manuel
- Izgara boyutları (manuel modda)
- Masa listesi (aşağıda)

### Masa (tables)
- Düzene bağlı
- **Numara** — katılımcıya gösterilecek olan. Otomatik artan üretilir ama organizatör değiştirebilir. Aynı düzende iki masa aynı numarayı alamaz
- Tip: oturmalı / ayaklı
- Sandalye sayısı (oturmalı ise; ayaklı ise boş)
- Önerilen kişi aralığı (ayaklı ise; alt ve üst sınır)
- Izgara konumu (manuel modda: x, y)
- Etiket (isteğe bağlı: "Sponsor Masası", "Yatırımcı Masası")

### Alan bloğu (layout_areas)
Manuel modda salona konan, masa olmayan işaretler: sahne, giriş, büfe, kayıt masası. Sadece görsel yön bulma amaçlı, eşleştirmeye girmez.
- Etiket metni, ızgara konumu, boyut

### Başvuru (registrations)
- Etkinlik, kullanıcı
- Durum: beklemede / kabul / red / iptal
- Başvuru tarihi
- **Katılım durumu:** gelmedi / geldi (check-in ile işaretlenir)
- Check-in zamanı
- QR kodu (her katılımcı için benzersiz)

### Talep (meeting_requests)
- Etkinlik, talep eden, talep edilen
- Oluşturma zamanı
- Durum: aktif / iptal

Aynı kişiye aynı etkinlikte birden fazla talep gönderilemez.

### Plan (plans)
- Etkinlik
- Versiyon numarası
- **Durum:** taslak / yayında / arşiv
- Oluşturulma zamanı, yayınlanma zamanı
- Kullanılan tohum değeri
- Hesaplama özeti: toplam görüşme sayısı, en az görüşme alan kişinin görüşme sayısı, ortalama masa skoru, çalışma süresi
- Bir önceki versiyona referans (varsa)

Bir etkinlikte aynı anda **en fazla bir** plan "yayında" olabilir. Yeni bir versiyon yayınlandığında önceki otomatik olarak "arşiv" durumuna geçer.

### Atama (assignments)
Planın satırları. Her satır bir kişinin bir slottaki yerini söyler.
- Plan, slot numarası, masa, katılımcı
- Sabit mi (çapa kişi veya organizatörün elle sabitlediği atama, motor bunu değiştiremez)

Bir kişi bir slotta hiçbir masaya atanmamışsa o slot için satır oluşmaz.

### Eşleşme gerekçesi (match_reasons)
Bir plandaki iki kişinin neden aynı masaya konduğunun kaydı.
- Plan, slot numarası, kişi A, kişi B
- Toplam sinerji skoru
- Kırılım: hangi kriterden kaç puan geldiği ve insan diliyle açıklaması

Bu tablo katılımcıya "neden bu kişiyle eşleştim" cevabını verir. Motor skoru hesaplarken zaten bu bilgiye sahiptir, sadece saklanır.

---

## 7. Roller

**Katılımcı** — profil doldurur, etkinliklere başvurur, kendi planını görür, talep gönderir.

**Organizatör** — etkinlik oluşturur, salon kurar, başvuruları yönetir, eşleştirmeyi çalıştırır, planı düzeltir ve yayınlar, check-in yapar.

**Her kayıtlı kullanıcı etkinlik oluşturabilir.** Ayrı bir organizatör onayı, yetki katmanı veya rol atama ekranı yoktur. Rol kullanıcıya değil, **etkinliğe göre** belirlenir: kendi oluşturduğu etkinlikte organizatör, başvurduğu etkinlikte katılımcıdır.

### Görünürlük kuralları — sıkı uygulanır

Katılımcı:
- Kendi atamalarını görür
- Kendi masasındaki kişilerin profillerini görür
- **Başka masalarda kimin oturduğunu göremez**
- İlgili plan versiyonu "yayında" değilse hiçbir atama göremez

Bu kural API seviyesinde uygulanır. "Arayüzde göstermiyoruz" yeterli değil — istek doğrudan atılsa bile veri dönmemeli.

Organizatör kendi etkinliğinin her şeyini görür. Başka organizatörlerin etkinliklerinin planlarına erişemez.

---

## 8. Modüller

### M1 — Kimlik

E-posta ve şifreyle kayıt. Giriş, çıkış.

**MVP'de e-posta doğrulaması ve şifre sıfırlama yoktur.** Kayıt anında hesap doğrudan kullanılabilir hale gelir. Bu bilinçli bir sadeleştirmedir, e-posta altyapısı MVP dışında bırakıldığı için.

Kısa ömürlü erişim jetonu, uzun ömürlü yenileme jetonu. Jetonlar cihazda güvenli depoda saklanır. Süresi dolan jeton arka planda sessizce yenilenir, kullanıcı tekrar giriş yapmak zorunda kalmaz.

Şifreler modern bir özetleme algoritmasıyla saklanır. Düz metin şifre hiçbir yere yazılmaz, loglanmaz.

Kayıt ekranında şifre gücü için asgari kural uygulanır ve kullanıcıya "şifrenizi unutursanız kurtarma seçeneği bulunmuyor" uyarısı gösterilir.

### M2 — Profil

Kayıttan sonra profil sihirbazı açılır. Adım adım ilerler, her adım kaydedilir, kullanıcı yarıda bırakıp sonra devam edebilir.

Sihirbaz sırası: temel bilgiler → şirket ve sektör → ne sunuyorum → ne arıyorum → fotoğraf.

**Profil tamamlanma yüzdesi** hesaplanır ve gösterilir. Eksik profil eşleştirmede kötü sonuç verir, kullanıcının bunu bilmesi lazım.

**Etkinliğe başvurabilmek için profil en az şu alanları içermeli:** ad soyad, şirket, sektör, en az üç "sunuyorum" etiketi, en az üç "arıyorum" etiketi. Eksikse başvuru butonu çalışmaz ve neyin eksik olduğu yazılır.

Profil her zaman düzenlenebilir. Ancak plan yayınlandıktan sonra yapılan değişiklikler o etkinliğin planını etkilemez.

### M3 — Etkinlik keşfi ve başvuru

Yaklaşan etkinliklerin listesi. Her kart: ad, tarih, yer, kalan kontenjan, başvuru durumu.

Detay ekranı: açıklama, program (slot saatleri hesaplanmış halde), yer bilgisi, kaç kişi katılıyor, başvur butonu.

**Slot saatleri hesaplanır ve gösterilir.** Organizatör başlangıç saati, slot süresi, mola süresi ve slot sayısı girer; sistem "Slot 1: 10:00-10:30, Slot 2: 10:40-11:10..." şeklinde programı üretir.

Başvuru durumları kullanıcıya net gösterilir: başvurmadı / beklemede / kabul edildi / reddedildi.

Kontenjan dolduysa veya son başvuru tarihi geçtiyse başvuru kapanır.

### M4 — Etkinlik oluşturma

Organizatörün adım adım ilerlediği bir sihirbaz.

**Temel bilgiler:** ad, açıklama, tarih, saat, yer, kapak görseli.

**Program:** slot süresi, mola süresi, slot sayısı. Girildikçe hesaplanan program anlık gösterilir, bitiş saati görünür. Organizatör "çok uzun sürüyor" diye anında fark eder.

**Kontenjan:** maksimum katılımcı sayısı, başvuru son tarihi, başvurular otomatik mi kabul edilecek yoksa organizatör tek tek mi onaylayacak.

**Salon düzeni:** M5'e geçilir.

Etkinlik taslak olarak kaydedilebilir, sonra devam edilebilir. Salon düzeni kurulmadan kayıtlar açılamaz.

**Kapasite uyarısı:** salon düzeni kurulduğunda toplam oturma kapasitesi hesaplanır. Kontenjan kapasiteden büyükse organizatör uyarılır. Bu bir engel değil uyarıdır, çünkü gelmeyecekler hesaba katılabilir.

### M5 — Salon düzeni

İki mod var. Organizatör hangisini istediğini seçer.

#### Otomatik mod

Organizatör sadece şunları girer:
- Masa tipi (oturmalı / ayaklı)
- Masa sayısı
- Oturmalı ise: masa başına sandalye sayısı
- Ayaklı ise: masa başına önerilen alt ve üst kişi sınırı

Sistem masaları oluşturur ve 1'den başlayarak numaralandırır. **Görsel kroki yoktur.** Katılımcıya sadece masa numarası gösterilir.

Bu mod, organizatörün gerçek hayatta masalara numara koyacağı varsayımına dayanır. Arayüzde bu açıkça yazılır: "Katılımcılar masa numarasıyla yerlerini bulacak. Salonda masalara numara koymayı unutmayın."

Masalar farklı sandalye sayısına sahip olabilmeli — organizatör sonradan tek tek düzenleyebilir.

#### Manuel mod

Organizatör salonu ekranda kurar.

**Tuval:** boş bir ızgara. Boyutu ayarlanabilir (kaça kaç hücre). Yakınlaştırma ve kaydırma desteklenir, hem parmakla hem fareyle çalışır.

**Izgaraya oturma:** masalar serbestçe sürüklenir ama bırakıldığında en yakın ızgara noktasına oturur. Kullanıcı bunu fark etmez, sadece düzen kendiliğinden hizalı çıkar. İki masa aynı hücreye konamaz.

**Masa ekleme:** araç çubuğundan tip seçilir, tuvale dokunulur, masa oraya konur.

**Masa düzenleme:** masaya dokununca panel açılır. Değiştirilebilenler:
- Numara (varsayılan otomatik artan, ama elle değiştirilebilir)
- Sandalye sayısı
- Etiket ("Sponsor Masası" gibi, isteğe bağlı)
- Silme

**Numara çakışması:** iki masa aynı numarayı alamaz. Denendiğinde uyarı verilir. Bu kritik — katılımcı masasını numarayla buluyor.

**Alan blokları:** sahne, giriş, büfe gibi işaretler konabilir. Sadece metin etiketi ve konum. Katılımcının salonda yön bulmasına yarar. Alan blokları da ızgaraya oturur ve masalarla aynı hücreyi paylaşamaz.

**Kaydetme:** düzen otomatik kaydedilir. Organizatör "kaydet" aramak zorunda kalmaz.

**Manuel modda MVP'ye girmeyenler:** masa döndürme, çoklu seçim, kopyala-yapıştır, geri al / ileri al geçmişi. Bunlar sonraki sürüme.

#### Masa kapasitesi kuralları

**Oturmalı masa:** sandalye sayısı kesin üst sınırdır. 3 sandalyeli masaya 4 kişi atanamaz.

**Ayaklı masa:** üst sınır kesindir. Organizatörün girdiği alt sınır ise bir hedeftir, kesin kural değildir.

**Her masa için geçerli kural:** kullanılan bir masada en az iki kişi olur. Tek kişilik masa kimseye bir şey vermez — o kişi otuz dakika tek başına oturur. Motor ya masaya en az iki kişi koyar ya masayı boş bırakır.

### M6 — Eşleştirme motoru

Bu modülün detayı Bölüm 9'da. Burada sadece arayüz tarafı:

Organizatör kayıtları kapatır. "Eşleştirmeyi çalıştır" butonu aktif olur. Basınca iş kuyruğa girer, ekranda durum gösterilir. Bittiğinde plan önizlemesi açılır.

Çalıştırma öncesi kontrol listesi gösterilir:
- Kaç katılımcı kabul edilmiş
- Kaç masa, toplam kapasite ne
- Kaç talep gelmiş
- Eksik profilli katılımcı var mı

Sorun varsa organizatör uyarılır ama çalıştırma engellenmez.

Talep sistemi henüz kapanmadan eşleştirme çalıştırılırsa organizatör ayrıca uyarılır — sonradan gelecek talepler bu plana yansımayacaktır.

### M7 — Plan önizleme ve düzeltme

Motor bitince organizatör planı görür. Plan "taslak" durumundadır, **katılımcılar göremez.**

#### Görünüm

Slot seçici üstte. Seçili slot için tüm masalar ve kimlerin oturduğu listelenir.

Her masa için gösterilenler:
- Numara ve etiket
- Oturan kişiler (ad, şirket)
- Doluluk (kaç kişi / kaç sandalye)
- Masa kalite göstergesi — sayı değil, üç seviye: iyi / orta / zayıf

#### Özet paneli

Planın genel sağlığı tek bakışta görünmeli:
- Toplam görüşme sayısı
- **En az görüşme alan kişi kaç görüşme aldı** — bu en önemli sayı
- Hiç eşleşmemiş kişi var mı, varsa kimler
- Karşılanan talep sayısı / toplam talep

#### Elle düzeltme — takas yöntemi

Sürükle-bırak yerine takas kullanılır: bir kişiye dokunulur, sonra ikinci kişiye dokunulur, yerleri değişir. Mobilde çok daha güvenilir çalışır ve aynı işi görür.

Boş sandalyeye taşıma da desteklenir: kişiye dokun, boş yere dokun, oraya taşınır.

#### Takas sonrası doğrulama

Her takastan sonra kontrol çalışır ve sonuç anında gösterilir:
- Aynı şirketten iki kişi aynı masada mı
- Masa kapasitesi aşıldı mı
- Bir masada tek kişi kaldı mı
- Bu ikili başka bir slotta zaten eşleşiyor mu
- Masanın kalite göstergesi nasıl değişti

Organizatör uyarıya rağmen devam edebilir — ama ne yaptığını bilerek yapar.

#### Sabitleme

Organizatör bir atamayı sabitleyebilir. Sabitlenen atama, motor tekrar çalıştırılsa bile değişmez. Çapa kişiler de sabit atama olarak tutulur.

#### Yayınlama

Organizatör "yayınla" der. Plan durumu "yayında" olur, katılımcılar kendi yerlerini görmeye başlar. Varsa önceki yayındaki plan "arşiv" durumuna geçer.

Yayınlanmış plan üzerinde düzeltme yapılabilir ama bu yeni bir versiyon oluşturur — mevcut yayındaki plan, yeni versiyon yayınlanana kadar olduğu gibi kalır.

### M8 — Katılımcı görünümü

Plan yayınlanmadan katılımcı hiçbir şey göremez. Etkinlik ekranında "Oturma planınız henüz hazırlanıyor" yazar.

Yayınlandıktan sonra:

#### Slot listesi

Katılımcının tüm slotları sırayla. Her satır:
- Slot numarası ve saati
- Masa numarası
- Kiminle oturacağı (isim ve şirket)

Bir slotta eşleşmemişse o slot "Bu turda serbestsin" olarak gösterilir. Boş bırakılmaz, açıklama yazılır.

#### Slot detayı

Bir slota dokununca:
- Masa numarası büyük ve net
- Manuel düzen varsa: krokide masanın yeri işaretli
- Masadaki her kişi için kart: fotoğraf, ad, unvan, şirket
- Her kişi için **eşleşme gerekçesi**

#### Eşleşme gerekçesi

Karşıdaki kişiyle neden eşleştiğini anlatan bir veya iki kısa cümle. Örnek: "İkiniz de fintech sektöründesiniz" veya "Kendisi yazılım geliştirme hizmeti sunuyor, siz bunu arıyorsunuz."

**Sayı gösterilmez.** "Uyum: %62" gibi bir ifade kullanılmaz. Sayı gören insan not almış gibi hisseder ve "neden 62?" tartışması çıkar. Sadece sebep gösterilir.

Gerekçe cümleleri kalıp metinlerden üretilir, her kriter için önceden yazılmış bir şablon vardır.

#### Profil görüntüleme

Masadaki kişinin tam profiline bakılabilir. Ancak sadece **aynı masada oturduğu kişilerin** profilini görebilir.

### M9 — Görüşme talepleri

Katılımcı, etkinliğe kabul edilmiş diğer katılımcıların listesini görür. Arama ve sektöre göre filtreleme var. Listede ad, unvan, şirket, sektör görünür.

Bir kişiye "görüşmek istiyorum" talebi gönderilebilir.

#### Kurallar

**Talep hakkı sınırlıdır.** Her katılımcı etkinlik başına belirli sayıda (varsayılan 3, organizatör değiştirebilir) talep gönderebilir. Kalan hak ekranda gösterilir.

Bu sınır olmazsa herkes herkese talep atar ve sistem "en çok talep atan kazanır"a döner. Kıtlık, insanı gerçekten istediğini seçmeye zorlar.

**Karşılıklı talep çok daha güçlüdür.** A, B'yi istiyor ve B de A'yı istiyorsa bu neredeyse kesin eşleşmedir. Tek taraflı talep sadece güçlü bir tercihtir, garanti değildir.

**Talep gönderildiği kişiye bildirilmez.** Karşı taraf kimin kendisini istediğini görmez. Sebep: sosyal baskı yaratmamak. Sadece eşleşme gerçekleşirse ve karşılıklıysa, plan ekranında "ikiniz de görüşmek istemiştiniz" notu çıkar.

**Talepler bir zamanda kapanır.** Etkinlikten önce belirlenmiş bir anda talep sistemi kapanır. Kapanmazsa plan hiç kilitlenemez.

**Talep garanti değildir.** Arayüzde bu açıkça yazılır: "Talepleriniz eşleştirmede öncelikli değerlendirilir, ancak karşılanacağı garanti edilmez."

### M10 — Check-in ve planın yenilenmesi

#### QR üretimi

Her kabul edilmiş katılımcı için benzersiz bir kod üretilir. Katılımcı bunu uygulamada QR olarak görür. İnternet olmasa bile görüntülenebilmeli — ekran görüntüsü alınabilir olmalı.

#### Tarama

Organizatörün ekranında kamera açılır, girişte katılımcıların kodları okutulur. Okunan kişi "geldi" olarak işaretlenir, ekranda adı ve fotoğrafı belirir.

Elle arama da olmalı — telefonu bozulan, kodu bulamayan kişi listeden bulunup elle işaretlenebilir.

Sayaç sürekli görünür: kaç kişi geldi, kaç kişi bekleniyor.

#### Yeniden çalıştırma

Organizatör "planı güncelle" der. Motor **gelmeyenler çıkarılmış** halde tekrar çalışır ve yeni bir plan versiyonu üretir.

**Burada kritik bir kural var: minimum değişim.**

Motor sıfırdan çalışırsa herkesin planı değişir. Dün akşam masasını öğrenmiş olan kişi sabah bambaşka bir yere düşer. Kapıda kaos çıkar.

Bunun yerine motor, bir önceki versiyonu başlangıç noktası olarak alır ve **gereksiz yere kimseyi kıpırdatmaz.** Sadece kişi kaybeden masalar onarılır. Bu, skor hesabına eklenen bir ceza terimiyle sağlanır (Bölüm 9.8).

**İkinci kural:** başlamış veya bitmiş slotlara dokunulmaz. Sadece gelecek slotlar yeniden hesaplanır.

Yeni versiyon organizatöre gösterilir, **kimin yeri değişti** listelenir, organizatör onaylayınca yayına geçer.

---

## 9. Eşleştirme motoru — detay

Projenin kalbi. Bu bölüm en dikkatli okunacak yerdir.

### 9.1 Problem gerçekte ne

Bu bir "ikili eşleştirme" problemi değildir. İki şeyin birleşimidir:

**Gruplama:** N katılımcıyı M masaya bölmek. Masada herkes herkesle oturur — sadece bir kişiyle değil. Yani skorlama ikili değil, **masa bazlı** olmak zorunda.

**Çok turlu çizelgeleme:** Etkinlikte birden çok slot var ve kimse kimseyle iki kez karşılaşmamalı. Yani Slot 1'deki karar Slot 8'i etkiler. Slotlar tek tek çözülemez, birlikte çözülmeli.

Bu problem NP-zordur. Kesin en iyi çözümü bulmanın hızlı yolu yoktur. Yaklaşım: **iyi bir başlangıç üret, sonra iyileştir.**

Hazır çözücü (OR-Tools gibi) kullanılmayacak. Sebep: "en zayıf bağ" skoru, adalet kuralı ve minimum değişim modu bu çözücülerde ifade edilmesi çok zahmetli kurallardır. Elle yazılmış yerel arama hem daha kısa hem daha kontrollü.

### 9.2 Girdi ve çıktı sözleşmesi

Motor şunları alır:

- **Katılımcı listesi:** her biri için tam sayı kimlik, şirket kimliği, sunulan etiketler, aranan etiketler, sektör, şehir
- **Masa listesi:** tam sayı kimlik, tip, kapasite (oturmalı ise sandalye sayısı, ayaklı ise alt-üst aralık)
- **Slot sayısı**
- **Talep listesi:** kimden kime
- **Sabit atamalar:** çapa kişiler ve organizatörün kilitlediği atamalar
- **Önceki plan (isteğe bağlı):** minimum değişim modu için
- **Ayarlar:** kişi başı asgari görüşme sayısı, kalite eşiği, tohum değeri

Motor şunları döndürür:

- **Atama listesi:** her satırda slot numarası, masa kimliği, katılımcı kimliği
- **Gerekçe listesi:** aynı masada oturan her ikili için skor kırılımı
- **Özet:** toplam görüşme, en az görüşme alan kişinin sayısı, eşleşmemiş kişiler, karşılanan talep sayısı, çalışma süresi

Motor veritabanı kimlikleri yerine kendi içinde tam sayı indeks kullanır. Dönüşüm dış katmanda yapılır — motor hızlı kalır.

### 9.3 Sinerji skoru — ikili uyum

İki katılımcı arasındaki uyum. Bileşenleri:

**Arz-talep eşleşmesi (en ağırlıklı).** A'nın sunduğu etiketlerle B'nin aradığı etiketlerin kesişimi. Ters yönü de hesaplanır. Çift yönlü eşleşme (A B'ye yarıyor VE B A'ya yarıyor) tek yönlüden çok daha değerlidir.

**Kategori düzeyinde kısmi puan.** Tam etiket eşleşmesi yoksa, etiketlerin **kategorileri** karşılaştırılır: A'nın sunduğu etiketlerin kategorileriyle B'nin aradıklarının kategorileri kesişiyorsa kısmi puan verilir. Tam eşleşme her zaman kısmiyi gölgeler — ikisi toplanmaz, büyüğü alınır.

Sebep: etiket havuzu inceldikçe alıcıyla satıcı aynı kelimeyi seçmiyor. "Backend geliştirme" sunan ile "Web yazılımı" arayan kesin bir eşleşme ama farklı etiket seçmişler. Kısmi puan olmadan sıfır alırlar.

Kısmi puanın üst sınırı **tek bir tam etiket eşleşmesidir**: bir tam eşleşme, "aynı alandayız"dan daha güçlü bir kanıttır. Sektör bonusu da kısmi puanla açılmaz — tam eşleşme arar, yoksa zayıf bir sinyal iki kez sayılmış olur.

**Sektör ilişkisi.** Aynı sektör bazen iyidir (ortak dil), bazen kötüdür (rakipler). Bunu "aynı sektör = iyi" diye basitleştirme. Doğrusu: aynı sektörde olup **biri sunan biri arayan** ise çok iyi; ikisi de aynı şeyi sunuyorsa nötr veya düşük.

**Coğrafi yakınlık.** Aynı şehir küçük bir artı.

**Talep bonusu.** Karşılıklı talep çok büyük artı. Tek taraflı talep orta artı.

**Çeşitlilik cezası.** Etiketleri neredeyse tıpatıp aynı olan iki kişi — yani ikisi de aynı şeyi sunup aynı şeyi arayan — birbirine bir şey katmaz. Küçük bir ceza.

Ağırlıklar tek bir ayar dosyasında toplanır. Motorun içine dağıtılmaz. Sebep: bu ağırlıklar mutlaka ayarlanacak, her seferinde kod aramak istemezsin.

Skor hesaplanırken **hangi bileşenden kaç puan geldiği saklanır.** Bu, katılımcıya gösterilecek gerekçenin kaynağıdır.

### 9.4 Masa skoru — en zayıf bağ

Bu kural yanlış konursa ürün sessizce kötüleşir.

Masa skoru, masadaki ikililerin skorlarının **toplamı değildir.**

Örnek: 4 kişilik bir masada üç kişi birbirine mükemmel uyumlu, dördüncü kişi hepsine tamamen alakasız. Toplama bakan bir sistem bu masayı yüksek puanlı görür. Ama o dördüncü kişi otuz dakika boyunca dışlanmış hisseder.

**Doğrusu: masa skoru, masadaki en zayıf ikili bağın skorudur.**

Böylece "kimse masada yabancı kalmasın" garantisi gelir. Çok katı gelirse en düşük tek değer yerine en düşük dilimin ortalaması alınabilir — ama mantık aynı kalır: **masanın kalitesini en kötü ilişki belirler.**

### 9.5 Kısıtlar

#### Kesin kurallar — asla ihlal edilemez

**Kapasite.** Oturmalı masada kişi sayısı sandalye sayısını aşamaz. Ayaklı masada üst sınırı aşamaz.

**Asgari grup.** Kullanılan bir masada en az iki kişi olur. Tek kişilik masa oluşturulmaz — ya en az iki kişi, ya boş masa.

**Aynı şirket ayrımı.** Aynı şirketten iki kişi aynı masaya asla oturamaz. Bu kuralın amacı: herkes farklı bir potansiyel iş bağlantısıyla tanışsın.

**Tekrar yok.** İki kişi etkinlik boyunca en fazla bir kez aynı masada oturur.

**Tek yer.** Bir kişi bir slotta en fazla bir masada olabilir. Hiçbir masaya atanmamış olması mümkündür.

**Sabit atamalar.** Çapa kişiler ve kilitlenmiş atamalar değiştirilemez.

#### Esnek kurallar — skorla yönetilir

**Kalite eşiği.** Sinerji skoru belirli bir değerin altındaysa o ikili tercih edilmez. Ama bu mutlak yasak değildir — adalet kuralı devreye girerse eşik esnetilir.

**Masa doluluğu.** Masaları doldurma zorunluluğu yoktur. 4 sandalyeli masada 2 kişi oturabilir. Boş sandalye, kötü eşleşmeden iyidir.

**Ayaklı masa alt sınırı.** Organizatörün girdiği alt sınır bir hedeftir. Motor ona ulaşmaya çalışır ama kalite pahasına zorlamaz. Kesin olan tek alt sınır, yukarıdaki "asgari grup" kuralıdır.

### 9.6 Adalet kuralı

Bu kural olmazsa ürün en sık şu şekilde başarısız olur:

Etkinlikte 200 kişi var, 180'i bir sektörden, 20'si bambaşka bir alandan. Motor "kalitesiz eşleşme yapmayayım" diyor. Sonuç: çoğunluk sekiz slotun sekizinde dolu, azınlık sekiz slotun birinde. O yirmi kişi bilete para vermiş, boş masada oturuyor.

**Çözüm:** kalite tek başına maksimize edilmez. Yanına şu kural konur:

> Her katılımcı **en az N görüşme** almak zorundadır. (Varsayılan 4, ayarlanabilir.)

Bu kesin bir kuraldır. Ancak sağlanamayacak durumlar olabilir — o zaman motor mümkün olan en yüksek asgariyi hedefler ve özet raporunda bunu bildirir.

Ve şu ilke: motor **toplam skoru değil, en kötü durumdaki kişinin durumunu** iyileştirmeye çalışır. Etkinliğin itibarını en mutlu katılımcı değil, en mutsuz katılımcı belirler.

### 9.7 Algoritma adımları

Bu numaralandırma yalnızca algoritmanın içindeki sırayı ifade eder. Projenin yapım sırası olan "Aşama" kavramıyla karıştırılmamalı.

**Adım 1 — Skor matrisi.** Tüm katılımcı ikilileri için sinerji skoru bir kez hesaplanır ve bellekte tutulur. NumPy ile yapılır, hızlıdır. Sonrasında her skor sorgusu tablo okuması olur.

**Adım 2 — Sabit atamaların yerleştirilmesi.** Çapa kişiler ve kilitli atamalar önce yerine konur, motor bunları hiç oynatmaz.

**Adım 3 — Açgözlü başlangıç.** Her slot için: en yüksek skorlu ikili bulunur ve bir masaya oturtulur. O masaya en uyumlu üçüncü kişi eklenir, sonra dördüncü. Kesin kurallar her aşamada kontrol edilir. Masa dolunca veya uygun kimse kalmayınca yeni masaya geçilir. Sonuç mükemmel değildir ama geçerli bir plandır.

**Adım 4 — Yerel arama.** Mevcut plandan başlanır, küçük değişiklikler denenir:
- İki kişinin yerini değiştir
- Bir kişiyi başka masaya taşı
- Bir kişiyi masadan çıkar (boş bırakmak daha iyiyse)

Her değişiklikten sonra skor yeniden hesaplanır. İyileştirdiyse tutulur, kötüleştirdiyse geri alınır. Ara sıra kötüleştiren hamleler de kabul edilir — yoksa algoritma yerel bir tepede sıkışıp kalır. Bu kabul oranı zamanla azalır.

Yüz binlerce deneme yapılır. Sonuç matematiksel olarak en iyi olmaz ama en iyiye çok yakın olur, ve kimse farkı göremez.

**Adım 5 — Adalet düzeltmesi.** Asgari görüşme sayısını tutturamamış kişiler bulunur. Bu kişiler için kalite eşiği esnetilir ve uygun masalara yerleştirilmeye çalışılır.

**Adım 6 — Gerekçe üretimi.** Nihai plandaki her masa arkadaşlığı için skor kırılımı toplanır ve saklanır.

### 9.8 Minimum değişim modu

Check-in sonrası yeniden çalıştırmada kullanılır.

Fark: Adım 3 (açgözlü başlangıç) atlanır. Bunun yerine **önceki plan başlangıç noktası olur.** Gelmeyenler çıkarılır, boşluklar oluşur, Adım 4 doğrudan bu plan üzerinde çalışır.

Ve skor fonksiyonuna bir ceza terimi eklenir: **yeri değişen her kişi için ceza.** Ceza katsayısı yüksek tutulur.

Sonuç: motor "gerekmedikçe kimseyi kıpırdatma, sadece delik açılan masaları onar" davranışı sergiler.

Ayrıca başlamış slotlar tamamen dondurulur.

Bu modda "asgari grup" kuralı yine geçerlidir: bir masada tek kişi kaldıysa o kişi başka bir masaya taşınır veya masa boşaltılır.

### 9.9 Performans beklentisi

Ölçek: yaklaşık 200 katılımcı, 8 slot, 50 masa.

Skor matrisi saniyenin altında hesaplanır. Yerel arama on saniyeler mertebesinde sürer. Bu kabul edilebilir çünkü arka planda çalışıyor ve organizatör ilerleme görüyor.

Beklenenden yavaş çıkarsa çözüm sırası: önce deneme sayısını azalt, sonra sıcak döngüyü derlenmiş hale getir. Mimariyi değiştirmeye gerek yok.

### 9.10 Motor testleri

Motorun testleri diğer her şeyden önce yazılır. Sentetik katılımcı üreten bir yardımcı olur — parametreleriyle senaryo kurulabilir.

**Kesin kural testleri:**
- Aynı şirketten iki kişi hiçbir masada aynı anda oturmuyor
- Hiçbir masada sandalye sayısından fazla kişi yok
- Hiçbir masada tek kişi oturmuyor
- Hiçbir ikili iki farklı slotta karşılaşmıyor
- Hiç kimse aynı slotta iki masada değil
- Sabit atamalar korunmuş

**Kalite testleri:**
- Her katılımcı asgari görüşme sayısına ulaşmış (veya ulaşılamadığı raporlanmış)
- Hiçbir masada, kalite eşiğinin çok altında bir ikili yok

**Zor senaryolar:**
- Tek şirketten çok fazla kişi (şirket ayrımı kuralı sistemi kilitliyor mu)
- Kapasiteden fazla katılımcı
- Kapasiteden çok az katılımcı
- Herkes birbirine uyumsuz
- Herkes birbirine aşırı uyumlu
- Bir kişi hariç herkes aynı sektörde (adalet kuralı çalışıyor mu)
- Tüm masalar çapa kişili
- Tek sayıda katılımcı — asgari grup kuralıyla artan kişiye ne oluyor

**Determinizm testi:**
- Aynı girdi ve aynı tohumla iki kez çalıştırıldığında birebir aynı sonuç

**Minimum değişim testi:**
- Yüz kişilik plandan on kişi çıkarıldığında, yeri değişen kişi sayısının makul bir sınırın altında kalması

---

## 10. Kabul kriterleri

Modül "bitti" sayılmadan önce bunlar doğrulanır.

**Kimlik:** Kayıt olan kullanıcı doğrudan giriş yapabiliyor. Erişim jetonunun süresi dolduğunda kullanıcı fark etmeden yenileniyor.

**Profil:** Eksik profille etkinliğe başvurulamıyor ve eksiğin ne olduğu yazıyor. Şirket adı seçildiğinde mevcut şirketlerle eşleşiyor, aynı şirket iki kez oluşturulmuyor.

**Etkinlik oluşturma:** Slot ve mola süreleri girildiğinde program anlık hesaplanıyor ve bitiş saati görünüyor. Kontenjan kapasiteyi aşarsa uyarı çıkıyor. Salon düzeni kurulmadan kayıtlar açılamıyor.

**Otomatik düzen:** Masa sayısı ve sandalye sayısı girilince masalar numaralı olarak oluşuyor.

**Manuel düzen:** Masa sürüklenip bırakıldığında ızgaraya oturuyor. İki masa aynı hücreye konamıyor. Aynı numara iki kez verilemiyor. Sayfa yenilendiğinde düzen kayıpsız geliyor.

**Motor:** Bölüm 9.10'daki testlerin tamamı geçiyor.

**Plan önizleme:** Organizatör her slotu görebiliyor. İki kişi takas edildiğinde kural ihlali anında uyarı olarak çıkıyor. En az görüşme alan kişinin sayısı özet panelde görünüyor.

**Plan durumu:** Bir etkinlikte aynı anda birden fazla plan yayında olamıyor. Yeni versiyon yayınlandığında önceki arşive geçiyor.

**Görünürlük:** Katılımcı, başka masadaki kişilerin bilgilerine API üzerinden doğrudan istek atsa bile erişemiyor. Plan yayında değilken hiçbir atama görünmüyor.

**Gerekçe:** Her masa arkadaşı için anlamlı bir cümle gösteriliyor. Hiçbir yerde sayısal skor görünmüyor.

**Talepler:** Talep hakkı sınırı çalışıyor. Kapanış zamanından sonra talep gönderilemiyor. Talep edilen kişi kimin talep ettiğini göremiyor.

**Check-in:** QR okunduğunda katılımcı geldi olarak işaretleniyor. Gelmeyenler çıkarılıp plan güncellendiğinde, yeri değişenlerin listesi organizatöre gösteriliyor.

**Taşınabilirlik:** Ortam dosyası değiştirilerek proje başka bir makinede tek komutla ayağa kalkıyor. Kodun hiçbir yerinde sabit adres yok.

---

## 11. Yapım sırası

Sıra önemlidir. Riskli parça en başta yazılır.

Bu numaralandırma projenin yapım sırasıdır. Algoritmanın içindeki "Adım" kavramıyla karıştırılmamalı.

**Aşama 0 — Temel.** Repo yapısı, Docker Compose, veritabanı bağlantısı, migration altyapısı, ortam değişkeni yönetimi, boş FastAPI uygulaması, boş Flutter projesi. Sistem tek komutla ayağa kalkıyor olmalı.

**Aşama 1 — Veri modeli.** Bölüm 6'daki tüm tablolar ve migration'lar. Plan versiyonlama yapısı baştan doğru kurulur, sonradan eklenmez.

**Aşama 2 — Eşleştirme motoru.** Hiçbir arayüz olmadan, sentetik veriyle, terminalden çalıştırılarak. Bölüm 9'un tamamı. Testler yazılır ve geçer. **Bu aşama bitmeden arayüze geçilmez.** Projenin tüm riski burada.

**Aşama 3 — Kimlik ve profil.** Kayıt, giriş, profil sihirbazı, etiket sistemi, şirket sistemi.

**Aşama 4 — Etkinlik oluşturma ve otomatik düzen.** Sihirbaz, program hesaplama, otomatik masa üretimi.

**Aşama 5 — Manuel salon editörü.** Izgara, masa yerleştirme, düzenleme, alan blokları.

**Aşama 6 — Etkinlik keşfi ve başvuru.** Liste, detay, başvuru akışı, organizatörün başvuru yönetimi.

**Aşama 7 — Motor entegrasyonu.** Arka plan işi, çalıştırma ekranı, plan üretimi, organizatör önizlemesi.

**Aşama 8 — Elle düzeltme.** Takas mekanizması, doğrulama uyarıları, sabitleme, yayınlama.

**Aşama 9 — Katılımcı görünümü.** Slot listesi, slot detayı, eşleşme gerekçesi, masa arkadaşı profilleri, görünürlük kuralları.

**Aşama 10 — Talep sistemi.** Katılımcı listesi, talep gönderme, hak sınırı, motora bonus olarak bağlanması.

**Aşama 11 — Check-in.** QR üretimi, tarama ekranı, elle işaretleme, minimum değişim modunda yeniden çalıştırma, değişenlerin raporlanması.

**Aşama 12 — Sağlamlaştırma.** Uçtan uca deneme (sahte bir etkinliği baştan sona çalıştır), hata durumları, boş durumlar, devir teslim dokümanı.

---

## 12. Açık kararlar

Bunlar henüz netleşmedi, ilerledikçe doldurulacak.

- ~~Etiket havuzunun içeriği: kaç kategori, her kategoride hangi etiketler~~ — Aşama 3'te başlangıç seti kondu (6×8), Aşama 6'da 9 kategori × 8 etikete çıkarıldı. Aşama 7'de 9.3'e kategori düzeyinde kısmi puan eklenince tavan yükseldi: **~120 etiket** artık bugünkü 72 kadar iyi sonuç veriyor. Kategori sayısı 9-15'te kalmak şartıyla — kategoriler etiketlerle birlikte çoğalırsa kısmi puanın etkisi kayboluyor (ölçüm `docs/kararlar.md`'de)
- ~~Sektör listesinin içeriği~~ — Aşama 3'te başlangıç seti kondu: 18 sektör. Gerçek etkinlik verisiyle ayarlanacak
- Sinerji skoru bileşenlerinin başlangıç ağırlıkları (test verisiyle ayarlanacak)
- Kalite eşiğinin nihai değeri — başlangıç değeri ortam dosyasında, test verisiyle ayarlanacak
- Görsel kimlik ve tema (Departure Board estetiği — ayrı bir tasarım notunda ele alınacak)
- ~~Manuel salon editöründe varsayılan ızgara boyutu ve hücre ölçüsü~~ — Aşama 5'te kondu: 24×16 hücre, hücre 64 piksel. Izgara 2 ile 60 arasında ayarlanabilir
- Proje devredildikten sonra hangi sunucuya kurulacağı — devir teslim dokümanında kurulum adımları anlatılacak

---

## 13. Sık yapılan hatalar

Bu maddeler geliştirme sırasında tekrar tekrar okunmalı. Hepsi gerçek başarısızlık biçimleridir.

**Masa skorunu toplam olarak hesaplamak.** Bir kişiyi dışlanmış bırakır. Skor, en zayıf bağdır.

**Adalet kuralını atlamak.** Bazı katılımcılar hiç eşleşmez. Kalite tek başına hedef değildir.

**Bir masaya tek kişi bırakmak.** O kişi otuz dakika tek başına oturur. Ya en az iki kişi, ya boş masa.

**Check-in sonrası motoru sıfırdan çalıştırmak.** Herkesin planı değişir, kapıda kaos çıkar. Minimum değişim modu zorunludur.

**Şirket adını serbest metin olarak karşılaştırmak.** Aynı şirket farklı yazılınca kural işlemez. Şirket kimliği üzerinden karşılaştırılır.

**Katılımcıya sayısal skor göstermek.** İnsanlar not almış gibi hisseder. Sadece gerekçe gösterilir.

**Plan görünürlüğünü etkinlik durumundan okumak.** Tek kaynak plan durumudur.

**Talep hakkına sınır koymamak.** Sistem spam'e döner, en çok talep atan kazanır.

**Görünürlük kuralını sadece arayüzde uygulamak.** API doğrudan çağrıldığında veri sızar. Kural sunucu tarafında uygulanır.

**Motoru HTTP isteği içinde çalıştırmak.** İstek zaman aşımına uğrar. Arka plan işi zorunludur.

**Motora veritabanı erişimi vermek.** Test edilemez hale gelir ve projenin en değerli parçası çürür.

**Manuel editöre döndürme, çoklu seçim, geri alma eklemek.** Hiçbiri kritik değil, hepsi zaman yer. MVP dışı.

**Ortam bilgilerini koda gömmek.** Proje devredildiğinde çalışmaz. Her şey ortam değişkeninden.

**E-posta gerektiren bir akış kurmak.** MVP'de e-posta gönderimi yok. Doğrulama, şifre sıfırlama, davet gibi akışlar bu sürümde yazılmaz.
