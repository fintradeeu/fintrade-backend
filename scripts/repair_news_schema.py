"""Repair the production news_articles schema.

This is an idempotent operational script for recovering deployments where
Alembic has a stale generated revision and cannot reach the news migration.
"""

import os
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import sqlalchemy as sa
from dotenv import load_dotenv


STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS news_articles (
        id SERIAL PRIMARY KEY,
        title VARCHAR(500) NOT NULL,
        type VARCHAR(50) NOT NULL DEFAULT 'Blog Story',
        description TEXT,
        video_type VARCHAR(50) NOT NULL DEFAULT 'youtube',
        video_url TEXT,
        thumbnail_url TEXT,
        status VARCHAR(50) NOT NULL DEFAULT 'published',
        views_count INTEGER DEFAULT 0,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS type VARCHAR(50) NOT NULL DEFAULT 'Blog Story'",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS video_type VARCHAR(50) NOT NULL DEFAULT 'youtube'",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS video_url TEXT",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS thumbnail_url TEXT",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'published'",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS views_count INTEGER DEFAULT 0",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    """
    UPDATE news_articles
    SET type = CASE
        WHEN video_url IS NOT NULL AND video_url <> '' THEN 'Market Update'
        ELSE 'Blog Story'
    END
    WHERE type IS NULL OR type::varchar = ''
    """,
    "UPDATE news_articles SET video_type = 'youtube' WHERE video_type IS NULL OR video_type::varchar = ''",
    "UPDATE news_articles SET status = 'published' WHERE status IS NULL OR status::varchar = ''",
    "UPDATE news_articles SET views_count = 0 WHERE views_count IS NULL",
    "CREATE INDEX IF NOT EXISTS ix_news_articles_id ON news_articles (id)",
    "DELETE FROM alembic_version",
    "INSERT INTO alembic_version (version_num) VALUES ('006_repair_news_articles_schema')",
]


def main() -> None:
    load_dotenv()
    database_url = os.environ["DATABASE_URL"]
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    database_url = database_url.replace("sqlite+aiosqlite://", "sqlite://")
    parsed = urlparse(database_url)
    if parsed.scheme.startswith("postgresql"):
        params = dict(parse_qsl(parsed.query))
        params.setdefault("sslmode", "require")
        database_url = urlunparse(parsed._replace(query=urlencode(params)))

    engine = sa.create_engine(database_url)
    with engine.begin() as conn:
        for statement in STATEMENTS:
            conn.execute(sa.text(statement))

    print("live news schema repaired")


if __name__ == "__main__":
    main()
