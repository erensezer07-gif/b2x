# Kararlar

Şartnamede yazmayan, uygulama sırasında verilmiş kararlar. Her biri neden öyle
yapıldığını da söyler — ileride "burası neden böyle" diye sorulduğunda cevabı
burada olsun diye.

---

## Aşama 0 — Temel

### Docker Compose tüm sistemi ayağa kaldırır

`db`, `redis`, `api`, `worker` — dördü de compose'ta tanımlı.

Şartname Bölüm 3 "tek komutla tüm sistem çalışır durumda olmalı" diyor, Bölüm 10
Taşınabilirlik kriteri de aynı şeyi istiyor. Yalnızca veri servislerini
konteynerleştirmek bu kriteri Aşama 0'da karşılamazdı.

Günlük geliştirmede `api` konteyneri kullanılmaz: imaj bind mount içermediği için
canlı yeniden yükleme yapmaz. Geliştirirken `docker compose up -d db redis` +
makinede native `uvicorn --reload` çalışır. `api` imajı teslim ve doğrulama
içindir.

### Compose dosyası infra/ altında, kökte ince bir sarmalayıcı

Şartnamenin klasör tablosu compose dosyasını `infra/` altında gösteriyor. Ama
göreli yollar ve `.env` okuması compose'un "proje klasörü"ne göre çözüldüğü için,
`infra/` içinden çalıştırmak kökteki `.env` dosyasını görmez.

Çözüm: servis tanımları `infra/docker-compose.yml` içinde kalır, depo kökündeki
`compose.yaml` bunu `include` ile içeri alır ve proje klasörünü kök olarak
sabitler. Böylece README'deki `docker compose up -d` komutu kökten çalışır.

Sonuç olarak `infra/docker-compose.yml` içindeki göreli yollar depo kökünden
çözülür — `build.context` bu yüzden `../backend` değil `backend`.

### Backend Dockerfile'ı backend/ altında

Build context'i sadeleştirir. Şartnamenin `infra/` tanımında Dockerfile geçmiyor,
bu yüzden çelişki yok.

### Bağımlılıklar venv + pip ile

Makinede zaten kurulu olan tek araç. `pyproject.toml` bağımlılıkları listeler,
`constraints.txt` sürümleri sabitler ve imaj bunu kullanır — devirde aynı
sürümler kurulur. `uv` daha hızlı olurdu ama devralacak kişinin makinesine yeni
bir araç kurmayı gerektirirdi.

`constraints.txt` Windows'ta üretildiği için Linux'a özgü paketleri (uvloop)
içermez. Tam kilitleme gerekirse liste konteyner içinde üretilmeli.

### env.example → .env.example

README iki yerde `.env.example` diyordu, dosyanın adı `env.example` idi.
`.gitignore` içindeki `.env` kuralı `.env.example` adını yakalamaz, sorun yok.

### Gizli değerlerin varsayılanı yok

`app/config.py` içinde `POSTGRES_PASSWORD`, `JWT_SECRET`, `POSTGRES_HOST` gibi
makineye özel veya gizli alanların varsayılanı yoktur — eksikse uygulama hiç
açılmaz. Yanlış bir varsayılanla sessizce çalışmak, açılmamaktan kötüdür.

Makineden makineye değişmeyen değerlerin (`API_HOST=0.0.0.0`, standart portlar,
motor ayarları) varsayılanı vardır; doğru kaynak yine `.env` dosyasıdır.

### alembic.ini yalnızca ASCII içerir

