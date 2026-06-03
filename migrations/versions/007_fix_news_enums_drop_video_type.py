"""Fix news_articles: convert status ENUM to VARCHAR, drop video_type column

Revision ID: 007_fix_news_enums_drop_video_type
Revises: 006_repair_news_articles_schema
Create Date: 2026-06-02

Problem: The live DB has:
  - status column as PostgreSQL ENUM type 'news_status' (not VARCHAR)
  - video_type column as NOT NULL (not in the SQLAlchemy model)
Both cause INSERT failures with a 500 error.
"""

from alembic import op
import sqlalchemy as sa


revision = "007_fix_news_enums"
down_revision = "006_repair_news_articles_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "news_articles" not in insp.get_table_names():
        # Table doesn't exist at all — nothing to fix
        return

    columns = {col["name"]: col for col in insp.get_columns("news_articles")}

    # ── 1. Convert status from ENUM → VARCHAR if needed ───────────────────────
    if "status" in columns:
        status_type = columns["status"]["type"]
        is_enum = getattr(status_type, "name", None) == "news_status" or "ENUM" in str(type(status_type)).upper()
        if is_enum:
            # It's an ENUM — convert it
            op.execute(sa.text("ALTER TABLE news_articles ALTER COLUMN status DROP DEFAULT"))
            op.execute(sa.text(
                "ALTER TABLE news_articles "
                "ALTER COLUMN status TYPE VARCHAR(50) USING status::VARCHAR"
            ))
            op.execute(sa.text("ALTER TABLE news_articles ALTER COLUMN status SET DEFAULT 'published'"))

    # ── 2. Drop the stale video_type column if it exists ─────────────────────
    if "video_type" in columns:
        # First make it nullable so we can safely drop
        try:
            op.execute(sa.text(
                "ALTER TABLE news_articles ALTER COLUMN video_type DROP NOT NULL"
            ))
        except Exception:
            pass
        op.drop_column("news_articles", "video_type")

    # ── 3. Drop orphaned enum types if they exist ────────────────────────────
    op.execute(sa.text("DROP TYPE IF EXISTS news_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS video_type"))


def downgrade() -> None:
    # Non-destructive downgrade: just re-add video_type as nullable VARCHAR
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "news_articles" not in insp.get_table_names():
        return

    columns = {col["name"] for col in insp.get_columns("news_articles")}
    if "video_type" not in columns:
        op.add_column(
            "news_articles",
            sa.Column("video_type", sa.String(length=50), nullable=True),
        )
