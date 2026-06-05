"""Force drop video_type again

Revision ID: 009_force_drop_video_type
Revises: 621bf7ebb607
Create Date: 2026-06-05 07:40:28.042578
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_force_drop_video_type'
down_revision: Union[str, None] = '621bf7ebb607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "news_articles" not in insp.get_table_names():
        return

    columns = {col["name"]: col for col in insp.get_columns("news_articles")}

    if "video_type" in columns:
        try:
            op.execute(sa.text("ALTER TABLE news_articles ALTER COLUMN video_type DROP NOT NULL"))
        except Exception:
            pass
        op.drop_column("news_articles", "video_type")


def downgrade() -> None:
    pass
