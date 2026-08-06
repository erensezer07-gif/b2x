"""Motor sınırının makine tarafından denetlenmesi.

Şartname Bölüm 5.1: `backend/engine/` paketi FastAPI, SQLAlchemy, veritabanı ve
HTTP bilmez; yalnızca standart kütüphane ve NumPy kullanır.

Bu kural yoruma bırakılmaz. Buradaki testler engine/ altındaki her Python
dosyasını ayrıştırır ve yasaklı bir modülün import edildiğini görürse kırılır.
Şartname Bölüm 13: "Motora veritabanı erişimi vermek" listedeki en pahalı hata —
projenin en değerli parçası test edilemez hale gelir.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENGINE_DIR = BACKEND_DIR / "engine"

# Anahtar: yasaklı üst düzey modül. Değer: neden yasak olduğunun açıklaması —
# test kırıldığında geliştirici sebebi de görür.
FORBIDDEN_IMPORTS = {
    "fastapi": "Motor HTTP bilmez.",
    "starlette": "Motor HTTP bilmez.",
    "sqlalchemy": "Motor veritabanı bilmez.",
    "alembic": "Motor veritabanı bilmez.",
    "asyncpg": "Motor veritabanı bilmez.",
    "psycopg": "Motor veritabanı bilmez.",
    "redis": "Motor kuyruk bilmez.",
    "arq": "Motor kuyruk bilmez.",
    "httpx": "Motor ağ çağrısı yapmaz.",
    "requests": "Motor ağ çağrısı yapmaz.",
    "pydantic": "Motor girdisini sade veri yapısı olarak alır (şartname 9.2).",
    "pydantic_settings": "Motor ayarlarını dışarıdan alır, ortamdan okumaz.",
    "app": "Bağımlılık ters yönde olamaz: app motoru çağırır, motor app'i çağıramaz.",
}

# B2X'e ait tüm ortam değişkeni önekleri. Motorun bunların hiçbirine ihtiyacı
# olmamalı; alt süreç testi bu değişkenleri silerek çalışır.
SETTINGS_PREFIXES = (
    "APP_",
    "API_",
    "CORS_",
    "POSTGRES_",
    "REDIS_",
    "JWT_",
    "STORAGE_",
    "MATCHING_",
    "REQUEST_",
)


def _imported_root_modules(source: str) -> set[str]:
    """Bir dosyanın import ettiği üst düzey modül adlarını çıkarır."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # node.level > 0 ise göreli import, yani paketin kendi içi — serbest.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_engine_does_not_import_forbidden_modules() -> None:
    violations: list[str] = []

    for path in sorted(ENGINE_DIR.rglob("*.py")):
        roots = _imported_root_modules(path.read_text(encoding="utf-8"))
        for root in sorted(roots & FORBIDDEN_IMPORTS.keys()):
            relative = path.relative_to(BACKEND_DIR).as_posix()
            violations.append(f"  {relative}: '{root}' — {FORBIDDEN_IMPORTS[root]}")

    assert not violations, "Motor sınırı ihlal edildi (şartname Bölüm 5.1):\n" + "\n".join(
        violations
    )


def test_engine_imports_without_application_environment() -> None:
    """Motor, hiçbir B2X ayarı tanımlı değilken de import edilebilmeli.

    Bu, sınırın gerçekten işlediğinin kanıtı: motor ayrı bir makinede, ortam
    dosyası olmadan, sentetik veriyle çalıştırılabilir olmalı.
    """
    clean_env = {
        key: value for key, value in os.environ.items() if not key.startswith(SETTINGS_PREFIXES)
    }

    result = subprocess.run(
        [sys.executable, "-c", "import engine"],
        cwd=BACKEND_DIR,
        env=clean_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        "Motor, uygulama ortamı olmadan import edilemedi:\n" + result.stderr
    )
