"""Minimum degisim bayragi (sartname 9.8, M10).

Check-in sonrasi calistirmada motor onceki plani baslangic noktasi olarak
aliyor. `previous_plan_id` bunu soylemiyor: her plan bir oncekinden turuyor
ama yalnizca bu modda onceki plan **baslangic** oluyor.

Karar is kuyruga girerken veriliyor, isci bu alani okuyor — istek govdesi o
noktada elde degil.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column(
            "minimal_change",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("plans", "minimal_change")
