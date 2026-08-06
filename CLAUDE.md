# B2X

B2B etkinlik eşleştirme ve oturma planlama platformu. Katılımcı profillerine bakıp her slot için kimin hangi masada oturacağını hesaplar.

## Önce bunu oku

**`B2X_SPEC.md`** projenin tek referansıdır. Bir modüle başlamadan ilgili bölümü oku.

## Değişmez kurallar

**Önce plan, sonra kod.** Ne yapılacağı yazılır, onay alınır, sonra kod yazılır. Büyük dosyalar tek seferde üretilmez.

**Şartnamenin dışına çıkma.** Spec'te tarif edilmemiş bir özellik kendiliğinden eklenmez. "Bunu da eklesek iyi olur" diye düşünülen şeyler önce konuşulur, önce spec'e yazılır.

**Motor sınırı.** `backend/engine/` klasörü FastAPI, SQLAlchemy, veritabanı veya HTTP bilmez. Sadece standart kütüphane ve NumPy. Bu klasörde `from fastapi` veya `from sqlalchemy` geçemez.

**Sabit değer yok.** Sunucu adresi, veritabanı bilgisi, anahtarlar, portlar — hepsi ortam değişkeninden. Kodda `localhost` geçmez. Proje başka bir makineye devredilecek, tek satır değişmeden çalışmalı.

**Her ekranda üç durum.** Yükleniyor, hata, boş. Sonradan eklenmez, ekranla birlikte yazılır.

**Motor değişikliği testsiz kabul edilmez.** `backend/engine/` altında değişiklik yapıldıysa testler çalıştırılır ve geçtiği görülür.

**Türkçe arayüz, İngilizce kod.** Kullanıcının gördüğü metinler Türkçe. Değişken, fonksiyon, tablo, sütun adları İngilizce.

**Görünürlük kuralları sunucuda uygulanır.** Katılımcı başka masadaki kişilerin bilgisine erişemez. Arayüzde gizlemek yeterli değil, API doğrudan çağrıldığında da veri dönmemeli.

**E-posta gerektiren akış yazılmaz.** MVP'de e-posta gönderimi yok. Doğrulama, şifre sıfırlama, davet bu sürümde yok.

## Terim uyarısı

İki ayrı numaralandırma var, karıştırma:

- **Aşama** = projenin yapım sırası (spec Bölüm 11, 0-12)
- **Adım** = eşleştirme algoritmasının iç sırası (spec Bölüm 9.7, 1-6)

## Ortam

- Windows 11, geliştirme Windows tarafında
- Postgres ve Redis WSL2 içindeki Docker'da çalışır
- Python 3.13, Flutter 3.44 (stable), Dart 3.12
- Hedef platformlar: Android ve Web. iOS kodu yazılır ama derlenmez (Mac yok)

## Klasörler

```
backend/app/     FastAPI uygulaması, API, veritabanı
backend/engine/  Eşleştirme motoru — izole
app/             Flutter
infra/           docker compose
docs/            notlar, kararlar
```

## Şu anki durum

**Aşama 0 bitti.** Docker Compose dört servisi ayağa kaldırıyor (db, redis, api, worker), motor sınırı testle korunuyor, Flutter iskeleti derleniyor.

**Aşama 1 bitti.** Spec Bölüm 6'daki 16 tablo `backend/app/models/` altında, tek migration'da (`0001_veri_modeli`). Plan versiyonlama baştan kuruldu: bir etkinlikte aynı anda en fazla bir plan yayında olabilir, bu koşullu benzersiz indeksle zorlanıyor. 22 kısıt testi şemanın gerçekten koruduğunu kanıtlıyor.

**Aşama 2 bitti — eşleştirme motoru çalışıyor.** Spec Bölüm 9'un tamamı: Adım 1-6, minimum değişim modu (9.8) ve 9.10'daki test setinin tamamı. `backend/engine/` yalnızca standart kütüphane ve NumPy kullanıyor.

200 katılımcı / 8 tur / 50 masa ölçeğinde ~5 saniye, kesin kural ihlali yok, herkes asgari tur hedefini tutturuyor. Check-in sonrası yeniden çalıştırmada 100 kişilik plandan 10 kişi çıkınca kalan 90 kişiden yalnızca 11'inin yeri değişiyor (sıfırdan çalıştırma 90'ını da değiştirirdi).

