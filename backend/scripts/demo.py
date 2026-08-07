"""Sahte bir etkinliği baştan sona kurar (şartname Aşama 12).

Kayıttan yayınlanmış plana kadar her adımı **gerçek uçlardan** geçirir.
Amacı iki türlü:

* **Duman testi.** Yeni kurulan bir sunucuda çalışıyorsa veritabanı,
  migration'lar, Redis, arka plan işçisi ve motor birlikte çalışıyor demektir.
  Kurulumu doğrulamanın en kısa yolu.
* **Demo verisi.** Arayüzü ilk kez açan biri boş bir ekranla karşılaşmasın.

Veritabanına doğrudan yazmıyor: HTTP üzerinden gidiyor ki gerçekten uçtan uca
olsun. Bu yüzden sunucunun (ve eşleştirme için arka plan işçisinin) ayakta
olması gerekir.

Kullanım:

    python scripts/demo.py
    python scripts/demo.py --adres http://sunucu:8000 --katilimci 24 --tur 6

Her çalıştırma **yeni bir etkinlik** açar; organizatör hesabı ilk çalıştırmada
oluşturulur, sonrakilerde aynısı kullanılır. Var olan veriye dokunmaz.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx

PASSWORD = "demo-sifresi-1234"
ORGANISER = "demo-organizator@ornek.com"

# Katılımcılar iki gruba ayrılıyor: sunanlar ve arayanlar. Böylece sinerji
# skoru gerçekten çalışıyor ve gerekçe cümleleri boş çıkmıyor (9.3, M8).
FIRST_NAMES = [
    "Ayşe",
    "Mehmet",
    "Zeynep",
    "Ahmet",
    "Elif",
    "Mustafa",
    "Fatma",
    "Emre",
    "Selin",
    "Burak",
    "Deniz",
    "Kaan",
    "Merve",
    "Cem",
    "Aslı",
    "Ozan",
    "Pınar",
    "Tolga",
    "Ece",
    "Serkan",
    "Gül",
    "Barış",
    "Nil",
    "Hakan",
]
LAST_NAMES = [
    "Yılmaz",
    "Demir",
    "Kaya",
    "Çelik",
    "Şahin",
    "Arslan",
    "Doğan",
    "Koç",
    "Aydın",
    "Öztürk",
    "Kurt",
    "Özdemir",
    "Aslan",
    "Çetin",
    "Kara",
    "Polat",
    "Erdoğan",
    "Yıldız",
    "Güneş",
    "Bulut",
    "Taş",
    "Ateş",
    "Deniz",
    "Akın",
]
CITIES = ["İzmir", "Bursa", "Ankara", "İstanbul", "Gaziantep", "Konya"]


class Demo:
    def __init__(self, base_url: str) -> None:
        # Windows konsolu cp1254 ile açılıyor ve çıktıdaki "↔" gibi işaretleri
        # kodlayamayıp betiği sonlandırıyor.
        for stream in (sys.stdout, sys.stderr):
            stream.reconfigure(encoding="utf-8", errors="replace")

        self.client = httpx.Client(base_url=base_url, timeout=60.0)
        self.base_url = base_url

    # --- Yardımcılar ---------------------------------------------------------

    def _use(self, token: str) -> None:
        self.client.headers["Authorization"] = f"Bearer {token}"

    def _post(self, path: str, **kwargs) -> dict:
        response = self.client.post(path, **kwargs)
        self._check(response)
        return response.json()

    def _get(self, path: str, **kwargs):
        response = self.client.get(path, **kwargs)
        self._check(response)
        return response.json()

    @staticmethod
    def _check(response: httpx.Response) -> None:
        if response.is_success:
            return
        raise SystemExit(
            f"\n{response.request.method} {response.request.url} "
            f"→ {response.status_code}\n{response.text}\n"
        )

    def _sign_in_or_up(self, email: str) -> str:
        """Hesap varsa girer, yoksa açar.

        Betik tekrar tekrar çalıştırılabilmeli: ikinci çalıştırmada
        organizatör zaten var ve kayıt 409 döner.
        """
        response = self.client.post("/auth/register", json={"email": email, "password": PASSWORD})
        if response.status_code == 409:
            response = self.client.post("/auth/login", json={"email": email, "password": PASSWORD})
        self._check(response)
        return response.json()["access_token"]

    # --- Adımlar -------------------------------------------------------------

    def check_server(self) -> None:
        health = self._get("/health/ready")
        broken = [name for name, state in health["checks"].items() if state != "ok"]
        if broken:
            raise SystemExit(f"Sunucu hazır değil: {', '.join(broken)}")
        print(f"sunucu     {self.base_url} · veritabanı ve redis erişilebilir")

    def create_organiser(self) -> str:
        token = self._sign_in_or_up(ORGANISER)
        self._use(token)
        company = self._post("/companies", json={"name": "Demo Fuarcılık A.Ş."})
        sector_id = self._get("/sectors")[0]["id"]
        self.client.patch(
            "/profile",
            json={
                "full_name": "Demo Organizatör",
                "title": "Etkinlik Koordinatörü",
                "company_id": company["id"],
                "sector_id": sector_id,
                "city": "İzmir",
            },
        )
        print(f"organizatör {ORGANISER} · şifre {PASSWORD}")
        return token

    def create_event(self, *, slots: int, tables: int, seats: int, capacity: int) -> dict:
        starts_at = (datetime.now(UTC) + timedelta(days=30)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        event = self._post(
            "/events",
            json={
                "name": f"Demo Buluşması {datetime.now().strftime('%d.%m %H:%M')}",
                "starts_at": starts_at.isoformat(),
                "slot_count": slots,
                "capacity": capacity,
            },
        )
        self.client.patch(
            f"/events/{event['id']}",
            json={
                "location": "İzmir Ticaret Odası",
                "description": "Tedarikçilerle alıcıları bir araya getiren buluşma.",
                "request_quota": 3,
                # Otomatik onay kapatılıyor: duman testi onay uçlarından da
                # geçsin. Varsayılan açık.
                "auto_approve_registrations": False,
            },
        )
        layout = self.client.put(
            f"/events/{event['id']}/layout/auto",
            json={"kind": "seated", "table_count": tables, "seat_count": seats},
        )
        self._check(layout)
        opened = self._post(f"/events/{event['id']}/open-registration")
        print(f"etkinlik   #{event['id']} · {slots} tur · {tables} masa × {seats} sandalye")
        return opened

    def create_participants(self, event: dict, count: int) -> list[tuple[str, str]]:
        """Profili tamamlanmış katılımcılar açar ve başvurtur.

        Dönen liste (ad, e-posta) ikilileri; ekrana yazılıyor ki demoyu
        gezen kişi bir katılımcı olarak da girebilsin.
        """
        organiser = self.client.headers["Authorization"]
        categories = self._get("/tag-categories")
        sectors = self._get("/sectors")
        # Etiketler iki havuza bölünüyor: bir grup sunuyor, diğeri arıyor.
        tags = [tag["id"] for category in categories for tag in category["tags"]]
        half = len(tags) // 2
        offered_pool, sought_pool = tags[:half], tags[half:]

        people = []
        for index in range(count):
            name = f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[index % len(LAST_NAMES)]}"
            email = f"demo-{uuid.uuid4().hex[:8]}@ornek.com"
            self._use(self._sign_in_or_up(email))

            supplier = index % 2 == 0
            company = self._post("/companies", json={"name": f"{name.split()[-1]} Ticaret"})
            offered = offered_pool if supplier else sought_pool
            sought = sought_pool if supplier else offered_pool
            step = (index * 3) % max(len(offered) - 3, 1)
            self.client.patch(
                "/profile",
                json={
                    "full_name": name,
                    "title": "Dış Ticaret Müdürü" if supplier else "Satın Alma Müdürü",
                    "company_id": company["id"],
                    "sector_id": sectors[index % len(sectors)]["id"],
                    "city": CITIES[index % len(CITIES)],
                    "bio": f"{name.split()[-1]} Ticaret olarak on yıldır bu işi yapıyoruz.",
                    "offered_tag_ids": offered[step : step + 3],
                    "sought_tag_ids": sought[step : step + 3],
                },
            )
            self._post(f"/events/{event['id']}/registration")
            people.append((name, email))

        self.client.headers["Authorization"] = organiser
        print(f"katılımcı  {count} kişi başvurdu")
        return people

    def approve_everyone(self, event: dict) -> None:
        pending = self._get(f"/events/{event['id']}/registrations", params={"status": "pending"})
        rows = pending["registrations"]
        if not rows:
            raise SystemExit("Onaylanacak başvuru yok — kayıtlar açılmamış olabilir.")
        for row in rows:
            self._post(f"/events/{event['id']}/registrations/{row['id']}/approve")
        print(f"onay       {len(rows)} başvuru kabul edildi")

    def send_requests(self, event: dict, people: list[tuple[str, str]]) -> int:
        """Birkaç görüşme talebi — biri karşılıklı (M9).

        Karşılıklı talep olmadan hem talep bonusu hem de katılımcının gördüğü
        *"İkiniz de görüşmek istemiştiniz"* gerekçesi hiç tetiklenmez.
        """
        if len(people) < 4:
            return 0

        organiser = self.client.headers["Authorization"]
        sent = 0

        def registration_ids() -> dict[str, int]:
            listing = self._get(f"/events/{event['id']}/participants")
            return {row["full_name"]: row["registration_id"] for row in listing["participants"]}

        first, second, third = people[0], people[1], people[2]
        for sender, targets in ((first, [second, third]), (second, [first])):
            self._use(self._sign_in_or_up(sender[1]))
            ids = registration_ids()
            for target in targets:
                target_id = ids.get(target[0])
                if target_id is None:
                    continue
                response = self.client.post(
                    f"/events/{event['id']}/requests",
                    json={"target_registration_id": target_id},
                )
                if response.is_success:
                    sent += 1

        self.client.headers["Authorization"] = organiser
        print(f"talep      {sent} görüşme talebi ({first[0]} ↔ {second[0]} karşılıklı)")
        return sent

    def run_matching(self, event: dict) -> dict:
        started = self._post(f"/events/{event['id']}/plans", json={})
        plan_id = started["id"]

        deadline = datetime.now(UTC) + timedelta(seconds=90)
        while datetime.now(UTC) < deadline:
            plan = self._get(f"/events/{event['id']}/plans/{plan_id}")
            if plan["job_status"] == "done":
                print(
                    f"eşleştirme versiyon {plan['version']} · "
                    f"{plan['total_meetings']} görüşme · "
                    f"en az {plan['min_meetings_per_person']} tur · "
                    f"{plan['runtime_ms']} ms"
                )
                return plan
            if plan["job_status"] == "failed":
                raise SystemExit(f"Eşleştirme başarısız: {plan['job_error']}")

        raise SystemExit(
            "Eşleştirme kuyrukta kaldı. Arka plan işçisi çalışıyor mu?\n"
            "  cd backend && arq app.worker.WorkerSettings"
        )

    def publish(self, event: dict, plan: dict) -> None:
        self._post(f"/events/{event['id']}/plans/{plan['id']}/publish")
        print("yayın      plan yayında, katılımcılar kendi masalarını görüyor")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sahte bir etkinliği baştan sona kurar ve planı yayınlar."
    )
    parser.add_argument("--adres", default="http://127.0.0.1:8000", help="Sunucu adresi")
    parser.add_argument("--katilimci", type=int, default=16, help="Katılımcı sayısı")
    parser.add_argument("--tur", type=int, default=5, help="Tur sayısı")
    parser.add_argument("--masa", type=int, default=6, help="Masa sayısı")
    parser.add_argument("--sandalye", type=int, default=6, help="Masa başına sandalye")
    args = parser.parse_args()

    demo = Demo(args.adres)
    demo.check_server()
    demo.create_organiser()
    event = demo.create_event(
        slots=args.tur,
        tables=args.masa,
        seats=args.sandalye,
        capacity=args.katilimci,
    )
    people = demo.create_participants(event, args.katilimci)
    demo.approve_everyone(event)
    demo.send_requests(event, people)
    plan = demo.run_matching(event)
    demo.publish(event, plan)

    print()
    print("Giriş bilgileri — şifre hepsinde aynı:", PASSWORD)
    print(f"  organizatör  {ORGANISER}")
    for name, email in people[:3]:
        print(f"  katılımcı    {email}  ({name})")
    if len(people) > 3:
        print(f"  ... ve {len(people) - 3} kişi daha")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
