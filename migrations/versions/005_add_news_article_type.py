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

    if "news_articles" not in insp.get_table_names():
        op.create_table(
            "news_articles",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("type", sa.String(length=50), nullable=False, server_default="Blog Story"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("video_type", sa.String(length=50), nullable=False, server_default="youtube"),
            sa.Column("video_url", sa.Text(), nullable=True),
            sa.Column("thumbnail_url", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="published"),
            sa.Column("views_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_news_articles_id", "news_articles", ["id"], unique=False)
        op.alter_column("news_articles", "type", server_default=None)
        op.alter_column("news_articles", "video_type", server_default=None)
        op.alter_column("news_articles", "status", server_default=None)
        op.alter_column("news_articles", "views_count", server_default=None)
        return

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
