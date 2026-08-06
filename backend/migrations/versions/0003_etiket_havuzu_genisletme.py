"""Etiket havuzunu 48'den 72'ye çıkarır.

Şartname Bölüm 12 havuzu *"başlangıç seti — gerçek etkinlik verisiyle
ayarlanacak"* diye işaretlemişti; bu o ayarlamanın ilk adımı.

## Neden tam 72

Havuz büyüdükçe iki kişinin ortak etiket bulma olasılığı düşüyor: beklenen
kesişim kabaca `seçim² ÷ havuz`. Kişi başı asgari seçim 3 (M2) sabit kaldığı
için havuzun bir tavanı var. Motor sentetik veriyle ölçüldü, 200 katılımcı /
8 tur / 50 masa, aynı tohum:

    havuz   ortalama masa skoru
    48      0.353   (önceki hâl)
    60      0.315
    72      0.337   ← son sağlam nokta
    84      0.095   ← çöküş
    96      0.063

84'te masaların dörtte üçünde en zayıf bağ sıfıra düşüyor: masaya birbirine
hiç uymayan insanlar oturuyor. 72 sınırın hemen altında.

Daha büyük bir havuz istenirse iki yol var, ikisi de bu migration'ın işi değil:
kişi başı asgari seçimi yükseltmek (M2 değişikliği) ya da motora kategori
düzeyinde kısmi puan eklemek (9.3 değişikliği). İkincisi tercih edilir —
kullanıcıdan fazlasını istemez ve yakın eş anlamlı etiket sorununu da çözer.

## Neden yalnızca ekleme var

`profile_tags` etiket **kimliğine** bakıyor. Etiket eklemek ve adını düzeltmek
bedava; silmek o etiketi seçmiş profilleri etkiler. Bu yüzden 0002'deki hiçbir
kayda dokunulmuyor, üç yeni kategori ekleniyor.

## Neden kategoriler işleve göre, sektöre göre değil

0002'deki kalıp korunuyor: tekstilci de gıdacı da "ambalaj" arar. İşlevsel
kategoriler havuzu küçük tutuyor — sektörel olsaydı her sektör kendi etiket
setini isterdi ve tavanı çoktan aşardık.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 0002'deki altı kategoriden sonra gelirler; sıra numaraları oradan devam eder.
FIRST_SORT_ORDER = 6

# (kategori, (etiketler...))
NEW_CATEGORIES = (
    (
        "Dış ticaret",
        (
            "Ülke pazarına giriş",
            "Yurt dışı temsilcilik",
            "İhracat finansmanı",
            "Uluslararası sertifikasyon",
            "Fuar ve organizasyon",
            "Dış ticaret mevzuatı",
            "Yurt dışı tedarikçi bulma",
            "Ürün yerelleştirme",
        ),
    ),
    (
        "Enerji ve sürdürülebilirlik",
        (
            "Güneş enerjisi kurulumu",
            "Enerji verimliliği",
            "Atık yönetimi ve geri dönüşüm",
            "Karbon ayak izi hesaplama",
            "Yeşil sertifikasyon",
            "Su ve arıtma",
            "Enerji tedariki",
            "Sürdürülebilir ambalaj",
        ),
    ),
    (
        "Tasarım ve mühendislik",
        (
            "Endüstriyel tasarım",
            "Mimari ve iç mekân projesi",
            "Mühendislik hizmeti",
            "Prototipleme ve 3D baskı",
            "Teknik çizim ve CAD",
            "Tersine mühendislik",
            "Test ve simülasyon",
            "Patent ve fikri mülkiyet",
        ),
    ),
)


def upgrade() -> None:
    connection = op.get_bind()

    for offset, (category_name, tags) in enumerate(NEW_CATEGORIES):
        category_id = connection.execute(
            sa.text(
                "INSERT INTO tag_categories (name, sort_order) "
                "VALUES (:name, :sort_order) RETURNING id"
            ),
            {"name": category_name, "sort_order": FIRST_SORT_ORDER + offset},
        ).scalar_one()

        for tag_order, tag_name in enumerate(tags):
            connection.execute(
                sa.text(
                    "INSERT INTO tags (category_id, name, sort_order) "
                    "VALUES (:category_id, :name, :sort_order)"
                ),
                {"category_id": category_id, "name": tag_name, "sort_order": tag_order},
            )


def downgrade() -> None:
    """Yalnızca bu migration'ın eklediklerini kaldırır.

    Etiketi seçmiş bir profil varsa `profile_tags` yabancı anahtarı silmeyi
    engeller ve geri alma hata verir. Bu **bilinçli**: sessizce veri kaybetmek
    yerine durup uyarması doğru.
    """
    connection = op.get_bind()

    tag_names = [tag for _category, tags in NEW_CATEGORIES for tag in tags]
    category_names = [category for category, _tags in NEW_CATEGORIES]

    connection.execute(sa.text("DELETE FROM tags WHERE name = ANY(:names)"), {"names": tag_names})
    connection.execute(
        sa.text("DELETE FROM tag_categories WHERE name = ANY(:names)"),
        {"names": category_names},
    )