**Aşama 3 bitti — kimlik ve profil çalışıyor.**

*Backend:* Argon2id şifre özetleme, erişim/yenileme jetonları, kayıt-giriş-tazeleme uçları, profil (kısmi güncelleme), şirket tekilleştirme, sektör ve etiket havuzu, depolama arayüzü ve fotoğraf uçları. 166 test.

*İstemci:* Tema tek dosyada, üç durum bileşenleri, API istemcisi, güvenli jeton deposu, sessiz yenileme, kayıt/giriş ekranları, beş adımlı profil sihirbazı, profil özeti. 13 test.

Tarayıcıda uçtan uca doğrulandı: kayıt → sihirbazın beş adımı → %89 tamamlanma → "başvurabilirsin" → sayfa yenilemede kaldığı adımdan devam.

**Aşama 4 bitti — etkinlik oluşturma ve otomatik salon düzeni.**

*Backend:* Program hesaplama servisi, etkinlik CRUD, kapak görseli, otomatik masa üretimi, kapasite uyarısı, kayıtları açma kapısı, sahiplik kontrolü. 204 test.

*İstemci:* Alt gezinme (Etkinlikler + Profilim), etkinlik listesi, dört adımlı sihirbaz, anlık program önizlemesi. 23 test.

Tarayıcıda doğrulandı: taslak → dört adım → tur eklenince süre 3:50'den 4:30'a → 10 masa 1-10 numaralı → kapasite uyarısı (100 kişi / 60 kişilik salon) → kayıtlar açıldı.

**Aşama 5 bitti — manuel salon editörü.**

*Backend:* Manuel mod ucu, masa yerleştirme ve taşıma, alan bloğu CRUD, hücre çakışması (masa↔masa ve masa↔alan bloğu), ızgara sınırları. Varsayılan ızgara 24×16 hücre. 231 test.

*İstemci:* `InteractiveViewer` tuvali, ızgaraya oturan sürükle-bırak, araç çubuğu, masa ve alan panelleri, biriken otomatik kaydetme. 45 test.

Aşama 1'den devreden borç kapandı: masa ile alan bloğunun aynı hücreyi paylaşmaması şemada ifade edilemiyordu, `app/services/layout.py` içindeki `find_cell_conflict()` ile uygulandı.

Tarayıcıda doğrulandı: otomatik 6 masa → manuele geçişte masalar korunup dizildi → sürükle-bırak ızgaraya oturdu → dolu hücreye bırakma "Bu hücre dolu: 5 numaralı masa." → sahne bloğu → numara çakışmasında satır içi uyarı → sayfa yenilemede düzen kayıpsız → sihirbaza dönüşte kapasite 36'dan 43'e güncellendi.

**Aşama 6 bitti — etkinlik keşfi ve başvuru.**

*Backend:* Keşif listesi, katılımcının gördüğü etkinlik detayı (organizatör alanları sızmıyor), başvuru kapıları, geri çekme, organizatörün onay/red uçları. 253 test.

*İstemci:* Etkinlikler sekmesi ikiye ayrıldı (Keşfet / Düzenlediklerim), katılımcı detay ekranı, başvuru akışı, eksik profil kapısı, organizatörün onay ekranı. 61 test.

Etiket havuzu 48'den **72'ye** çıktı (migration `0003`, üç yeni kategori). 72 bir tavan — sebebi aşağıdaki tuzaklarda.

Aşama 3'te kurulan başvuru kapısı burada ilk kez iş görüyor: eksik profille başvuru 422 dönüyor ve eksikler Türkçe yazılıyor.

Tarayıcıda doğrulandı: keşif listesi → eksik profille başvuru engellendi ve eksikler listelendi → profil tamamlanınca başvuru → organizatör profil özetiyle gördü ve onayladı → katılımcıda "Kabul edildi" → kontenjan dolunca onay düğmesi "Kontenjan dolu".

**Aşama 7 bitti — motor bağlandı.**

