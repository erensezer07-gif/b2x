# B2X

B2B etkinlik eşleştirme ve oturma planlama platformu.

Kurumsal etkinliklerde (zirve, fuar, iş forumu) katılımcıların birbiriyle tanışması genelde tesadüfe kalır. B2X bunu planlı hale getirir: katılımcı profillerini karşılaştırıp her görüşme turu için kimin hangi masada oturacağını hesaplar.

Ayrıntılı işlevsel şartname: **`B2X_SPEC.md`**

Projeyi devralıyorsan: **`docs/devir-teslim.md`** — sistem haritası, dokunulmaz kurallar, bilinen sınırlar ve belirti→sebep tablosu.

## Yapı

| Klasör | İçerik |
|---|---|
| `backend/app/` | FastAPI uygulaması, API uçları, veritabanı katmanı |
| `backend/engine/` | Eşleştirme motoru — bağımsız, veritabanı ve HTTP bilmeyen paket |
| `app/` | Flutter istemcisi (Android, Web, iOS) |
| `infra/` | Docker Compose servis tanımları |
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

**3. Sistemi başlat**

```
docker compose up -d
```

Dört servis ayağa kalkar: `db`, `redis`, `api`, `worker`. Durumu görmek için:

```
docker compose ps
```

API dokümanı: `http://localhost:8000/docs`
Sağlık kontrolü: `http://localhost:8000/health/ready` — veritabanına ve Redis'e gerçekten ulaşılıp ulaşılmadığını söyler.

**4. Veritabanı şemasını kur**

```
docker compose exec api alembic upgrade head
```

> Aşama 1 tamamlanana kadar tablo tanımı yoktur; bu komut şu an hatasız çalışır ama iş yapmaz.

**5. Dosya klasörü**

Profil fotoğrafları `.env` içindeki `STORAGE_LOCAL_PATH` klasörüne yazılır (varsayılan `./storage`). Klasör ilk çalıştırmada kendiliğinden oluşur ve depoya girmez.

Bulut depolamaya geçilecekse `backend/app/services/storage.py` içindeki `Storage` arayüzünü uygulayan yeni bir sınıf yazmak yeterli — başka hiçbir dosya değişmez.

**6. İstemciyi çalıştır**

```
cd app
flutter pub get
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

Sunucu adresi koda gömülmez, derleme sırasında `--dart-define` ile verilir. Verilmezse uygulama açılır ama adresin eksik olduğunu ekranda söyler.

Android için `-d chrome` yerine cihaz kimliği yazılır; `flutter devices` ile listelenir.

## Geliştirme

Konteynerdeki `api` servisi kodu imajın içinden çalıştırır, canlı yeniden yükleme yapmaz. Günlük geliştirmede yalnızca veri servisleri konteynerde tutulur, backend doğrudan makinede çalıştırılır:

```
docker compose up -d db redis
```

> **Sondaki `db redis` önemli.** Düz `docker compose up -d` yazarsan `api` konteyneri de kalkar ve `API_PORT`'u kaplar. O zaman iki şey olur: makinedeki `uvicorn` portu alamaz, ve tarayıcı istekleri imajın içindeki **eski koda** gider. Belirtisi, var olduğunu bildiğin bir uca `Not Found` almandır. Kontrol: `http://localhost:8000/docs` uzun bir uç listesi göstermeli; iki satır gösteriyorsa konteyner yanıt veriyordur.
>
> Yanlışlıkla açtıysan: `docker compose stop api worker`
>
> İmajı tazelemek istersen (teslim öncesi): `docker compose build api worker`

Sanal ortam (bir kez):

```
python -m venv .venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
pip install -e ".\backend[dev]"      # Linux/macOS: pip install -e "./backend[dev]"
```

Sunucu:

```
cd backend
uvicorn app.main:app --reload
```

Arka plan işçisi:

```
cd backend
arq app.worker.WorkerSettings
```

Migration üretmek ve uygulamak:

```
cd backend
alembic revision --autogenerate -m "aciklama"
alembic upgrade head
```

## Testler

Eşleştirme motorunun testleri kritik önemdedir. `backend/engine/` üzerinde yapılan her değişiklikten sonra çalıştırılır:

```
cd backend
pytest
```

Testler iki gruba ayrılır:

- **Veritabanı istemeyenler** — ayarlar, sağlık ucu, motor sınırı. Depo yeni klonlanmış ve Docker hiç çalıştırılmamış olsa bile geçerler.
- **Şema kısıt testleri** — ayrı bir test veritabanı (`<POSTGRES_DB>_test`) oluşturup migration'ları uygular, sonra kuralları bilerek ihlal edip veritabanının reddettiğini doğrular. Veritabanı çalışmıyorsa anlaşılır bir mesajla atlanırlar.

Kısıt testlerinin de çalışması için:

```
docker compose up -d db
cd backend
pytest
```

Motor sınırı (şartname Bölüm 5.1) testle korunur: `backend/engine/` altında FastAPI, SQLAlchemy, veritabanı veya HTTP kütüphanesi import edilirse `pytest` kırılır. Aynı kural yazarken uyarı versin diye `ruff` tarafında da tanımlıdır:

```
cd backend
ruff check .
ruff format .
```

İstemci tarafı:

```
cd app
flutter analyze
flutter test
```

## Demo verisi ve duman testi

Sahte bir etkinliği baştan sona kurar: kayıt, profiller, başvurular, onaylar, görüşme talepleri, eşleştirme ve yayınlama — hepsi gerçek uçlardan.

```
cd backend
python scripts/demo.py
```

