# B2X

B2B etkinlik eşleştirme ve oturma planlama platformu.

Kurumsal etkinliklerde (zirve, fuar, iş forumu) katılımcıların birbiriyle tanışması genelde tesadüfe kalır. B2X bunu planlı hale getirir: katılımcı profillerini karşılaştırıp her görüşme turu için kimin hangi masada oturacağını hesaplar.

Ayrıntılı işlevsel şartname: **`B2X_SPEC.md`**

## Yapı

| Klasör | İçerik |
|---|---|
| `backend/app/` | FastAPI uygulaması, API uçları, veritabanı katmanı |
| `backend/engine/` | Eşleştirme motoru — bağımsız, veritabanı ve HTTP bilmeyen paket |
| `app/` | Flutter istemcisi (Android, Web, iOS) |
| `infra/` | Docker Compose ve altyapı dosyaları |
| `docs/` | Kararlar ve notlar |

## Teknoloji

- **İstemci:** Flutter 3.44 — Riverpod, go_router
- **Backend:** Python 3.13 + FastAPI
- **Veritabanı:** PostgreSQL 16
- **Kuyruk:** Redis + ARQ
- **Motor:** Saf Python + NumPy

## Gereksinimler

- Python 3.13
- Flutter 3.44 (stable)
- Docker ve Docker Compose
- Git

## Kurulum

**1. Depoyu al**

```
git clone <depo-adresi>
cd b2x
```

**2. Ortam dosyasını oluştur**

```
cp .env.example .env
```

Windows PowerShell:

```
Copy-Item .env.example .env
```

`.env` içindeki `POSTGRES_PASSWORD` ve `JWT_SECRET` değerlerini değiştir. `.env` dosyası depoya girmez.

**3. Servisleri başlat**

```
docker compose up -d
```

Postgres ve Redis ayağa kalkar.

**4. Veritabanı şemasını kur**

```
cd backend
alembic upgrade head
```

**5. Backend'i çalıştır**

```
uvicorn app.main:app --reload
```

API dokümanı: `http://localhost:8000/docs`

**6. İstemciyi çalıştır**

```
cd app
flutter pub get
flutter run -d chrome
```

Android için `-d chrome` yerine cihaz kimliği verilir. `flutter devices` ile listelenir.

## Telefondan test

Telefon ve bilgisayar aynı ağdaysa, `.env` içindeki `API_BASE_URL` değerini bilgisayarın yerel ağ adresiyle değiştir:

```
API_BASE_URL=http://192.168.1.35:8000
```

Yerel adres `ipconfig` (Windows) veya `ip addr` (Linux) ile bulunur.

## Testler

Eşleştirme motorunun testleri kritik önemdedir. Motor üzerinde yapılan her değişiklikten sonra çalıştırılır:

```
cd backend
pytest
```

## Başka bir sunucuya kurulum

Projede sabit adres veya makineye özel ayar bulunmaz. Tüm yapılandırma `.env` dosyasından okunur.

Yeni bir sunucuya kurmak için: depoyu kopyala, `.env` dosyasını o ortama göre doldur, `docker compose up -d` çalıştır, migration'ları uygula.

## iOS notu

Flutter kodu iOS'u destekler ancak iOS derlemesi macOS ve Xcode gerektirir. Proje Windows üzerinde geliştirildiği için iOS derlemesi yapılmamıştır. Mac erişimi olan bir ortamda `flutter build ios` ile derlenebilir.
