# Devir teslim

Bu belge projeyi **devralan geliştirici** için yazıldı. Kurulum ve günlük
komutlar `README.md`'de; burada onlar tekrarlanmıyor. Buradaki soru şu:
*kod nerede, neden öyle yazıldı, neye dokunurken dikkat etmek gerekir.*

Okuma sırası:

1. `B2X_SPEC.md` — **tek referans.** Ürünün ne yapması gerektiği burada.
2. Bu belge — sistemin haritası ve dokunulmaz kuralları.
3. `docs/kararlar.md` — verilen kararlar ve **gerekçeleri.** Bir şeyin neden
   böyle olduğunu merak ettiğinde önce buraya bak; büyük ihtimalle denenmiş
   ve ölçülmüştür.
4. `CLAUDE.md` — kısa durum özeti ve tuzak listesi.

---

## 1. On dakikada çalışır hale getirme

```
docker compose up -d db redis
cd backend && alembic upgrade head
uvicorn app.main:app --reload            # ayrı bir kabukta
arq app.worker.WorkerSettings            # ayrı bir kabukta
python scripts/demo.py                   # sahte etkinlik + yayınlanmış plan
cd ../app && flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

`scripts/demo.py` bir **duman testidir**: kayıttan yayınlanmış plana kadar her
adımı gerçek uçlardan geçirir. Sonuna kadar gidiyorsa veritabanı,
migration'lar, Redis, arka plan işçisi ve motor birlikte çalışıyor demektir.
Bitişte ekrana giriş bilgilerini yazar; arayüzü dolu veriyle gezebilirsin.

---

## 2. Sistem haritası

```
Flutter (app/)
   │  HTTP + JWT
   ▼
FastAPI (backend/app/)
   │  api/routes/   uçlar — doğrulama, yetki, HTTP durum kodları
   │  services/     iş kuralları — asıl mantık burada
   │  models/       SQLAlchemy tabloları
   │  schemas/      Pydantic istek/yanıt şemaları
   ▼