*Motor:* Kategori düzeyinde kısmi puan (9.3). Tam etiket eşleşmesi tam puan, aynı kategoride buluşma kısmi puan. Katsayı 0.30, doyum 1 — ölçülerek seçildi. Etiket havuzunun tavanı 72'den ~120'ye çıktı.

*Backend:* Veritabanı↔motor dönüşümü, arka plan işi (ARQ), plan versiyonlama, kontrol listesi. `plans` tablosuna hesabın durumu eklendi (migration `0004`). 280 test.

*İstemci:* Kontrol listesi, çalıştırma, durum izleme, özet, versiyon geçmişi. 73 test.

Gerçek veriyle doğrulandı (24 katılımcı / 8 şirket / 6 masa / 5 tur): kuyrukta → çalışıyor → bitti, 96 atama, herkes en az 4 turda oturmuş, **kesin kural ihlali sıfır** (aynı kişi iki masada, kapasite aşımı, aynı şirket aynı masada, tek kişilik masa).

Tarayıcıda doğrulandı: kontrol listesi ve Türkçe uyarı → çalıştır → "Kuyrukta" → "Bitti" + özet → ikinci çalıştırma versiyon 2 ve geçmiş. Aynı tohum iki kez aynı sonucu verdi (5.3).

**Aşama 8 bitti — plan önizleme ve elle düzeltme.**

*Backend:* Slot görünümü (boş masalar dahil), üç seviyeli masa kalitesi, takas ve boş yere taşıma, sabitleme, yayınlama. Kural kontrolleri takastan sonra çalışıyor ve takası **engellemiyor** (M7); reddedilen tek durum sabitlenmiş atama. Takas yeni ikililer ürettiği için sinerji modeli yeniden kurulup `match_reasons` tazeleniyor. 311 test.

*İstemci:* Plan önizleme ekranı, tur seçici, kalite rozetleri, dokun-dokun takas, uyarı ve ret şeritleri, özet paneli, yayınlama onayı. 108 test.

Uyarılar bağımsız bir gözle sınanıyor: her takastan sonra plan `engine/rules.py`'deki `find_violations`'tan geçiyor ve orada bulunan her ihlal türünün uçtan da uyarı olarak döndüğü doğrulanıyor.

Tarayıcıda doğrulandı (10 katılımcı / 5 masa × 3 sandalye / 4 tur): dört tur gezildi → takas → dört uyarı türü Türkçe → boş masaya taşıma → sabitleme → sabitlenmişi taşımada kırmızı ret şeridi → yayınla → "Yayında". İki dil hatası tarayıcıda yakalandı ve düzeltildi (aşağıdaki tuzaklar).

**Sıradaki: Aşama 9 — Katılımcı deneyimi.** Katılımcının kendi programı, masa arkadaşları, eşleşme gerekçesi.

### API uçları

```
POST /auth/register  POST /auth/login  POST /auth/refresh  GET /auth/me
GET  /profile        PATCH /profile
POST /profile/photo  DELETE /profile/photo
GET  /companies?q=   POST /companies
GET  /sectors        GET /tag-categories
GET  /files/...      (yerel depolamadaki dosyalar)

GET  /events              POST /events
GET  /events/{id}         PATCH /events/{id}
POST /events/{id}/cover   DELETE /events/{id}/cover
POST /events/{id}/open-registration

GET  /events/{id}/layout
PUT  /events/{id}/layout/auto      PUT /events/{id}/layout/manual
POST /events/{id}/tables           PATCH /events/{id}/tables/{tid}
DELETE /events/{id}/tables/{tid}
POST /events/{id}/areas            PATCH /events/{id}/areas/{aid}
DELETE /events/{id}/areas/{aid}

GET    /events/discover                 GET /events/{id}/public
POST   /events/{id}/registration        DELETE /events/{id}/registration
GET    /events/{id}/registrations?status=
POST   /events/{id}/registrations/{rid}/approve
POST   /events/{id}/registrations/{rid}/reject

GET  /events/{id}/matching-check
POST /events/{id}/plans      GET /events/{id}/plans      GET /events/{id}/plans/{pid}

GET   /events/{id}/plans/{pid}/slots/{slot}
POST  /events/{id}/plans/{pid}/swap
PATCH /events/{id}/plans/{pid}/assignments/{aid}
POST  /events/{id}/plans/{pid}/publish
```

