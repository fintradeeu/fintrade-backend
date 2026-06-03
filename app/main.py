"""FinTrade LMS — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import init_db
from app.utils.logger import setup_logging

# ── Module routers ───────────────────────────────────────────────────
from app.modules.auth.routes import router as auth_router
from app.modules.courses.routes import router as courses_router
from app.modules.exams.routes import router as exams_router
from app.modules.offers.routes import router as offers_router
from app.modules.lectures.routes import router as lectures_router
from app.modules.ai.routes import router as ai_router
from app.modules.admin.routes import router as admin_router
from app.modules.faculty.routes import router as faculty_router
from app.modules.distributors.routes import router as distributor_router
from app.modules.learning.routes import router as learning_router
from app.modules.certificates.routes import router as certificates_router
from app.modules.simulator.routes import router as simulator_router
from app.modules.placement.routes import router as placement_router
from app.modules.feedback.routes import router as feedback_router
from app.modules.kyc.routes import router as kyc_router
from app.modules.roles.routes import router as roles_router
from app.modules.news.routes import router as news_router
from app.modules.settings.routes import router as settings_router
from app.modules.payments.routes import router as payments_router
from app.modules.dashboard.routes import router as dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging(debug=settings.DEBUG)
    await init_db()

    # Seed default roles and admin user (idempotent — skips if already present)
    from app.db.seed import seed
    try:
        await seed(skip_init_db=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Seed skipped or failed: {e}")

    # Auto-repair news schema on startup to prevent UndefinedColumnError on fresh deployments
    try:
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await _repair_news_schema_async(session)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"News schema auto-repair skipped or failed: {e}")

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Trading Education LMS — Phase 1 Backend",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
origins = settings.cors_origins_list

# Force allow production domains (in case .env overrides the default and misses them)
for domain in ["https://www.thefintrade.com", "https://thefintrade.com", "https://api.thefintrade.com"]:
    if domain not in origins:
        origins.append(domain)

allow_all = "*" in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if allow_all else origins,
    allow_origin_regex=".*" if allow_all else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── Register routers ────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(courses_router)
app.include_router(exams_router)
app.include_router(offers_router)
app.include_router(lectures_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(faculty_router)
app.include_router(distributor_router)
app.include_router(learning_router)
app.include_router(certificates_router)
app.include_router(simulator_router)
app.include_router(placement_router)
app.include_router(feedback_router)
app.include_router(dashboard_router)
app.include_router(kyc_router)
app.include_router(roles_router)
app.include_router(news_router)
app.include_router(settings_router)
app.include_router(payments_router)


import os
from fastapi.staticfiles import StaticFiles

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

# ── System Routes (External API) ────────────────────────────────────
from fastapi import HTTPException
import traceback

@app.post("/system/db/migrate", tags=["System"])
def trigger_db_migration(secret_key: str):
    """Trigger Alembic migrations from external request (e.g. Postman)."""
    if secret_key != "fintrade_migrate_2026":
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    try:
        from alembic.config import Config
        from alembic import command
        import os
        
        # Determine the root directory (where alembic.ini is located)
        # Assuming app is a package inside the root directory
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.exists(os.path.join(root_dir, "alembic.ini")):
            # Fallback to current working directory
            root_dir = os.getcwd()
            
        alembic_cfg = Config(os.path.join(root_dir, "alembic.ini"))
        
        import glob

        # 1. Clean up rogue generated migration files left on the server.
        versions_dir = os.path.join(root_dir, "migrations", "versions")
        known_migrations = {
            "001_add_distributors_referrals_rbac.py",
            "002_add_exam_features.py",
            "003_make_lecture_course_id_nullable.py",
            "004_add_google_oauth.py",
            "005_add_news_article_type.py",
            "006_repair_news_articles_schema.py",
            "007_fix_news_enums_drop_video_type.py",
            "008_add_user_permissions.py",
            ".gitkeep",
        }
        for f in glob.glob(os.path.join(versions_dir, "*")):
            if os.path.isdir(f):
                continue
            if os.path.basename(f) not in known_migrations:
                try:
                    os.remove(f)
                except Exception:
                    pass
                
        # 2. Proactively clear any duplicate heads in alembic_version table and stamp to 004
        import sqlalchemy as sa
        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("sqlite+aiosqlite://", "sqlite://")
        sync_engine = sa.create_engine(sync_url)
        try:
            with sync_engine.connect() as conn:
                conn.execute(sa.text("DELETE FROM alembic_version;"))
                conn.execute(sa.text("INSERT INTO alembic_version (version_num) VALUES ('004_add_google_oauth');"))
                conn.commit()
        except Exception as db_err:
            print("DB version auto-heal skipped or failed:", db_err)

        # 3. Run upgrade head programmatically to apply the REAL migrations from Git
        try:
            command.upgrade(alembic_cfg, "head")
        except Exception as migration_err:
            # Some live deployments have a stale generated migration revision
            # in the Alembic graph. Repair the news schema directly so the
            # admin content API can recover without manual DB console access.
            if "4968c3161755" not in str(migration_err):
                raise
            _repair_news_schema(sync_engine)

        return {
            "status": "success",
            "message": "Migration generated and applied successfully"
        }
    except Exception as e:
        error_details = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}\n{error_details}")


@app.get("/system/db/inspect", tags=["System"])
async def inspect_db(secret_key: str):
    """Temporary diagnostic endpoint to check news_articles schema and query traceback on live server."""
    if secret_key != "fintrade_migrate_2026":
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    try:
        from app.db.database import AsyncSessionLocal
        import sqlalchemy as sa
        async with AsyncSessionLocal() as session:
            # Query table columns
            res = await session.execute(sa.text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'news_articles'
            """))
            columns = [{"column_name": r[0], "data_type": r[1]} for r in res.all()]
            
            # Query news articles
            try:
                res_data = await session.execute(sa.text("SELECT * FROM news_articles LIMIT 5"))
                keys = res_data.keys()
                data = []
                for row in res_data.all():
                    row_dict = {}
                    for k, val in zip(keys, row):
                        if hasattr(val, "isoformat"):
                            row_dict[k] = val.isoformat()
                        else:
                            row_dict[k] = val
                    data.append(row_dict)
                query_error = None
            except Exception as q_err:
                import traceback
                data = None
                query_error = traceback.format_exc()
                
            return {
                "columns": columns,
                "data": data,
                "query_error": query_error
            }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


def _repair_news_schema(sync_engine):
    """Repair production news schema when Alembic graph is polluted."""
    import sqlalchemy as sa

    statements = [
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
        "INSERT INTO alembic_version (version_num) VALUES ('006_repair_news_articles_schema')"
    ]

    for statement in statements:
        try:
            with sync_engine.begin() as conn:
                conn.execute(sa.text(statement))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"News schema repair statement failed: {statement.strip()[:60]}... error: {e}"
            )


async def _repair_news_schema_async(db):
    """Repair production news schema asynchronously."""
    import sqlalchemy as sa

    statements = [
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
        "INSERT INTO alembic_version (version_num) VALUES ('006_repair_news_articles_schema')"
    ]

    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            import logging
            logging.getLogger(__name__).warning(
                f"News schema repair statement failed: {statement.strip()[:60]}... error: {e}"
            )

# Mount static uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health / readiness probe."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
