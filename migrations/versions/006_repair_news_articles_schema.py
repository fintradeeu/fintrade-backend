"""Repair news articles schema

Revision ID: 006_repair_news_articles_schema
Revises: 005_add_news_article_type
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa


revision = "006_repair_news_articles_schema"
down_revision = "005_add_news_article_type"
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

    columns = {column["name"] for column in insp.get_columns("news_articles")}

    def add_missing(column_name: str, column: sa.Column) -> None:
        if column_name not in columns:
            op.add_column("news_articles", column)

    add_missing("type", sa.Column("type", sa.String(length=50), nullable=False, server_default="Blog Story"))
    add_missing("description", sa.Column("description", sa.Text(), nullable=True))
    add_missing("video_type", sa.Column("video_type", sa.String(length=50), nullable=False, server_default="youtube"))
    add_missing("video_url", sa.Column("video_url", sa.Text(), nullable=True))
    add_missing("thumbnail_url", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    add_missing("status", sa.Column("status", sa.String(length=50), nullable=False, server_default="published"))
    add_missing("views_count", sa.Column("views_count", sa.Integer(), nullable=True, server_default="0"))
    add_missing("created_by", sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    add_missing("created_at", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    add_missing("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    refreshed_columns = {column["name"] for column in sa.inspect(bind).get_columns("news_articles")}
    if "type" in refreshed_columns:
        op.execute(
            sa.text(
                """
                UPDATE news_articles
                SET type = CASE
                    WHEN video_url IS NOT NULL AND video_url <> '' THEN 'Market Update'
                    ELSE 'Blog Story'
                END
                WHERE type IS NULL OR type = ''
                """
            )
        )
    if "video_type" in refreshed_columns:
        op.execute(sa.text("UPDATE news_articles SET video_type = 'youtube' WHERE video_type IS NULL OR video_type = ''"))
    if "status" in refreshed_columns:
        op.execute(sa.text("UPDATE news_articles SET status = 'published' WHERE status IS NULL OR status = ''"))
    if "views_count" in refreshed_columns:
        op.execute(sa.text("UPDATE news_articles SET views_count = 0 WHERE views_count IS NULL"))

    for column_name in ("type", "video_type", "status", "views_count"):
        if column_name in refreshed_columns:
            op.alter_column("news_articles", column_name, server_default=None)


def downgrade() -> None:
    pass