Çıkış ucu yok: jetonlar durumsuz, çıkış istemcide jetonu silmekle olur.

**Motoru denemek için:** `cd backend && python -m engine.cli --katilimci 200 --slot 8 --masa 50`

Verilen kararlar ve gerekçeleri: `docs/kararlar.md`.

## Komutlar

Docker WSL2 içinde çalışıyor; `docker compose` komutları WSL kabuğundan verilir.

Açık bir `wsl.exe` oturumu kalmazsa WSL localhost port yönlendirmesini kaldırır: konteynerler ayakta kalır ama Windows'tan `localhost:5432` kapanır. Oturum açılışında çalışan bir zamanlanmış görev bunu önlüyor — kurulumu ve denenip işe yaramayanlar README'de.

**Sistem**

```
docker compose up -d              tüm sistem (db, redis, api, worker)
docker compose up -d db redis     sadece veri servisleri — günlük geliştirme
docker compose ps                 servis durumları
docker compose logs -f api        günlük takibi
```

**Backend** (venv etkin, `backend/` klasöründen)

```
uvicorn app.main:app --reload     sunucu
arq app.worker.WorkerSettings     arka plan işçisi
pytest                            testler — veritabanı gerektirmez
ruff check . && ruff format .     lint ve biçim
alembic upgrade head              şemayı güncelle
alembic revision --autogenerate -m "aciklama"
```

Sanal ortam bir kez: `python -m venv .venv` ardından `pip install -e ".\backend[dev]"`.

**İstemci** (`app/` klasöründen)

```
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
flutter analyze
flutter test
flutter build web --dart-define=API_BASE_URL=<adres>
```

Sunucu adresi koda gömülmez, `--dart-define` ile verilir.

**Doğrulama**

```
curl http://localhost:8000/health         süreç ayakta mı
curl http://localhost:8000/health/ready   db ve redis'e erişiliyor mu
```

## Dikkat edilecek tuzaklar

**`backend/alembic.ini` yalnızca ASCII.** Alembic bu dosyayı işletim sisteminin yerel kod sayfasıyla okur; Türkçe karakter Windows'ta dosyayı okunamaz yapar. Diğer dosyalarda Türkçe serbest.

**Motor sınırı testle korunuyor.** `backend/engine/` altına FastAPI, SQLAlchemy, veritabanı veya HTTP kütüphanesi import edilirse `pytest` kırılır.

**Yeni durum alanı eklerken `status_check` kullan.** `app/models/enums.py` içindeki `status_column` tek başına CHECK kısıtı üretmez — sütun denetimsiz metin olur. Kısıt `status_check` ile `__table_args__` içine elle yazılır.

**Migration ürettikten sonra kayma kontrolü yap.** `alembic revision --autogenerate` ikinci kez çalıştırıldığında **boş** revizyon üretmeli. Üretmiyorsa model ile migration ayrışmıştır.

**Modelin yeni modülü `app/models/__init__.py`'ye eklenmeli.** Eklenmezse `Base.metadata` onu görmez ve autogenerate tabloyu "silinmiş" sayar.

**Motorda yeni hamle veya kural yazarken amaç fonksiyonunu da kontrol et.** `PlanState.objective()` kullanılmayan masayı 0 puan sayar; kötü bir masa da 0 alırsa arama ikisini ayırt edemez. Boş masaya tek kişi oturtma hatası tam olarak böyle oluştu — ayrıntı `docs/kararlar.md`'de.

**Şirket normalleştirmesine dokunursan testleri çalıştır.** `app/services/company.py` aynı şirketin farklı yazımlarını tek kimliğe indirger; "aynı şirketten iki kişi aynı masaya oturamaz" kuralının tamamı buna dayanır. Noktanın ayraç sayılması bu kuralı sessizce bozmuştu.

**Test e-postaları `.test` veya `.local` olamaz.** `email-validator` ayrılmış üst düzey alan adlarını reddeder; `tests/conftest.py` içindeki `unique_email` fixture'ı kullanılmalı.

