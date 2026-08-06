"""Plana hesabın durumu: kuyrukta / çalışıyor / bitti / hata.

Şartname 5.4: *"Organizatör 'eşleştir' dediğinde iş kuyruğa atılır, ekranda
durum gösterilir, bitince sonuç gelir. İşin durumu takip edilebilir olmalı:
kuyrukta / çalışıyor / bitti / hata."*

Bölüm 6'daki `plans` alan listesinde böyle bir alan yok; 5.4'ün gereği olarak
ekleniyor. Şartname Bölüm 6 ayrıntı seviyesini kendisi de "uygulama sırasında
netleşir" diye işaretliyor.

## Neden plan durumundan ayrı

`status` (taslak / yayında / arşiv) **planın** durumu, `job_status`
**hesabın**. İkisi bağımsız: hesabı bitmiş bir plan hâlâ taslaktır,
organizatör inceleyip yayınlayana kadar öyle kalır.

İkisini tek alanda toplamak Bölüm 13'ün "plan görünürlüğünü etkinlik
durumundan okumak" hatasının kardeşi olurdu.

Plan satırı iş **kuyruğa girer girmez** oluşuyor, motor sonra çalışıyor. O
aralıkta plan var ama içi boş — özet alanları bu yüzden Aşama 1'den beri boş
geçilebilir.

Yeni CHECK kısıtı: hesabı bitmemiş plan yayınlanamaz. Yarım bir planı
katılımcıya göstermek Bölüm 7'yi ihlal ederdi.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column(
            "job_status",
            sa.Enum("queued", "running", "done", "failed", name="job_status", native_enum=False),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
    )
    op.add_column("plans", sa.Column("job_error", sa.Text(), nullable=True))
    op.add_column("plans", sa.Column("job_id", sa.String(length=64), nullable=True))

    op.create_check_constraint(
        op.f("ck_plans_job_status"),
        "plans",
        "job_status IN ('queued', 'running', 'done', 'failed')",
    )
    op.create_check_constraint(
        op.f("ck_plans_published_needs_finished_job"),
        "plans",
        "status <> 'published' OR job_status = 'done'",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_plans_published_needs_finished_job"), "plans", type_="check")
    op.drop_constraint(op.f("ck_plans_job_status"), "plans", type_="check")
    op.drop_column("plans", "job_id")
    op.drop_column("plans", "job_error")
    op.drop_column("plans", "job_status")
