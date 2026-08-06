"""Şirket adı normalleştirmesi (şartname Bölüm 6).

*"'ABC Yazılım', 'ABC Yazılım A.Ş.', 'abc yazilim' ayrı şirket sanılır ve kural
işlemez."* Aynı şirketten iki kişinin aynı masaya oturmaması kuralının tamamı
buraya dayanıyor — motor karşılaştırmayı şirket kimliğiyle yapıyor, kimliği de
bu fonksiyon belirliyor.

Bu testler veritabanı istemez.
"""

import pytest

from app.services.company import normalize_company_name


def test_spec_example_collapses_to_one_identity() -> None:
    """Şartnamenin verdiği üç yazım tek kimliğe düşmeli."""
    variants = ["ABC Yazılım", "ABC Yazılım A.Ş.", "abc yazilim"]
    normalized = {normalize_company_name(variant) for variant in variants}
    assert len(normalized) == 1, f"ayrı kimliklere düştü: {normalized}"


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("ABC Yazılım", "abc yazilim"),
        ("ABC Yazılım A.Ş.", "abc yazilim"),
        ("ABC Yazılım Ltd. Şti.", "abc yazilim"),
        ("ABC Yazılım San. ve Tic. A.Ş.", "abc yazilim"),
        ("  ABC   YAZILIM  ", "abc yazilim"),
        ("ABC-Yazılım", "abc yazilim"),
        ("ABC Yazılım İthalat İhracat", "abc yazilim"),
    ],
)
def test_common_turkish_trade_name_forms(written: str, expected: str) -> None:
    assert normalize_company_name(written) == expected


def test_dotted_capital_i_folds_to_plain_i() -> None:
    """`"İ".lower()` Python'da i + birleşen nokta üretir; elle çevriliyor."""
    assert normalize_company_name("İNŞAAT") == "insaat"
    assert normalize_company_name("İnşaat") == normalize_company_name("insaat")


def test_dotless_capital_i_folds_like_turkish() -> None:
    """`"I".lower()` Python'da "i" verir; Türkçede "ı" olmalı.

    İkisi de ASCII'de "i"ye katlandığı için sonuç aynı yere düşüyor — asıl önemli
    olan iki yazımın ayrışmaması.
    """
    assert normalize_company_name("IŞIK") == normalize_company_name("Işık")
    assert normalize_company_name("IŞIK") == "isik"


def test_all_turkish_letters_fold_to_ascii() -> None:
    assert normalize_company_name("ÇĞİÖŞÜ çğıöşü") == "cgiosu cgiosu"


def test_brand_words_are_not_stripped() -> None:
    """Fazla normalleştirme iki ayrı şirketi birleştirir — daha az zararlı olan
    yön bu değil. "Holding" ve "Grup" gerçekten şirket ayırt edebiliyor."""
    assert normalize_company_name("ABC Holding") != normalize_company_name("ABC")
    assert normalize_company_name("ABC Grup") != normalize_company_name("ABC")


def test_different_companies_stay_apart() -> None:
    assert normalize_company_name("ABC Yazılım") != normalize_company_name("ABD Yazılım")
    assert normalize_company_name("ABC Yazılım") != normalize_company_name("ABC Tekstil")


def test_name_made_only_of_legal_forms_is_not_emptied() -> None:
    """Her şey atılırsa tüm şirketler tek bir boş kimliğe toplanırdı."""
    assert normalize_company_name("A.Ş.") != ""
    assert normalize_company_name("Ltd. Şti.") != ""
    assert normalize_company_name("A.Ş.") != normalize_company_name("Ltd. Şti.")


def test_punctuation_and_symbols_do_not_split_identities() -> None:
    assert normalize_company_name("A&B Danışmanlık") == normalize_company_name("A B Danismanlik")


def test_empty_input_yields_empty_result() -> None:
    assert normalize_company_name("   ") == ""