**Ekranlarda sabit renk veya aralık yazma.** Hepsi `app/lib/core/theme/app_theme.dart` içinden gelir; görsel kimlik kararı verildiğinde tek dosya değişecek.

**Yeni ekran yazarken üç durumu da kur.** `app/lib/core/widgets/state_views.dart` içindeki `LoadingView`, `ErrorView`, `EmptyView` kullanılır — sonradan eklenmez.

**Form hatasını `AsyncValue.guard` ile paylaşılan duruma yazma.** Yönlendirme o durumu görüp kullanıcıyı başka sayfaya atar, hata hiç okunmaz. Hata formun kendi state'inde tutulur.

**Testte modül seviyesindeki fonksiyonu yamalama.** Uçlar `from ... import x` ile fonksiyonu kendi ad alanlarına kopyalar; modülü değiştirmek onları etkilemez. FastAPI bağımlılığı yapıp `dependency_overrides` kullan — `StorageDep` bu yüzden var.

**Dosya yükleyen istek `FormData` klonlamalı.** Akış ilk gönderimde tükenir; sessiz yenileme tekrar denediğinde sunucuya boş gövde gider. `api_client.dart` bunu araya giricide hallediyor.

**Veri değiştikten sonra `invalidate` tek başına yetmez.** Yeniden hesaplama asenkron başlar; hemen gezinirsen ekran eski veriyle açılır. `invalidate` + `await read(...future)` kullan — `EventActions` bu kalıbı izliyor.

**Program hesabı iki yerde: `schedule.py` ve `schedule.dart`.** Birini değiştirirsen diğerini de değiştir; aynı senaryolar iki tarafta da test ediliyor (`test_schedule.py`, `schedule_test.dart`).

**Uzun süren dış bağımlılığı bağımlılık olarak ver.** Depolama (`StorageDep`) ve kuyruk (`JobQueueDep`) böyle; testler `dependency_overrides` ile sahtesini koyuyor. Kuyruk ilk yazımda doğrudan çağrılmıştı ve her uç testi gerçek Redis'e iş atıyordu — altmış hayalet iş birikti.

**`rollback` sonrası ORM nesnesine dokunma.** Bütün nesnelerin süresi dolar; bir alanı okumak eşzamansız yeniden yükleme tetikler ve `MissingGreenlet` verir. Hata yolunda nesne değil kimlik taşı — `plan_runner._fail` bu yüzden `plan_id` alıyor.

**`arq app.worker.WorkerSettings` çalışmıyorsa eşleştirme kuyrukta bekler.** Plan `queued` durumunda kalır, hata vermez. Geliştirirken en sık atlanan adım.

**Sabit yollu uç, parametreli uçtan önce kaydedilmeli.** `main.py` içinde `registration.router`, `event.router`'dan önce geliyor; tersi olsaydı `/events/discover` yolu `/events/{event_id}` ile eşleşir ve "discover" bir kimlik sanılıp 422 dönerdi.

**Katılımcıya `EventResponse` döndürme.** O şema organizatörün alanlarını taşıyor (`auto_approve_registrations`, `request_quota`, `capacity_summary`). Katılımcının gördüğü `PublicEventResponse` ayrı — alan gizlemek yerine ayrı şema, ileride organizatör yanıtına eklenen bir alan sessizce dışarı çıkmasın diye.

**Süzgeçli listede tek süzgeci tazeleme.** `eventRegistrationsProvider` süzgeci argümanında tutuyor, yani her süzgeç ayrı bir önbellek. Onaylanan başvuru "bekleyen"den düşüp "kabul"e girmeli; `RegistrationActions._invalidateRegistrations` hepsini birden tazeliyor.

**Etiket eklerken mevcut kategorilere ekle.** Kategori düzeyinde kısmi puan (9.3) havuzun tavanını 72'den ~120'ye çıkardı, ama yalnızca kategori sayısı 9-15'te kalırsa: kategoriler etiketlerle birlikte çoğalırsa örtüşme yine seyrekleşir ve kazanç kaybolur. Ölçüm komutu `python -m engine.cli --etiket <n> --kategori <k> --secim 3`. Ayrıntı `docs/kararlar.md`'de.