Sonuna kadar gidiyorsa veritabanı, migration'lar, Redis, arka plan işçisi ve motor birlikte çalışıyor demektir. Yeni bir sunucuda kurulumu doğrulamanın en kısa yolu. Bitişte giriş bilgilerini ekrana yazar.

```
python scripts/demo.py --adres http://sunucu:8000 --katilimci 24 --tur 6
```

Her çalıştırma yeni bir etkinlik açar, var olan veriye dokunmaz. Arka plan işçisi çalışmıyorsa bunu açıkça söyler.

## Eşleştirme motorunu denemek

Motor bağımsızdır: veritabanı, sunucu veya arayüz olmadan, sentetik veriyle terminalden çalıştırılabilir.

```
cd backend
python -m engine.cli --katilimci 200 --slot 8 --masa 50 --sandalye 6
```

Rapor skor dağılımını, masa doluluğunu, kişi başı tur sayısını, süreleri ve kesin kural denetimini basar. Tüm düğmeler için `python -m engine.cli --help`.

Denenmeye değer birkaç senaryo:

```
python -m engine.cli --uyum 0.0            kimse kimseye uymuyor
python -m engine.cli --sirket 1            herkes aynı şirketten
python -m engine.cli --esik 0.20           kalite eşiği düşük
python -m engine.cli --deneme 200000       daha uzun yerel arama
```

## Telefondan test

Telefon ve bilgisayar aynı ağdaysa, uygulamayı bilgisayarın yerel ağ adresiyle derle:

```
flutter run --dart-define=API_BASE_URL=http://<bilgisayarin-yerel-ip-adresi>:8000
```

Yerel adres `ipconfig` (Windows) veya `ip addr` (Linux) ile bulunur. Sunucunun dışarıdan erişilebilmesi için `.env` içindeki `API_HOST` değeri `0.0.0.0` olmalıdır.

## Windows + WSL2 notu

Docker Desktop kullanılmıyorsa Docker, WSL2 dağıtımının içinde çalışır. `docker compose` komutları WSL kabuğundan çalıştırılır.

**Belirti:** Windows'ta çalışan backend bir süre sonra veritabanına ulaşamaz olur. `docker compose ps` konteynerlerin ayakta olduğunu söyler, WSL'in kendi IP adresinden Postgres'e bağlanılır, ama `localhost:5432` kapalıdır.

**Sebep:** WSL, açık bir `wsl.exe` oturumu kalmadığında dağıtımı "çalışmıyor" sayar (`wsl --list --running` boş döner) ve **localhost port yönlendirmesini kaldırır**. Dağıtımın kendisi ve konteynerler çalışmaya devam eder — yalnızca Windows'tan erişim kopar. Süre yaklaşık bir dakikadır.

**Çözüm:** Windows tarafında açık bir WSL oturumu tutulur. Oturum açılışında çalışan gizli bir zamanlanmış görev bu işi görür:

```powershell
$name = "B2X - WSL oturumunu acik tut"
# Oturum herhangi bir sebeple düşerse döngü yeniden açar. Bu şart:
# temiz çıkış, zamanlanmış görevin "yeniden dene" kuralı için hata sayılmaz.
$cmd = 'while ($true) { wsl.exe -d Ubuntu-22.04 -u root -- sleep infinity; Start-Sleep -Seconds 5 }'
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -Command `"$cmd`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings
Start-ScheduledTask -TaskName $name
```

Çalıştığı şuradan görülür — `Running` yazmalı, `Ready` değil:

```powershell
Get-ScheduledTask -TaskName "B2X - WSL oturumunu acik tut" | Select-Object State
```

Dağıtım adı farklıysa (`wsl --list` ile görülür) komut ona göre değiştirilir. Kaldırmak için:

```powershell
Unregister-ScheduledTask -TaskName "B2X - WSL oturumunu acik tut" -Confirm:$false
```

**Denenip işe yaramayanlar** — aynı yola tekrar girilmesin diye:

- `.wslconfig` içinde `vmIdleTimeout`. Sorun VM'in boşta kapanması değil, oturum kalmayınca yönlendirmenin kaldırılması. Değer yazılı bırakılabilir ama tek başına bir şey değiştirmez.
- Dağıtımın içinde çalışan bir keepalive servisi. Dağıtım zaten ölmüyor; Windows tarafındaki oturum eksik.
- `networkingMode=mirrored`. Yönlendiriciyi tamamen devreden çıkarır ama WSL trafiği Hyper-V güvenlik duvarına takılır; Windows'tan hiçbir servise ulaşılamaz. Açmak için `firewall=false` gerekir, bu da makinenin güvenlik ayarını düşürür.

Docker Desktop kurulu ve WSL entegrasyonu açıksa bu bölümün tamamı geçersizdir; `docker compose` doğrudan Windows'tan çalışır ve port yönlendirmesini Docker Desktop yönetir.

## Başka bir sunucuya kurulum

Projede sabit adres veya makineye özel ayar bulunmaz. Tüm yapılandırma `.env` dosyasından okunur.

Yeni bir sunucuya kurmak için: depoyu kopyala, `.env` dosyasını o ortama göre doldur, `docker compose up -d` çalıştır, migration'ları uygula.

Üretimde değiştirilmesi gerekenler: `APP_ENV`, `APP_DEBUG=false`, güçlü `POSTGRES_PASSWORD` ve `JWT_SECRET`, `CORS_ORIGINS` (yıldız yerine gerçek alan adları), `STORAGE_PUBLIC_BASE_URL`.

## iOS notu

Flutter kodu iOS'u destekler ancak iOS derlemesi macOS ve Xcode gerektirir. Proje Windows üzerinde geliştirildiği için iOS derlemesi yapılmamıştır. Mac erişimi olan bir ortamda `flutter build ios` ile derlenebilir.