Alembic bu dosyayı işletim sisteminin **yerel kod sayfasıyla** okur (Windows
Türkçe kurulumda cp1254, Linux'ta UTF-8). UTF-8 yazılmış Türkçe bir yorum, dosyayı
Windows'ta okunamaz hale getirdi — `UnicodeDecodeError` ile Alembic hiç açılmadı.

Bu yüzden `alembic.ini` içinde Türkçe özel karakter kullanılmaz. Kısıtlama
yalnızca bu dosyaya özeldir; diğer dosyalar UTF-8 okunur ve Türkçe serbesttir.

Aynı sebeple veritabanı adresi de bu dosyada değil, `migrations/env.py` içinde
`app.config` üzerinden ortamdan okunur.

### Motor sınırı iki katmanla korunur

Şartname Bölüm 5.1'in makine tarafından denetlenen karşılığı:

- `backend/tests/test_engine_boundary.py` — `engine/` altındaki her dosyayı AST
  ile ayrıştırır, yasaklı bir modülün import edildiğini görürse testi kırar.
  Ayrıca motorun hiçbir B2X ortam değişkeni tanımlı değilken import
  edilebildiğini alt süreçte doğrular.
- `backend/engine/.ruff.toml` — aynı listeyi `banned-api` olarak tanımlar, ihlal
  yazılırken lint uyarısı çıkar.

Asıl güvence testtir; lint yalnızca erken uyarıdır. İkisinin de gerçekten
kırıldığı, bilerek ihlal eden geçici bir dosyayla doğrulandı.

### Sağlık uçları

`/health` bağımlılıklara bakmaz, `/health/ready` veritabanı ve Redis'e gerçekten
ulaşır ve biri erişilemezse 503 döner.

Bunlar ürün özelliği değil altyapıdır: compose'un konteyneri hazır sayması ve
"sistem ayağa kalktı" iddiasının doğrulanabilmesi için gerekli.

### Worker'da bir `ping` işi var

ARQ en az bir kayıtlı iş olmadan açılmıyor — worker konteyneri sonsuz yeniden
başlama döngüsüne giriyordu.

`app/worker.py` içindeki `ping` işi `/health` ucunun kuyruk tarafındaki
karşılığıdır: ürün mantığı içermez, kuyruğun uçtan uca çalıştığını gösterir.
Aşama 7'de eşleştirme işi bunun yanına eklenecek.

### Flutter: sunucu adresinin varsayılanı yok

`AppConfig.apiBaseUrl` derleme sırasında `--dart-define=API_BASE_URL=...` ile
verilir, kodda varsayılan yoktur. Buraya bir adres yazılsaydı, tanım
unutulduğunda uygulama sessizce yanlış sunucuya giderdi. Boşsa karşılama ekranı
durumu Türkçe olarak söyler.

### Flutter: tema kararı ertelendi

Görsel kimlik şartname Bölüm 12'de açık karar olarak duruyor ("Departure Board
estetiği, ayrı bir tasarım notunda"). Bu yüzden `main.dart` içinde marka rengi
uydurulmadı, Material varsayılanı kullanıldı.

"Yükleniyor / hata / boş" bileşenleri de Aşama 3'te, veri çeken ilk ekranla
birlikte yazılacak — Aşama 0'da veri çeken ekran yok.

### Uygulama kimliği

`--org com.b2x --project-name b2x`, yani Android applicationId ve iOS bundle
kimliği `com.b2x.b2x`. Gerçek bir alan adına geçilecekse mağazaya çıkmadan önce
değiştirilmeli.

### Windows + WSL2: dağıtım boşta kapanıyor

Docker WSL2 içinde çalışıyor, geliştirme Windows tarafında. WSL dağıtımı bir süre
boşta kalınca Windows onu kapatıyor; konteynerler ve `localhost` port
yönlendirmesi de kapanıyor. Belirtisi: Windows'ta çalışan backend aniden
veritabanına bağlanamıyor.

Bu bir kod sorunu değil, ortam davranışı. Kalıcı çözüm `%USERPROFILE%\.wslconfig`
içine `[wsl2] vmIdleTimeout=-1` yazıp `wsl --shutdown` yapmak. README'de anlatıldı,
makinenin ayarı değiştirilmedi.

---

## Aşama 1 — Veri modeli

### Birincil anahtarlar bigint

Motor kendi içinde tam sayı indeks kullanıyor (şartname 9.2), dönüşüm bedelsiz
oluyor. Günlükler ve adresler okunabilir kalıyor.

Tahmin edilemez olması gereken tek kimlik katılımcının QR kodu ve o ayrı bir alan
olarak rastgele üretiliyor. Görünürlük kuralları zaten sunucuda uygulandığı için
sıralı kimlik bir açık yaratmıyor.

### Katılımcıya atıf `registrations` üzerinden

`assignments`, `meeting_requests` ve `match_reasons` doğrudan `users` değil
`registrations` referansı tutuyor. Şartname sözlüğü katılımcıyı "etkinliğe
başvurup kabul edilmiş kullanıcı" diye tanımlıyor; kaydı referans alınca "bu kişi
bu etkinliğe kayıtlı" bilgisi şemadan geliyor, ayrıca kontrol edilmesi gerekmiyor.

`meeting_requests` bunu bir adım öteye taşıyor: bileşik yabancı anahtarla talep
eden ve talep edilenin **aynı etkinlikte** olması garanti ediliyor. Bunun için
`registrations` üzerinde `(event_id, id)` benzersizliği var.

### Durum alanları metin, kısıt elle yazılıyor

Postgres'in yerel ENUM tipi kullanılmadı: ona sonradan değer eklemek migration
tarafında zahmetli.

Ama SQLAlchemy'nin kendi ürettiği CHECK kısıtı da kullanılmadı ve bunun sebebi
uygulama sırasında ortaya çıktı:

1. `Enum(native_enum=False)` varsayılan olarak **hiç kısıt üretmiyor** —
   `create_constraint` SQLAlchemy 1.4'ten beri `False`. Fark edilmeseydi durum
   sütunları denetimsiz metin olarak kalacaktı.
2. `create_constraint=True` yapılınca kısıt oluşuyor ama tabloya yalnızca DDL
   üretilirken ekleniyor, model üzerinde görünmüyor. Sonuç: `alembic
   --autogenerate` onu "modelde yok" sayıp her seferinde silmeye çalışıyordu.

Çözüm `app/models/enums.py` içindeki `status_check`: kısıt elle yazılıyor, hem
veritabanında hem modelde duruyor, autogenerate temiz kalıyor.

### Kısıt adları kurala bağlandı

`Base.metadata` bir adlandırma kuralı taşıyor. Aksi hâlde Postgres kendi adını
üretiyordu (`companies_normalized_name_key` gibi) ve o adlar migration'lara
rastgele girip geri alma işlemlerini kırılganlaştırıyordu.

Kural CheckConstraint'lere önek eklediği için modelde kısa ad veriliyor
("email_lowercase"), veritabanında tam ad oluşuyor ("ck_users_email_lowercase").

### Migration testlerde de Alembic ile kuruluyor

Kısıt testleri `Base.metadata.create_all` ile değil, `alembic upgrade head` ile
kurulmuş bir veritabanına karşı çalışıyor. Teslim edilen şey migration; modelde
olup migration'a girmemiş bir kısıt ancak böyle yakalanır.

Veritabanına ulaşılamazsa testler atlanıyor. Aşama 0'ın "pytest veritabanı
istemez" özelliği korunuyor: veritabanısız 11 test geçiyor, 22 kısıt testi
atlanıyor.

### Üretilen migration'lar biçim denetimi dışında

`ruff check` migration'larda çalışmaya devam ediyor ama `ruff format` ve satır
uzunluğu kuralı `migrations/versions/` için kapalı. Gövdeyi Alembic üretiyor;
her `alembic revision` çıktısını yeniden biçimlendirmek zorunda kalmak gereksiz
sürtünme yaratırdı.

Alembic'in `post_write_hooks` özelliği ile ruff otomatik çalıştırılabilirdi ama
ruff'ın konsol betiği (`console_scripts`) girdisi yok; `exec` kancası ise mutlak
yol ya da işletim sistemine özel yol gerektirirdi — ikisi de taşınabilirliği
bozardı.

`migrations/script.py.mako` şablonu güncel Python tipi yazımına çevrildi, böylece
üretilen dosyalar baştan lint-temiz geliyor.

### Şartnameye eklenen iki alan

`events` tablosuna Bölüm 6'da sayılmayan iki alan eklendi, çünkü şartnamenin
tarif ettiği davranış bunlar olmadan çalışmıyor:

* `auto_approve_registrations` — M4: "başvurular otomatik mi kabul edilecek yoksa
  organizatör tek tek mi onaylayacak"
* `request_quota` — M9: "varsayılan 3, organizatör değiştirebilir"

`B2X_SPEC.md` Bölüm 6 da buna göre güncellendi.

### Motor ayarları etkinlik tablosunda tutulmuyor

`env.example` "bu değerler etkinlik bazında da ayarlanabilir" diyor ama Bölüm 6
böyle bir alan listelemiyor. Şartnameye sadık kalındı: ayarlar ortam
değişkeninden geliyor, kullanılan tohum değeri `plans.seed` içinde saklanıyor —
determinizm için yeterli. Etkinlik başına ayar istenirse önce şartnameye yazılmalı.

### Şemaya konmayan tek kural

Masa ile alan bloğunun aynı ızgara hücresini paylaşmaması. İki ayrı tabloyu
kapsadığı için tek bir benzersiz indeksle ifade edilemiyor; Aşama 5'te uygulama
katmanında kontrol edilecek.

---

## Aşama 2 — Eşleştirme motoru (Tur 1-2)

### "Görüşme" birimi tur

Adalet kuralındaki (9.6) "en az N görüşme" **oturulan slot sayısı** olarak
sayılıyor, tanışılan kişi sayısı olarak değil. 9.6'daki başarısızlık hikâyesi
slot sayıyor: "çoğunluk sekiz slotun sekizinde dolu, azınlık sekiz slotun
birinde". Bu okumayla varsayılan 4 anlamlı bir eşik oluyor; kişi bazında sayılsa
tek bir masa yeterdi ve kural neredeyse hiç devreye girmezdi.

### Amaç fonksiyonu

```
amaç = adalet_ağırlığı × Σ min(oturulan_tur, hedef)
     + Σ (masa_skoru − eşik_cezası × eşiğin_altında_kalan)
     − taşıma_cezası × yeri_değişen_yerleşim
```

`min(x, hedef)` tavanı kilit nokta: hedefin altındaki birini bir tur daha
oturtmak puan kazandırır, hedefi tutturmuş birini oturtmak kazandırmaz. Arama
böylece 9.6'nın istediği gibi "en kötü durumdaki kişiye" yönelir. Saf "en kötüyü
maksimize et" düz platolar üretir ve yerel arama takılırdı.

### Eşik cezası — sonradan eklendi

İlk hâlde amaç fonksiyonu **boş masa ile kötü masayı aynı görüyordu**: ikisi de
0 puan. Yerel arama iki uyumsuz kişiyi oturtmayı bedelsiz sanıyor, masaların
dörtte birinde en zayıf bağ 0.000 çıkıyordu.

9.5 kalite eşiğini "skorla yönetilen esnek kural" diye tarif ediyor — kesin yasak
değil ama tercih edilmeyen. Eşiğin altında kalan masaya eksik puan başına ceza
eklendi. 20.000 denemede ortalama masa skoru 0.358'den 0.489'a çıktı.

### Tek yönlü eşleşme iki kez cezalanıyordu

Arz-talep terimi önce `(ileri+geri)/2` ile ortalama alıp bir de `(1+bonus)`'a
bölüyordu. Sonuç: "tam aradığın şeyi sunuyorum, üç etikette birden" diyen bir
ikili 0.216 alıyor ve 0.35 eşiğini geçemiyordu. Bölme yerine 1'e kırpmaya
geçildi; çift yönlünün üstünlüğü korunuyor (testler doğruluyor), tek yönlü 0.345.

### Yerel arama boş masaya taşıyamaz

Şartname üç hamle sayıyor (takas, taşıma, çıkarma). Taşıma hamlesi boş masaya
izin verince tek kişilik masa oluşuyordu — kesin kural ihlali (9.5).

Bunu amaç fonksiyonu göremiyordu: tek kişilik masa "kullanılmıyor" sayıldığı için
0 puan alıyor, oturan kişi ise adalet teriminden +2 kazanıyordu. Arama insanları
boş masalara yalnız park edip adalet skorunu şişiriyor, plan sonunda
temizlenince o kişiler hedefin altına düşüyordu. 200 kişilik senaryoda 9 tek
kişilik masa ve sonrasında 2 mağdur kişi.

Yeni masa açmak artık yalnızca açgözlü başlangıcın (Adım 3) ve adalet
düzeltmesinin (Adım 5) işi; ikisi de masayı en az iki kişiyle açar.

### Taşıma hamlesinin kapsamı

"Bir kişiyi başka masaya taşı" hamlesi, kaynağın *hiçbir masa olmaması* durumunu
da kapsıyor — yani oturmayan birini oturtmak da bir taşıma. Bu olmadan açgözlü
aşamada yer bulamamış kimse bir daha asla oturamaz, adalet kuralı yerel aramadan
hiç fayda göremezdi.

### Masa skoru kesin min kaldı

9.4 katı gelirse "en düşük dilimin ortalaması" seçeneğine izin veriyor. İkisi aynı
senaryoda ölçüldü:

| Ölçüt | Kesin min | En düşük dilim ort. |
|---|---|---|
| Ortalama masa doluluğu | 2.23 | 2.23 |
| Masadaki en zayıf bağın en kötüsü | 0.36 | **0.11** |

Esnetme doluluğa hiçbir şey katmıyor ama masaya 0.11'lik bir bağ sokuyor —
9.4'ün uyardığı "yarım saat dışlanmış oturan dördüncü kişi" tam olarak bu.

### Sentetik üreteç kümelenmiş etiket dağıtıyor

İlk hâl etiketleri havuzdan düzgün dağıtıyordu; gerçek katılımcılar ilgi
alanlarına göre kümelenir (fintech'çi "ödeme altyapısı" sunar, "bankacılık
ortaklığı" arar). Rastgele dağıtım motoru olduğundan kötü gösteriyordu — ilk
ölçek denemesinde 71 kişi hiç oturamamıştı. İlgi alanı kümelemesi eklenince aynı
senaryoda atama 184'ten 894'e çıktı.

### Yerel aramanın katkısı bu senaryoda sınırlı

Ölçek denemesinde skor matrisindeki 19.900 ikiliden yalnızca 1519'u eşiği
geçiyor, plan ise ~950 tanışma istiyor. Açgözlü başlangıç iyi ikililerin çoğunu
zaten tüketiyor, geriye yerel aramaya az alan kalıyor (100.000 denemede ~20
iyileşme). Adalet düzeltmesi asıl işi yapıyor: hedefin altındaki 45 kişiyi 0'a
indiriyor.

Başlangıç sıcaklığı 0.6'dan 6.0'a kadar denendi, fark yaratmadı — engel sıcaklık
değil, iyi ikili kıtlığı.

Aramaya daha fazla alan açmanın yolu **iki kişilik bir masayı bütün hâlde başka
masaya taşıyan bileşik bir hamle** olurdu; şartnamenin saydığı üç hamlenin
dışına çıkar, bu yüzden yapılmadı. Gerekirse önce şartnameye yazılmalı.

---

## Aşama 2 — Minimum değişim modu (Tur 3)

### Gelmeyenler listeden silinmiyor, işaretleniyor

`EngineInput.absent_participants` eklendi. Katılımcı listesinden çıkarmak
indeksleri kaydırırdı ve `previous_plan` içindeki referanslar başka kişilere
işaret ederdi — motor indeks tabanlı çalışıyor (9.2).

Gelmeyenler `can_seat` içinde eleniyor, ayrıca özet raporunda "eşleştirilemedi"
sayılmıyorlar: etkinliğe katılmadılar, motor onları yerleştiremediği için değil.

### Dondurulmuş slotlar geçmişin kaydı

Başlamış veya bitmiş slotlar önceki plandan olduğu gibi alınıyor ve hiç
değiştirilmiyor — **gelmeyenler bile çıkarılmıyor**. O turlar gerçekten yaşandı;
kaydı sonradan düzenlemek geçmişi değiştirmek olurdu. Kural kontrolü de
yapılmıyor, çünkü geçmiş zaten olmuş bitmiş.

`frozen_slots` dolu ama `previous_plan` boşsa girdi reddediliyor: neyin
dondurulacağı ancak önceki plandan bilinebilir.

### Ölçülen fayda

Yüz kişilik plandan on kişi çıkarıldığında (9.10'un minimum değişim testi):

| Yol | Yeri değişen (gelmeyenler hariç) | Atama |
|---|---|---|
| Sıfırdan çalıştırma | **90 / 90** | 421 |
| Minimum değişim modu | **11 / 90** | 389 |

Sıfırdan çalıştırma tam olarak 9.8'in uyardığı sonucu veriyor: herkesin planı
değişiyor. Minimum değişim modu 32 atama feda edip 79 kişiyi yerinde bırakıyor —
şartnamenin istediği takas bu.

### Adım 5 bu modda da çalışıyor

Şartname 9.8 adalet düzeltmesini atlamayı söylemiyor. Gelmeyenler delik açınca
kalanlar hedefin altına düşebiliyor; düzeltme yalnızca **yeni oturma ekliyor**,
kimseyi taşımıyor, dolayısıyla minimum değişim amacıyla çelişmiyor.

---

## Aşama 3 — Kimlik ve profil (Tur 1: backend)

### Şifre özetleme Argon2id

M1 "modern bir özetleme algoritması" diyor; Argon2id parola özetleme yarışmasının
kazananı ve OWASP'ın ilk önerisi. Tuz özetin içinde taşınıyor, ayrı sütun yok.

Giriş sırasında `check_needs_rehash` çalışıyor: parametreler ileride
sertleştirilirse kullanıcının özeti bir sonraki girişinde sessizce yenileniyor.

### Jetonlar durumsuz, çıkış ucu yok

Sunucuda oturum kaydı tutulmuyor. Çıkış, istemcinin jetonu güvenli depodan
silmesiyle oluyor. İş yapmayan bir `/auth/logout` ucu, sunucunun oturumu
gerçekten sonlandırdığı izlenimi verirdi — yanıltıcı olurdu.

Sınır açıkça kabul ediliyor: **çalınmış bir yenileme jetonu süresi dolana kadar
geçerli kalır.** MVP'de e-posta altyapısı ve dolayısıyla hesap kurtarma akışı yok,
ortam kontrollü. İptal gerekirse `jti` iddiası hazır; bir kara liste tablosu
eklemek yeterli.

Erişim ve yenileme jetonu aynı anahtarla imzalandığı için `type` iddiası zorunlu.
Kontrol olmasaydı uzun ömürlü yenileme jetonu korumalı uçlara girerdi — test
altında.

### Giriş hatası ayrıntı vermiyor

"Böyle bir e-posta yok" ile "şifre yanlış" ayrı yanıtlar verseydi, kimlerin
kayıtlı olduğu dışarıdan öğrenilebilirdi. İkisi de aynı 401'i döndürüyor ve bir
test bunu kilitliyor.

### Kayıt doğrudan oturum açıyor

Bölüm 10: *"Kayıt olan kullanıcı doğrudan giriş yapabiliyor."* Ayrı bir giriş
adımı istenmediği için `/auth/register` jetonları doğrudan döndürüyor. Profil
kaydı da aynı anda açılıyor ki sihirbaz ilk adımdan itibaren kaydedebilsin.

### Nokta kelime ayracı değil, kısaltma işareti

Şirket normalleştirmesinde yakalanan hata: `"A.Ş."` noktalarda bölününce `"a"` ve
`"s"` oluyor, tüzel kişilik eki listesindeki `"as"` ile eşleşmiyordu. Sonuç
`"abc yazilim a s"` — yani `"ABC Yazılım A.Ş."` ile `"ABC Yazılım"` **ayrı şirket
sayılıyordu**, şartnamenin tam da uyardığı hata.

Nokta ve kesme işareti artık ayraç değil, tamamen siliniyor. Diğer noktalama
(tire, `&`) ayraç olmaya devam ediyor.

### Fazla normalleştirme mi, eksik mi

İki yönün zararı simetrik değil:

- **Fazla**: iki ayrı şirket birleşir, farklı şirketlerden iki kişi aynı masaya
  oturamaz — gereksiz kısıt.
- **Eksik**: aynı şirket ikiye bölünür, kural sessizce işlemez, iki iş arkadaşı
  aynı masaya oturur — şartnamenin asıl korktuğu.

Bu yüzden yalnızca tüzel kişilik biçimleri atılıyor (`A.Ş.`, `Ltd. Şti.`,
`San. ve Tic.`). "Holding" ve "Grup" bırakılıyor: onlar gerçekten şirket ayırt
edebiliyor.

### Kısmi güncellemede "gönderilmedi" ile "null" farklı

Sihirbaz her adımı ayrı kaydediyor. Gönderilmeyen alan değişmiyor, açıkça `null`
gönderilen alan temizleniyor. Pydantic'in `exclude_unset` bilgisi ikisini
ayırıyor; ayırmasaydı tek bir adımı kaydetmek diğer adımların verisini silerdi.

### `populate_existing` olmadan güncelleme görünmüyordu

Profil güncellendikten sonra yanıt hazırlanırken profil yeniden sorgulanıyor.
SQLAlchemy kimlik haritasındaki nesneyi olduğu gibi döndürüp zaten yüklenmiş
ilişkileri tazelemiyor: `company_id` değişse bile `company` eski hâliyle (None)
kalıyordu. Sorguya `populate_existing` eklendi.

### Tamamlanma yüzdesi ile başvuru yeterliliği ayrı

**Tamamlanma** dokuz kalem üzerinden hesaplanıyor ve yalnızca bilgilendiriyor.
**Başvuru yeterliliği** beş zorunlu alana bakıyor ve eksikleri listeliyor (M2).
Web sitesi ve LinkedIn tamamlanmaya girmiyor: şartname onları "isteğe bağlı"
sayıyor, girselerdi eksiksiz bir profil bile %100 görünmezdi.

Eksik alanlar İngilizce anahtar olarak dönüyor (`full_name`, `company`, ...);
Türkçe cümleyi arayüz kuruyor. Motorun gerekçe kırılımındaki ayrımın aynısı —
sunucu kullanıcı metni üretmiyor.

### Etiket ve sektör içeriği migration'da

Bölüm 12 bu içeriği açık karar bırakmıştı. 6 kategori × 8 etiket ve 18 sektör
`0002` migration'ı ile yükleniyor. Havuz boş olsaydı sihirbazın iki adımı hiç
çalışmaz, dolayısıyla eşleştirmenin girdisi de oluşmazdı. Liste **başlangıç
setidir**, gerçek etkinlik verisiyle ayarlanacak; spec'teki açık karar buna göre
işaretlendi.

### Ayrılmış alan adları e-posta doğrulamasına takılıyor

`@ornek.test` ve `@b2x.local` gibi adresler `email-validator` tarafından
reddediliyor (ayrılmış üst düzey alan adları). Test verisi bu yüzden gerçek
görünümlü bir alan adı kullanıyor. MVP'de e-posta **gönderilmediği** için
(Bölüm 2) bunun bir yan etkisi yok — adres yalnızca giriş kimliği.

---

## Aşama 3 — Kimlik ve profil (Tur 2: Flutter)

### Tema tek dosyada, palet henüz nötr

`app/lib/core/theme/app_theme.dart` renk, tipografi ve aralık ölçeğinin tek
kaynağı. Hiçbir ekranda çıplak renk veya sayı yazılmıyor.

Bölüm 12 görsel kimliği ("Departure Board estetiği") açık karar bırakmıştı;
erteleme ertelenmiş kaldı. Marka rengi uydurmak sonradan verilecek kararı
zorlaştırırdı. Karar geldiğinde değişecek tek yer `_seedColor` ve ölçekler.

### Üç durum bileşenleri baştan yazıldı

`LoadingView`, `ErrorView`, `EmptyView` — Bölüm 0: *"Bunlar sonradan eklenmez,
ekranla birlikte yazılır."* Tek yerde durmalarının somut faydası hata
durumundaki "tekrar dene" düğmesi: her ekran aynı davranışı paylaşıyor,
kullanıcı çıkmaz bir ekranda kalmıyor.

### Sessiz yenileme tek seferlik

401 alan istek, yenileme jetonuyla tazelenip **aynı istek tekrarlanıyor**;
kullanıcı hiçbir şey görmüyor (M1, Bölüm 10).

Eşzamanlı isteklerin hepsi aynı anda 401 alabilir. Yenileme `_refreshInFlight`
ile tek seferlik tutuluyor: ilk istek başlatır, diğerleri aynı sonucu bekler.
Olmasaydı her istek ayrı bir yenileme tetikler ve sunucuya gereksiz yük binerdi.

Yenileme isteği **kendi Dio örneğiyle** gidiyor. Araya girici ona da takılsaydı,
yenileme 401 aldığında kendini tekrar çağırır ve sonsuz döngüye girerdi.

### Form hatası paylaşılan duruma yazılmıyor

`AuthController.login/register` hatayı **fırlatıyor**, `AsyncValue.guard` ile
duruma yazmıyor. Sebep yönlendirme: paylaşılan durum "hata" olsaydı, yönlendirme
onu görüp kullanıcıyı başka sayfaya atardı ve hata hiç okunmazdı. Formun kendi
hatası formun kendi state'inde kalıyor.

Aynı sebeple "yükleniyor" da yerel: giriş denemesi sırasında kullanıcı açılış
ekranına düşmemeli.

### Açılış ekranı gerekli

`SignedOut` ile "henüz bilmiyoruz" ayrı tutuluyor. Güvenli depo okunana kadar
yönlendirme hiçbir yere göndermiyor; olmasaydı oturumu açık bir kullanıcı her
açılışta bir an giriş ekranını görürdü.

### Riverpod 3 farkları

`AsyncValue.copyWithPrevious` artık paket dışına kapalı (`invalid_use_of_internal_member`)
ve `valueOrNull` kaldırılmış. İkisinin yerine `asData?.value` kullanılıyor.

### `prefer_initializing_formals` kapatıldı

Kural `this._alan` biçiminde atama öneriyor ama Dart'ta alt çizgiyle başlayan ad
adlandırılmış parametre olamaz. Özel alanı adlandırılmış parametreden kurmanın
tek yolu gövdede atama — kural bizim yapımızda uyulamaz durumda.

### Pydantic doğrulama mesajları çevriliyor

Sunucu doğrulama hatalarını İngilizce döndürüyor ("value is not a valid email
address"). Arayüz dili Türkçe olmak zorunda (Bölüm 0), bu yüzden `ApiException`
tanıdığı mesajları çeviriyor; tanımadıklarını olduğu gibi geçirmiyor, genel bir
Türkçe cümleye düşürüyor. Kullanıcı hiçbir durumda İngilizce uyarı görmemeli.

### Web'de güvenli depo sınırlı

`flutter_secure_storage` Android'de Keystore, iOS'ta Keychain kullanıyor. Web'de
tarayıcının sunduğu koruma sınırlı — orada gerçek bir güvenli alan yok. MVP'de
web yalnızca geliştirme ve demo için derleniyor, üretim hedefi mobil (Bölüm 3).

---

## Aşama 3 — Kimlik ve profil (Tur 3: sihirbaz)

### Depolama arayüzü: anahtar saklanır, adres üretilir

Şartname Bölüm 3: *"arada bir depolama arayüzü olur (yükle, sil, adres al)"*.
`app/services/storage.py` soyut `Storage` sınıfını ve yerel disk uygulamasını
taşıyor; S3'e geçmek için yeni bir sınıf yazıp `_build_storage` eşlemesine
eklemek yeterli.

Veritabanında **anahtar** saklanıyor (`profiles.photo_key`), adres değil. Adres
depolama arka ucuna ve ortama göre değişir; kaydedilmiş bir adres sunucu
taşındığında kırılırdı. Yanıtta ise anahtar değil kullanılabilir adres dönüyor —
istemcinin adres kurma kuralını bilmesi gerekmiyor.

### Dosya adı hiç kullanılmıyor

Yüklenen dosyanın adı iki risk taşıyor: yol kaçışı (`../`) ve başkasının
dosyasının adresini tahmin etme. Ad tamamen atılıyor, yerine rastgele bir
belirteç konuyor. Ayrıca `_resolve` kök dışına çıkan anahtarları reddediyor —
veritabanından bozuk bir değer gelse bile kök dışında dosya silinemez.

SVG kabul edilmiyor: içine betik gömülebilir.

### Eski fotoğraf yenisi kaydedildikten sonra siliniyor

Ters sırada olsaydı yükleme yarıda kaldığında kullanıcı hem eski hem yeni
fotoğrafından olurdu. Silme başarısız olursa istek düşmüyor: kullanıcının işlemi
tamamlandı, diskte kalan artık dosya yüzünden hata göstermek yanlış olurdu.

### Depolama bağımlılık olarak veriliyor

İlk denemede test, `app.services.storage.get_storage`'ı modül seviyesinde
yamalıyordu ve **çalışmadı**: uçlar `from ... import get_storage` ile fonksiyonu
kendi ad alanlarına kopyalamıştı, modülü değiştirmek onları etkilemedi. Dosya
gerçek `./storage` klasörüne yazılıyordu.

`StorageDep` bağımlılığı eklendi (mevcut `SessionDep` kalıbıyla aynı). Testler
`dependency_overrides` ile geçici klasöre yönlendiriyor — hem doğru çalışıyor hem
uçlar somut sınıfı değil sözleşmeyi görüyor.

### FormData sessiz yenilemede klonlanıyor

`FormData` bir akış: ilk gönderimde tüketiliyor. Erişim jetonu dolup istek
tekrarlandığında olduğu gibi gönderilseydi sunucuya boş gövde giderdi. Araya
girici yeniden denemeden önce klonluyor, böylece fotoğraf yükleme de sessiz
yenilemeden faydalanıyor.

### Sihirbaz durumu sunucuda, istemcide değil

Her adım kendi verisini kaydediyor; "ileri" kaydetmeden geçmiyor. Uygulama
kapansa bile ilerleme kaybolmuyor (M2: *"kullanıcı yarıda bırakıp sonra devam
edebilir"*).

Sihirbaz açılışta **ilk eksik adıma** atlıyor: profil doluysa son adımda açılıyor
ve oradan özete geçiliyor. Kaldığı yeri istemcide saklamak gerekmiyor, profilin
kendisi zaten söylüyor.

### İki etiket adımı tek bileşen

"Ne sunuyorum" ve "ne arıyorum" aynı `TagsStep` bileşenini kullanıyor, yalnızca
`direction` farklı. Sebep şartname Bölüm 6: iki liste **aynı havuzdan** seçiliyor.
Ayrı bileşenler yazmak, iki havuzun zamanla ayrışmasına kapı açardı.

### Eksik alan etiketleri istemcide

Sunucu İngilizce anahtar döndürüyor (`full_name`, `offered_tags`); Türkçe cümleyi
`ProfileRequirement` enum'u kuruyor. Tanınmayan anahtar `unknown`'a düşüyor —
sunucu ileride yeni bir zorunluluk eklerse eski istemci çökmüyor.

---

## Aşama 4 — Etkinlik oluşturma ve otomatik salon düzeni

### Program saklanmıyor, hesaplanıyor

Ayrı bir `slots` tablosu yok (Aşama 1'de de kurulmamıştı). Başlangıç saati, slot
süresi, mola süresi ve slot sayısından türetilebilen bir şeyi kaydetmek, alanlar
değiştiğinde iki kaynağın ayrışması demekti.

**Son slottan sonra mola yok:** etkinlik son görüşme biter bitmez biter. Molayı
da saymak toplam süreyi bir mola kadar uzun gösterirdi. Testle kilitli.

### Aynı formül iki dilde

`app/services/schedule.py` ve `app/lib/features/events/schedule.dart` aynı hesabı
yapıyor. Sebep: M4 *"girildikçe anlık gösterilir"* istiyor, her tuş vuruşunda
sunucuya gitmek anlamsız olurdu. Sunucu yine de tek doğruluk kaynağı — kaydedilen
etkinliğin programı oradan geliyor.

Ayrışma riskini kapatmak için **aynı senaryolar iki tarafta da test ediliyor**
(`test_schedule.py` ve `schedule_test.dart`): şartnamenin örneği, 8 turluk ölçek,
gece yarısını aşan program, sıfır mola, tek slot.

### `PUT .../layout/auto` — yerine koyuyor, eklemiyor

Organizatör masa sayısını değiştirdiğinde eski masalar silinip yenileri
kuruluyor. `POST` olsaydı her denemede masa birikirdi.

**Plan üretilmişse kilitleniyor:** atamalar masa kimliğine bağlı, masaları silmek
planı bozardı. Hem yeniden kurma hem tek masa düzenleme 409 dönüyor.

### Başkasının etkinliğine 404, 403 değil

`get_owned_event` bağımlılığı sahipliği doğruluyor. 403 "böyle bir etkinlik var
ama giremezsin" bilgisini sızdırırdı; kimlik taranarak hangi etkinliklerin var
olduğu öğrenilememeli (Bölüm 7).

Ayrı bir yetki katmanı yok — rol etkinliğe göre belirleniyor, kontrol her uçta
sahiplikle yapılıyor.

### Kapasite uyarısı engel değil, kayıt açma kapısı engel

İkisi bilerek farklı davranıyor (M4):

* **Kapasite uyarısı** — kontenjan salondan büyükse bayrak kalkıyor ama hiçbir
  şeyi durdurmuyor. Organizatör gelmeyecekleri hesaba katıyor olabilir.
* **Kayıtları açma** — salon düzeni yoksa uç 409 döndürüyor. Bu gerçek bir kapı
  (Bölüm 10 kabul kriteri).

### Riverpod 3'te aile notifier'ı yok

`FamilyAsyncNotifier` kaldırılmış ve `AsyncNotifierProvider.family` argümansız
bir kurucu bekliyor; notifier argümanına erişemiyor.

Onun yerine `FutureProvider.family` + `EventActions` sınıfı kullanıldı: depoyu
sarmalayıp değişiklikten sonra ilgili sağlayıcıları tazeliyor. Daha az API
yüzeyi, aynı davranış, sürüm değişikliklerine daha az bağımlı.

### `invalidate` tek başına yetmiyor

Sihirbazdan listeye dönüldüğünde kart bayat veri gösteriyordu: adı "Yeni
etkinlik", durumu "Taslak" — oysa sunucuda "Fintech Zirvesi 2026" ve "Kayıtlar
açık" yazıyordu. Sayfa yenilenince doğru geliyordu, yani sunucu değil istemci
önbelleği sorunluydu.

Sebep: `invalidate` yeniden hesaplamayı **asenkron** başlatıyor. Çağıran hemen
gezinirse ekran eski veriyle açılıyor. Çözüm `invalidate` + `read(...future)`:
yeni değer beklendikten sonra ilerleniyor.

### Kapak görseli aynı depolama arayüzünden

Aşama 3'te kurulan `Storage` sözleşmesi (Bölüm 3) olduğu gibi kullanıldı; tek
fark klasör adı (`event-covers`). Yeni bir kod yolu açılmadı — bulut depolamaya
geçiş hâlâ tek dosya değişikliği.

---

## Aşama 5 — Manuel salon editörü

### Varsayılan ızgara 24×16 hücre, hücre 64 piksel

Şartname Bölüm 12'de açık bırakılmıştı, burada kapandı.

Salonlar genelde dikdörtgen; yatay oran gerçek bir fuar alanına benziyor. 384
hücre şartnamedeki 50 masalık ölçeğe (9.9) bol geliyor — masaların arasında
yürünecek boşluk kalıyor. 64 piksel dokunma hedefi için rahat, parmakla
sürüklerken masa parmağın altında kaybolmuyor.

Sınırlar 2 ile 60 arasında. Alt sınır bir masayla bir alan bloğunun yan yana
sığacağı en küçük tuval; üst sınır 3600 hücre — ötesi salon değil, kaybolunacak
bir tuval.

**Piksel ölçüsü sunucuya hiç gitmiyor.** Sunucu hücre koordinatı biliyor,
hücrenin kaç piksel çizileceği çizim kararı — istemcide duruyor.

### Otomatik moddan manuel moda geçerken masalar korunuyor

`PUT .../layout/manual` mevcut masaları silmiyor: numara ve kapasite aynı
kalıyor, yalnızca ızgara konumu atanıyor (satır satır, soldan sağa). Organizatör
25 masayı yeniden kurmasın, sürükleyerek düzeltsin.

Aynı uç ızgarayı yeniden boyutlandırmak için de çağrılıyor. O durumda yerleşik
masalara dokunulmuyor — `plan_row_placements` yalnızca **konumu olmayan**
masalara yer buluyor.

**Küçültme dışarıda öğe bırakacaksa reddediliyor.** Sığmayan masaların
numaraları hata mesajında yazıyor. Sessizce silmek organizatörün emeğini yok
etmek olurdu.

### Hücre çakışması uçta kontrol ediliyor, indeks arkada bekçi kalıyor

Masa↔masa çakışmasını veritabanı `uq_tables_layout_cell` ile zaten engelliyordu
(Aşama 1). Yine de uçta önden kontrol var: numara çakışması da aynı
`IntegrityError`'a düşüyor, ikisi ayırt edilemeden organizatöre yanlış mesaj
giderdi. Şimdi mesaj hangi masayla çakışıldığını söylüyor.

Masa↔alan bloğu çakışması **yalnızca** burada. Aşama 1'de not düşülmüştü: *"İki
ayrı tabloyu kapsadığı için tek bir benzersiz indeksle ifade edilemiyor; Aşama
5'te uygulama katmanında kontrol edilecek."* `app/services/layout.py` içindeki
`find_cell_conflict()` tek yeri; masa ve alan bloğu uçlarının hepsi oradan
geçiyor. İkisi de `Placement` dikdörtgenine indirgeniyor — masa 1×1, alan bloğu
`width × height` — böylece kesişim tek yerde yazılıyor.

### Yerleştirme önce planlanıyor, sonra uygulanıyor

`plan_row_placements()` masaları taşımıyor, taşınacakları listeliyor. Yer
yetmezse `None` dönüyor ve hiçbir şey değişmemiş oluyor. Doğrudan atasaydı yer
yarıda bittiğinde düzen yarı taşınmış hâlde kalırdı.

### Manuel moddan otomatiğe dönerken ızgara temizleniyor

`create_auto_layout` eskiden yalnızca `layout.mode` atıyordu. Manuel modda
`grid_width`/`grid_height` dolu olduğu için `grid_matches_mode` CHECK'i patlar,
uç 500 dönerdi. Aşama 4'te ulaşılamayan bir yoldu — manuel mod hiç
kurulamıyordu — Aşama 5'te gerçek oldu.

Şimdi otomatiğe geçerken ızgara alanları boşaltılıyor ve alan blokları
siliniyor: o modda görsel kroki yok (M5), blokların yeri kalmaz. Bir test
geçişi kilitliyor.

### Alan bloğunun tipi yok, yalnızca etiketi var

Şartname *"Sadece metin etiketi ve konum"* diyor. Sahne / giriş / büfe / kayıt
masası bir sayım gibi görünüyor ama şema alanı yapılmadı: arayüz bunları hazır
etiket önerisi olarak sunuyor, organizatör istediğini yazabiliyor. Enum yapmak
şartnamede olmayan bir kısıt getirirdi.

### Editör sihirbazın içinde değil, ayrı tam ekran

Tuval, araç çubuğu ve paneller sihirbazın dar sütununa sığmıyor. Salon adımı
mod seçimini ve bir "Salonu düzenle" düğmesini tutuyor; editör
`/etkinlikler/:id/salon` rotasında açılıyor.

**Manuel moda geçiş kendiliğinden olmuyor.** Mod düğmesine basmak yalnızca
kartı değiştiriyor; sunucuya istek "Manuel düzeni kur" düğmesiyle gidiyor ve
kart öncesinde kaç masanın korunacağını yazıyor. Sekme değiştirir gibi basılan
bir düğmenin veri değiştirmesi sürpriz olurdu.

**Editörden çıkarken etkinlik tazeleniyor.** Masa sayısı değişmişse kapasite
özeti ve "kayıtlar açılabilir mi" bilgisi de değişti; Aşama 4'teki
`invalidate` + `read(...future)` kalıbı burada da geçerli.

### Düzenin doğrusu hep sunucudan geliyor

Editör iyimser güncelleme yapmıyor: her hamle sunucuya gidiyor ve ekran dönen
düzenle yenileniyor. Reddedilen bir hamle böylece "geri alınmış" olmuyor, hiç
uygulanmamış oluyor — arayüzde bir an bile yanlış bir düzen görünmüyor.

Sürükleme sırasında konum yerelde tutuluyor, yalnızca bırakınca istek atılıyor.
Sürükleme boyunca istek atmak hem gereksiz hem de her ara konumda çakışma
uyarısı verirdi.

### Bekleyen otomatik kayıtlar birikiyor, birbirini ezmiyor

İlk yazımda panelin zamanlayıcısı tek bir gönderim tutuyordu; yeni değişiklik
bekleyeni değiştiriyordu. Sandalye sayısını artırıp hemen etiket yazınca
sandalye kaydı sessizce kayboluyordu — tarayıcıda yakalandı, testler
görmemişti.

Şimdi değişiklikler bir sözlükte birikiyor ve duraklama sonunda tek istekte
gidiyor. Şartname *"organizatör 'kaydet' aramak zorunda kalmaz"* diyor;
kaydetmediği için veri kaybetmesi bunun tersi olurdu. Dört test kilitliyor.

**Panel kapanırken bekleyen değişiklik `_send`'ten geçmiyor.** O yol ekranı
güncellemeye çalışıyor, oysa ekran kapanıyor: `dispose` içinde `setState`
çağrısı gönderimi hiç başlatmadan patlıyordu. Kapanışta biriken sözlük alınıp
doğrudan gönderiliyor.

### Kaydetme göstergesi yalnızca kaydederken kuruluyor

Saydamlığı sıfırlanmış bir `CircularProgressIndicator` görünmese de tik atmaya
devam ediyor: hem boşuna kare üretiyor hem de `pumpAndSettle` hiç
durulmadığı için panel testleri yazılamıyordu.
