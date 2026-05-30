"""Add type field to news articles

Revision ID: 005_add_news_article_type
Revises: 004_add_google_oauth
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa


revision = "005_add_news_article_type"
down_revision = "004_add_google_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    columns = [column["name"] for column in insp.get_columns("news_articles")]
    if "type" not in columns:
        op.add_column(
            "news_articles",
            sa.Column("type", sa.String(length=50), nullable=False, server_default="Blog Story"),
        )
        op.execute(
            sa.text(
                """
                UPDATE news_articles
                SET type = CASE
                    WHEN video_url IS NOT NULL AND video_url <> '' THEN 'Market Update'
                    ELSE 'Blog Story'
                END
                """
            )
        )
        op.alter_column("news_articles", "type", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    columns = [column["name"] for column in insp.get_columns("news_articles")]
    if "type" in columns:
        op.drop_column("news_articles", "type")