**`explain()` kırılımına puan olmayan bir şey koyma.** Katkıların toplamı skora eşit olmalı; `test_breakdown_matches_the_matrix` bunu kontrol ediyor ama yalnızca kendi senaryolarında. Bayrak niteliğinde bir bilgi gerekiyorsa gerçek bir katkı kalemine dönüştürülmeli — `category` böyle yapıldı.

**Etiket silme. Yalnızca ekle.** `profile_tags` etiket kimliğine bakıyor; silinen etiketi seçmiş profiller etkilenir. Ad düzeltmek serbest, kimlik aynı kalıyor.

**Hücre çakışmasını `find_cell_conflict()` üzerinden geçir.** Masa↔masa çakışmasını veritabanı indeksi de yakalar ama numara çakışmasıyla aynı `IntegrityError`'a düşer; mesaj yanlış çıkar. Masa↔alan bloğu çakışması ise **yalnızca** `app/services/layout.py` içinde kontrol ediliyor, şemada karşılığı yok.

**Panelde otomatik kaydetme birikimli olmalı.** `layout_sheets.dart` içindeki `_DebouncedSaver` bekleyen değişiklikleri bir sözlükte topluyor. Tek bir gönderim tutulursa arka arkaya değiştirilen iki alandan ilki sessizce kaybolur — tam olarak böyle oldu, ayrıntı `docs/kararlar.md`'de.

**Görünmeyen ilerleme göstergesi bırakma.** Saydamlığı sıfırlanmış `CircularProgressIndicator` tik atmaya devam eder ve `pumpAndSettle` hiç durulmaz; gösterge yalnızca gerektiğinde kurulmalı.

**Türkçe cümlede sayıya ek getirme.** Ek sayının **okunuşuna** göre değişiyor: 1'in ama 2'nin, 3'ün, 4'te, 6'da, 9'un. Arayüzde "Masa 2'ın" ve "Masa 4'da" çıktı. Cümle ek gerektirmeyecek şekilde kurulur — *"Masa 3 — tek kişi kaldı: ..."*. `plan_test.dart` içinde bir test bunu tutuyor.

**Masa kalitesi motorun amaç fonksiyonundan farklı.** Motor 9.4'ü optimize ediyor (masanın en zayıf ikilisi); rozet `table_score()` ile **en yalnız kişinin en iyi bağına** bakıyor. İkisi bilerek ayrı: en zayıf ikili masa boyuyla birlikte anlamını yitiriyor, ölçümde altı sandalyeli masaların hiçbiri "iyi" alamıyordu. İki kişilik masada iki ölçüt aynı sonucu veriyor. Ayrıntı ve ölçüm `docs/kararlar.md`'de.

**Tek kişilik masaya "Boş" yazma.** Sunucu ona kalite vermiyor (skor en zayıf ikili bağ, tek kişide bağ yok) ve `TableQuality.empty` dönüyor. İstemci bunu doğrudan etikete çevirince masada biri otururken rozet "Boş" diyordu. `QualityBadge` doluluğa da bakıyor.

**Takas uçları görünümü geri döndürüyor, ekran onu kullanmalı.** Sağlayıcının yeniden yüklemesini beklemek listeyi bir an eski hâline döndürür ve seçimi kaybettirir. `plan_screen.dart` yanıttaki görünümü tutuyor, sağlayıcıyı ayrıca tazeliyor.

**Kural ihlali takası engellemez.** M7 açıkça *"organizatör uyarıya rağmen devam edebilir"* diyor. `apply_swap` yalnızca sabitlenmiş atamayı reddediyor (409); kalan her şey `200` gövdesinde uyarı olarak dönüyor. Uyarı şeridi ile ret şeridi ayrı — biri "oldu ama dikkat", diğeri "olmadı".

**Takastan sonra `match_reasons` tazelenmeli.** Takas daha önce yan yana gelmemiş ikililer üretiyor; satırlar yazılmazsa masa skoru yanlış çıkar ve Aşama 9'da katılımcıya olmayan bir gerekçe gösterilir. `_recompute_reasons` sinerji modelini yeniden kuruyor (200 kişi için ~10 ms).
