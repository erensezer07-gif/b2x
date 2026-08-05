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

**Aşama 0 — Temel.** Repo iskeleti, Docker Compose, veritabanı bağlantısı, migration altyapısı, boş FastAPI ve Flutter projeleri.

Aşama 2 (eşleştirme motoru) bitmeden hiçbir ekran yazılmaz.

## Komutlar

Bu bölüm Aşama 0 tamamlanınca doldurulacak.
