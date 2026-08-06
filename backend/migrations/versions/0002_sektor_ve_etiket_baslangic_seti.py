"""Sektör ve etiket havuzunun başlangıç seti.

Şartname Bölüm 12 bu içeriği açık karar olarak işaretliyordu: *"Etiket havuzunun
içeriği: kaç kategori, her kategoride hangi etiketler"* ve *"Sektör listesinin
içeriği"*. Buradaki liste bir **başlangıç setidir** — gerçek etkinlik verisiyle
ayarlanacak, nihai değildir.

İçerik neden migration'da: kullanıcı serbest metin yazamıyor, kategorileri
gezerek seçiyor (Bölüm 6). Havuz boşsa profil sihirbazının "ne sunuyorum" ve
"ne arıyorum" adımları hiç çalışmaz, dolayısıyla eşleştirmenin girdisi de oluşmaz.

Etiketler **tek havuz**: "ne sunuyorum" ve "ne arıyorum" aynı listeden seçilir.
Sinerji hesabının temeli bu — A'nın sunduğu ile B'nin aradığı aynı etikete denk
gelmezse karşılaştırma yapılamaz (Bölüm 6, 9.3).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SECTORS = (
    "Bilişim ve yazılım",
    "Finans ve bankacılık",
    "Sigorta",
    "Otomotiv",
    "Tekstil ve hazır giyim",
    "Gıda ve içecek",
    "İnşaat ve gayrimenkul",
    "Enerji",
    "Kimya ve ilaç",
    "Makine ve metal",
    "Lojistik ve taşımacılık",
    "Perakende ve e-ticaret",
    "Turizm ve konaklama",
    "Sağlık",
    "Eğitim",
    "Tarım ve hayvancılık",
    "Medya ve reklam",
    "Danışmanlık ve hukuk",
)

# (kategori, (etiketler...))
TAG_CATALOGUE = (
    (
        "Yazılım ve teknoloji",
        (
            "Mobil uygulama geliştirme",
            "Web yazılımı geliştirme",
            "ERP kurulumu ve entegrasyonu",
            "Veri analitiği ve raporlama",
            "Yapay zekâ çözümleri",
            "Siber güvenlik",
            "Bulut altyapısı",
            "E-ticaret altyapısı",
        ),
    ),
    (
        "Finansman ve yatırım",
        (
            "Melek yatırım",
            "Girişim sermayesi",
            "Banka kredisi ve finansman",
            "Devlet teşviki ve hibe",
            "Şirket satın alma ve birleşme",
            "Faktoring ve leasing",
            "Mali müşavirlik",
            "Yatırımcı ilişkileri",
        ),
    ),
    (
        "Üretim ve tedarik",
        (
            "Fason üretim",
            "Hammadde tedariki",
            "Ambalaj ve paketleme",
            "Kalite kontrol ve belgelendirme",
            "Makine ve ekipman",
            "Kalıp ve döküm",
            "Ar-Ge ve ürün geliştirme",
            "Yedek parça",
        ),
    ),
    (
        "Lojistik ve dağıtım",
        (
            "Yurt içi nakliye",
            "Uluslararası taşımacılık",
            "Depolama ve antrepo",
            "Gümrük müşavirliği",
            "Soğuk zincir",
            "Son kilometre teslimat",
            "İhracat operasyonu",
            "İthalat operasyonu",
        ),
    ),
    (
        "Danışmanlık ve hizmet",
        (
            "Yönetim danışmanlığı",
            "Hukuk danışmanlığı",
            "İnsan kaynakları",
            "Eğitim ve kurumsal gelişim",
            "Süreç iyileştirme",
            "Sürdürülebilirlik danışmanlığı",
            "Dijital dönüşüm",
            "Bağımsız denetim",
        ),
    ),
    (
        "Pazarlama ve satış",
        (
            "Dijital pazarlama",
            "Marka ve kurumsal kimlik",
            "Bayilik ve distribütörlük",
            "İhracat pazarlaması",
            "Sosyal medya yönetimi",
            "Halkla ilişkiler",
            "Pazar araştırması",
            "Satış kanalı geliştirme",
        ),
    ),
)


def upgrade() -> None:
    """Başlangıç setini yükler."""
    connection = op.get_bind()

    for order, name in enumerate(SECTORS):
        connection.execute(
            sa.text("INSERT INTO sectors (name, sort_order) VALUES (:name, :sort_order)"),
            {"name": name, "sort_order": order},
        )

    for category_order, (category_name, tags) in enumerate(TAG_CATALOGUE):
        category_id = connection.execute(
            sa.text(
                "INSERT INTO tag_categories (name, sort_order) "
                "VALUES (:name, :sort_order) RETURNING id"
            ),
            {"name": category_name, "sort_order": category_order},
        ).scalar_one()

        for tag_order, tag_name in enumerate(tags):
            connection.execute(
                sa.text(
                    "INSERT INTO tags (category_id, name, sort_order) "
                    "VALUES (:category_id, :name, :sort_order)"
                ),
                {
                    "category_id": category_id,
                    "name": tag_name,
                    "sort_order": tag_order,
                },
            )


def downgrade() -> None:
    """Başlangıç setini kaldırır.

    Yalnızca bu migration'ın eklediği adlar siliniyor; sonradan elle eklenmiş
    kategoriler, etiketler ve sektörler yerinde kalıyor.
    """
    connection = op.get_bind()

    tag_names = [tag for _category, tags in TAG_CATALOGUE for tag in tags]
    category_names = [category for category, _tags in TAG_CATALOGUE]

    connection.execute(
        sa.text("DELETE FROM tags WHERE name = ANY(:names)"), {"names": tag_names}
    )
    connection.execute(
        sa.text("DELETE FROM tag_categories WHERE name = ANY(:names)"),
        {"names": category_names},
    )
    connection.execute(
        sa.text("DELETE FROM sectors WHERE name = ANY(:names)"), {"names": list(SECTORS)}
    )