PostgreSQL          Redis + ARQ ──► backend/engine/  (eşleştirme motoru)
```

**Uçlar ince, servisler kalın.** Bir uç genelde şunu yapar: yetkiyi doğrula,
servisi çağır, sonucu şemaya çevir. İş kuralı arıyorsan `services/` altına
bak.

### Motor (`backend/engine/`)

Projenin kalbi ve **bilerek izole**. Veritabanı, HTTP, FastAPI bilmez; sadece
standart kütüphane ve NumPy. Girdisi bir `EngineInput`, çıktısı bir
`EngineOutput` — ikisi de düz veri (`types.py`).

| Dosya | İş |
|---|---|
| `types.py` | Girdi/çıktı veri yapıları ve ayarlar |
| `scoring.py` | İkili sinerji skoru ve bileşenleri (spec 9.3) |
| `weights.py` | Bileşen ağırlıkları |
| `state.py` | Plan durumu — oturma matrisi, skorlar, amaç fonksiyonu |
| `greedy.py` | Adım 3: ilk yerleştirme |
| `local_search.py` | Adım 4: benzetimli tavlama |
| `fairness.py` | Adım 5: asgari tur onarımı |
| `minimal_change.py` | 9.8: önceki plandan devam, gereksiz taşımayı cezalandır |
| `rules.py` | Bağımsız denetleyici — kesin kuralların ikinci gözü |
| `reasons.py` | Skor kırılımı (M8'in gerekçeleri buradan besleniyor) |
| `runner.py` | Adımları sırayla çalıştırır, özeti üretir |
| `synthetic.py` / `cli.py` | Sentetik veri ve terminal raporu |

Motoru veritabanı olmadan denemek:

```
cd backend && python -m engine.cli --katilimci 200 --slot 8 --masa 50
```

### Veritabanı ↔ motor köprüsü

`app/services/matching.py`. Kabul edilmiş başvuruları, masaları, talepleri ve
(varsa) önceki planı motorun beklediği indeks tabanlı biçime çevirir. Motor
0 tabanlı, veritabanı 1 tabanlı — dönüşüm yalnızca burada.

`app/services/plan_runner.py` işi kuyruğa alır, çalıştırır, sonucu satırlara
yazar ve özet sayılarını hesaplar.

### İstemci (`app/lib/`)

```
core/     tema, API istemcisi, jeton deposu, yönlendirici, üç durum bileşenleri
features/ auth · profile · events · shell · splash
```

Durum yönetimi Riverpod. Kalıp şu: `*_repository.dart` HTTP yapar,
`*_controller.dart` sağlayıcıları tanımlar, `*_screen.dart` çizer.
**Türkçe metinlerin tamamı istemcide** — sunucu İngilizce anahtar döndürür,
cümleyi arayüz kurar. Böylece bütün dil tek katmanda duruyor.

---

## 3. Dokunulmaz kurallar

Bunlar tercih değil; her biri bir başarısızlık biçiminden geliyor.

**Motor sınırı.** `backend/engine/` altına FastAPI, SQLAlchemy, veritabanı
veya HTTP kütüphanesi girmez. Bir test bunu koruyor
(`tests/test_engine_boundary.py`) ve `ruff` de uyarır. Sebep: motorun tek
başına test edilebilir ve ölçülebilir kalması.

**Görünürlük sunucuda uygulanır.** Katılımcı başka masadaki kişinin bilgisine
erişemez. Arayüzde gizlemek yetmez — uç doğrudan çağrıldığında da veri
dönmemeli. Katılımcı uçları kimlik parametresi bile almaz: kimlik jetondan
gelir, "başkasının planını iste" diye bir istek biçimi yoktur.

**Sabit değer yok.** Sunucu adresi, veritabanı bilgisi, anahtarlar, portlar —
hepsi ortam değişkeninden. Kodda `localhost` geçmez. İstemcide adres
`--dart-define` ile derleme sırasında verilir.

**Motor değişikliği testsiz kabul edilmez.** `backend/engine/` altında bir şey
değiştiyse `pytest` çalıştırılır ve geçtiği görülür.

**Bir etkinlikte aynı anda tek yayında plan.** Koşullu benzersiz indeksle
veritabanı seviyesinde zorlanıyor. Yeni versiyon yayınlanınca öncekisi
arşive geçer.

**Türkçe arayüz, İngilizce kod.** Değişken, fonksiyon, tablo, sütun adları
İngilizce; kullanıcının gördüğü her metin Türkçe.

---

## 4. Kapsam dışı bırakılanlar

Eksik değil, **bilerek yok.** Eklemeden önce şartnameye yazılmalı.

- **E-posta gönderimi.** Doğrulama, şifre sıfırlama, davet — hiçbiri yok.
  MVP'de e-posta gerektiren akış yazılmıyor (spec Bölüm 2).
- **Bildirim.** Push, SMS, uygulama içi bildirim yok.
- **Gelen görüşme talebi ucu.** M9: *"talep gönderildiği kişiye
  bildirilmez."* Kural bir süzgeçle değil, **ucun yokluğuyla** uygulanıyor.
  Yeni bir alan eklerken karşı tarafın talebini sızdırmadığından emin ol.
- **Katılımcıya skor gösterimi.** M8: *"'Uyum: %62' gibi bir ifade
  kullanılmaz."* Katılımcı şemaları organizatörünkinden ayrı ve bir test
  yanıtın tamamını tarayarak skor sızmadığını doğruluyor.
- **Etiket silme.** Yalnızca ekleme. Silinen etiketi seçmiş profiller
  etkilenir; ad düzeltmek serbest, kimlik sabit kalır.
- **iOS derlemesi.** Kod destekliyor, macOS olmadığı için derlenmedi.

---

## 5. Bilinen sınırlar ve sıradaki işler

**Ayarlanacak sayılar.** Sinerji bileşenlerinin ağırlıkları (`engine/weights.py`)
ve kalite eşiği başlangıç değerleridir; gerçek etkinlik verisiyle
ayarlanmalı. Kalite eşiği ortam dosyasında.

**Etiket havuzunun tavanı.** Bugün 72 etiket / 9 kategori. Kategori düzeyinde
kısmi puan sayesinde ~120 etikete kadar çıkılabilir — **kategori sayısı
9-15'te kalmak şartıyla.** Kategoriler etiketlerle birlikte çoğalırsa örtüşme
seyrekleşir ve kazanç kaybolur. Ölçüm komutu:
`python -m engine.cli --etiket <n> --kategori <k> --secim 3`

**Ölçek.** 200 katılımcı / 8 tur / 50 masa ölçeğinde ~5 saniye. Daha
büyüğü denenmedi; yerel aramanın deneme sayısı (`--deneme`) ayarlanabilir.

**Görsel kimlik.** Tema tek dosyada (`app/lib/core/theme/app_theme.dart`).
Karar verildiğinde yalnızca o dosya değişir; ekranlarda sabit renk veya
aralık yoktur.

**Depolama.** Profil fotoğrafları yerel diske yazılıyor. Buluta geçmek için
`app/services/storage.py` içindeki `Storage` arayüzünü uygulayan yeni bir
sınıf yazmak yeterli, başka dosya değişmez.

---

## 6. Belirti → sebep

Sık karşılaşılanlar. Uzun listesi `CLAUDE.md`'nin tuzaklar bölümünde.

| Belirti | Sebep |
|---|---|
| Plan "Kuyrukta" yazıp orada kalıyor | `arq app.worker.WorkerSettings` çalışmıyor. Ekran 45 saniye sonra bunu söylüyor |
| Var olduğunu bildiğin uca `Not Found` | `api` konteyneri portu kapmış, istek imajın içindeki eski koda gidiyor. `docker compose stop api worker` |
| Backend bir süre sonra veritabanını kaybediyor | WSL'de açık oturum kalmamış, localhost yönlendirmesi düşmüş. README'deki zamanlanmış görev |
| Postgres yeniden başladıktan sonra ekranlar sonsuz dönüyor | Havuzdaki bağlantılar cevapsız kalmış. `DB_TIMEOUT_SECONDS` sonunda hataya döner; kalıcı çözüm sunucuyu yeniden başlatmak |
| `alembic` dosyayı okuyamıyor | `backend/alembic.ini` **yalnızca ASCII** olmalı; Alembic onu işletim sisteminin yerel kod sayfasıyla okuyor |
| `autogenerate` boş revizyon üretmiyor | Model ile migration ayrışmış. Yeni bir model modülü `app/models/__init__.py`'ye eklenmemiş olabilir |
| Testte `MissingGreenlet` | `rollback` sonrası ORM nesnesine dokunulmuş, ya da bir ilişki eager yüklenmemiş |
| İstemcide önceki kullanıcının verisi | Veri tutan bir sağlayıcı depoyu `watch` yerine `read` ile almış; oturum değişince zincir kopuyor |

---

## 7. Test yaklaşımı

| Katman | Nerede | Ne kanıtlıyor |
|---|---|---|
| Motor | `tests/test_engine_*.py` | Kesin kurallar ihlal edilmiyor, adalet tutuyor, minimum değişim çalışıyor, aynı tohum aynı sonucu veriyor |
| Şema | `tests/test_schema_constraints.py` | Kuralı bilerek ihlal edip veritabanının reddettiğini doğruluyor |
| Uçlar | `tests/test_*_api.py` | Yetki, görünürlük, kapılar, Türkçe hata mesajları |
| İstemci | `app/test/` | Türkçe cümle kurulumu, üç durum, önbellek tazeleme, yönlendirme |

İki alışkanlık işe yaradı, sürdürülmesi öneriliyor:

**Düzeltmenin testi, düzeltme olmadan kırılmalı.** Yazdıktan sonra düzeltmeyi
geçici olarak geri al ve testin gerçekten kırıldığını gör. Kırılmıyorsa test
bir şey korumuyordur.

**Uçtan uca bak.** İki ucu hazır ama ortası bağlanmamış özellikler birim
testlerinden geçiyor. Karşılıklı talep gerekçesi tam olarak böyleydi: sunucu
biliyordu, istemci cümleyi kuruyordu, testler geçiyordu — ve özellik üretimde
hiç çalışmadı.

---

## 8. Şartnameyi değiştirmek

Ürün davranışı değişecekse sıra şudur: **önce şartname, sonra kod.**
`B2X_SPEC.md` tek referans; kod ondan sapmışsa hangisinin doğru olduğu
belirsizleşir ve belge çürür.

Karar verirken gerekçeyi `docs/kararlar.md`'ye yaz. Orada "şöyle yaptık"
değil "şu ölçüldü, şu denendi, bu yüzden böyle" yazıyor — devralan kişinin
aynı yolu ikinci kez yürümemesi için.
