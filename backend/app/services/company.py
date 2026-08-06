"""Şirket adı normalleştirmesi ve tekilleştirme (şartname Bölüm 6).

Şartnamenin kritik notu: *"Aynı şirketten iki kişinin aynı masaya oturmaması
gerekiyor. Ama kullanıcılar şirket adını serbest metin girerse 'ABC Yazılım',
'ABC Yazılım A.Ş.', 'abc yazilim' ayrı şirket sanılır ve kural işlemez."*

Aşama 1'de `companies.normalized_name` benzersizliği kuruldu; normalleştirmenin
kendisi burada.

## Türkçe tuzağı

Python'un `str.lower()` metodu Türkçeye göre çalışmaz:

* `"I".lower()` → `"i"` verir, Türkçede `"ı"` olmalı.
* `"İ".lower()` → `"i"` + birleşen nokta üretir; tek karakter sanılan şey iki
  kod noktasıdır ve `"i"` ile eşleşmez.

Bu yüzden küçültme öncesinde iki harf elle çevriliyor.

## Hangi yöne yanılmak daha az zararlı

**Fazla normalleştirme** iki ayrı şirketi birleştirir: aslında farklı şirketlerden
iki kişi aynı masaya oturamaz hale gelir — gereksiz bir kısıt.

**Eksik normalleştirme** aynı şirketi ikiye böler: kural sessizce işlemez, iki iş
arkadaşı aynı masaya oturur — şartnamenin asıl korktuğu şey bu.

Bu yüzden yalnızca **tüzel kişilik biçimleri** atılıyor (`A.Ş.`, `Ltd. Şti.`,
`San. ve Tic.`). "Holding", "Grup" gibi tanımlayıcı kelimeler bırakılıyor: onlar
gerçekten farklı şirketleri ayırt edebiliyor.
"""

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company

# Küçültmeden önce elle çevrilen iki harf — gerekçesi modül başlığında.
_TURKISH_LOWERCASE = str.maketrans({"I": "ı", "İ": "i"})

# Karşılaştırma ASCII üzerinden yapılır: "Yazılım" ile "Yazilim" aynı şirket.
_ASCII_FOLD = str.maketrans(
    {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "â": "a",
        "î": "i",
        "û": "u",
    }
)

# Tüzel kişilik biçimleri ve ticaret unvanı ekleri. Yalnızca şirket türünü
# anlatan kelimeler — markayı anlatanlar değil.
_LEGAL_FORMS = frozenset(
    {
        "as",
        "anonim",
        "sirketi",
        "sirket",
        "ltd",
        "limited",
        "sti",
        "san",
        "sanayi",
        "tic",
        "ticaret",
        "ith",
        "ihr",
        "ithalat",
        "ihracat",
        "ve",
        "inc",
        "llc",
        "corp",
        "co",
        "gmbh",
        "bv",
        "sa",
        "srl",
        "plc",
    }
)

# Nokta ve kesme işareti kelime ayracı değil, kısaltma işaretidir: "A.Ş." tek bir
# kelimedir ("aş"), iki harf değil. Ayraç sayılsaydı "a" ve "s" olarak bölünür,
# tüzel kişilik eki listesiyle eşleşmez ve "ABC Yazılım A.Ş." ile "ABC Yazılım"
# ayrı şirket sanılırdı — şartnamenin tam da uyardığı hata.
_ABBREVIATION_MARKS = re.compile(r"[.'’]")

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalize_company_name(name: str) -> str:
    """Şirket adını karşılaştırılabilir hale getirir.

    Örnek: `"ABC Yazılım San. ve Tic. A.Ş."` → `"abc yazilim"`
    """
    folded = _fold(name)
    tokens = [token for token in folded.split() if token]

    meaningful = [token for token in tokens if token not in _LEGAL_FORMS]

    # Ad tamamen tüzel kişilik eklerinden oluşuyorsa (örneğin yalnızca "A.Ş."
    # yazılmışsa) elde kalan hiçbir şey olmaz. Böyle bir durumda ekleri atmadan
    # önceki hâle dönmek, her şeyi tek bir boş kimliğe toplamaktan iyidir.
    return " ".join(meaningful) if meaningful else " ".join(tokens)


def _fold(name: str) -> str:
    """Büyük-küçük harf, Türkçe karakter ve noktalamayı tekdüzeleştirir."""
    text = unicodedata.normalize("NFKC", name)
    text = _ABBREVIATION_MARKS.sub("", text)
    text = text.translate(_TURKISH_LOWERCASE).lower()
    text = text.translate(_ASCII_FOLD)
    # Kalan aksanlar (ör. kopyala-yapıştır ile gelen) ayrıştırılıp atılır.
    text = "".join(
        character
        for character in unicodedata.normalize("NFD", text)
        if not unicodedata.combining(character)
    )
    return _NON_ALPHANUMERIC.sub(" ", text).strip()


async def find_or_create_company(session: AsyncSession, name: str) -> Company:
    """Şirketi normalleştirilmiş adıyla bulur, yoksa oluşturur.

    Bölüm 10 kabul kriteri: *"Şirket adı seçildiğinde mevcut şirketlerle
    eşleşiyor, aynı şirket iki kez oluşturulmuyor."*

    İki kullanıcı aynı anda aynı şirketi girebilir. Benzersizlik kısıtı ikincisini
    reddeder; o durumda hata yüzeye çıkarılmaz, mevcut kayıt döndürülür. Kontrol
    ile ekleme arasındaki yarışı kapatmanın tek güvenli yolu bu.
    """
    display_name = name.strip()
    if not display_name:
        raise ValueError("Şirket adı boş olamaz.")

    normalized = normalize_company_name(display_name)
    existing = await _get_by_normalized_name(session, normalized)
    if existing is not None:
        return existing

    company = Company(name=display_name, normalized_name=normalized)
    try:
        # İç işlem (savepoint): çakışma olursa yalnızca bu ekleme geri alınır,
        # çağıranın oturumundaki diğer değişiklikler ayakta kalır.
        async with session.begin_nested():
            session.add(company)
    except IntegrityError:
        conflicting = await _get_by_normalized_name(session, normalized)
        if conflicting is None:
            raise
        return conflicting

    return company


async def _get_by_normalized_name(session: AsyncSession, normalized: str) -> Company | None:
    result = await session.execute(select(Company).where(Company.normalized_name == normalized))
    return result.scalar_one_or_none()


async def search_companies(session: AsyncSession, query: str, limit: int = 10) -> list[Company]:
    """Yazarken öneri için arama (Bölüm 6).

    Arama da normalleştirilmiş ad üzerinden yapılır: kullanıcı "abc yazilim"
    yazınca "ABC Yazılım A.Ş." çıkmalı.
    """
    normalized = normalize_company_name(query)
    if not normalized:
        return []

    result = await session.execute(
        select(Company)
        .where(Company.normalized_name.like(f"%{normalized}%"))
        .order_by(Company.normalized_name)
        .limit(limit)
    )
    return list(result.scalars())
