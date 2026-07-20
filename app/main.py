"""FinTrade LMS — FastAPI application entry point."""

from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
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
from app.modules.franchise_ibs.routes import router as franchise_ibs_router
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
from app.modules.mobile_api.routes import (
    router as mobile_users_router,
    student_router as mobile_students_router,
    mobile_auth_router,
    mobile_profile_router,
    mobile_v1_router,
)
from app.modules.commissions.routes import router as commissions_router
from app.modules.batches.routes import router as batches_router
from app.modules.doubts.routes import router as doubts_router
from app.modules.logs.routes import router as logs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    import asyncio
    import logging
    import traceback
    logger = logging.getLogger(__name__)

    def run_alembic_upgrade():
        try:
            import os
            import sys
            import traceback
            # pyrefly: ignore [missing-import]
            from alembic.config import Config
            # pyrefly: ignore [missing-import]
            from alembic import command
            
            logger.info("Running automated database migrations on startup...")
            print("Running automated database migrations on startup...", file=sys.stderr, flush=True)
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if not os.path.exists(os.path.join(root_dir, "alembic.ini")):
                root_dir = os.getcwd()
                
            alembic_cfg = Config(os.path.join(root_dir, "alembic.ini"))
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully.")
            print("Database migrations completed successfully.", file=sys.stderr, flush=True)
        except BaseException:
            message = "Automated database migrations failed:\n" + traceback.format_exc()
            logger.error(message)
            print(message, file=sys.stderr, flush=True)

    try:
        await asyncio.to_thread(run_alembic_upgrade)

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
                await _repair_users_schema_async(session)
                await _repair_courses_schema_async(session)
                await _repair_payment_transactions_schema_async(session)
                await _repair_feedback_schema_async(session)
                await _repair_news_schema_async(session)
                await _repair_lectures_schema_async(session)
                await _repair_certificates_schema_async(session)
                await _repair_batches_schema_async(session)
                await _repair_doubts_schema_async(session)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Schema auto-repair skipped or failed: {e}")

    # Start background live class scheduler
        from app.utils.live_class_scheduler import live_class_scheduler_loop
        import asyncio
        asyncio.create_task(live_class_scheduler_loop())
    except BaseException:
        import sys
        logging.basicConfig(level=logging.INFO)
        message = "Application startup failed:\n" + traceback.format_exc()
        logger.critical(message)
        print(message, file=sys.stderr, flush=True)
        raise

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Trading Education LMS — Phase 1 Backend",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ── Global exception handler ────────────────────────────────────────
# When an unhandled exception causes a raw 500, FastAPI skips the CORS
# middleware, so the browser reports "CORS error" instead of the real error.
# This handler catches ALL unhandled errors and returns a proper JSONResponse
# which flows back through the CORS middleware and gets the right headers.
# pyrefly: ignore [missing-import]
from starlette.requests import Request
# pyrefly: ignore [missing-import]
from starlette.responses import JSONResponse
import traceback as _tb

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    from starlette.exceptions import HTTPException as StarletteHTTPException
    if isinstance(exc, StarletteHTTPException):
        error_detail = exc.detail
        status_code = exc.status_code
    else:
        error_detail = str(exc)
        status_code = 500
        tb = _tb.format_exc()
        import logging
        logging.getLogger("uvicorn.error").error(f"Unhandled error on {request.method} {request.url}: {error_detail}\n{tb}")
    
    headers = {}
    origin = request.headers.get("origin")
    if origin:
        if "*" in settings.cors_origins_list or origin in settings.cors_origins_list:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Methods"] = "*"
            headers["Access-Control-Allow-Headers"] = "*"
            
    public_detail = (
        error_detail if status_code != 500 else (
            f"Internal Server Error: {error_detail}"
            if settings.DEBUG
            else "An unexpected server error occurred. Please try again."
        )
    )
    return JSONResponse(
        status_code=status_code,
        content={"detail": public_detail},
        headers=headers,
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
app.include_router(mobile_users_router, prefix="/api")
app.include_router(mobile_students_router, prefix="/api")
app.include_router(mobile_auth_router, prefix="/api")
app.include_router(mobile_profile_router, prefix="/api")
app.include_router(mobile_v1_router, prefix="/api")
app.include_router(commissions_router)
app.include_router(batches_router)
app.include_router(doubts_router)
app.include_router(franchise_ibs_router)
app.include_router(logs_router)

# Mount media directory

import os
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

# ── System Routes (External API) ────────────────────────────────────
# pyrefly: ignore [missing-import]
from fastapi import HTTPException
import traceback

@app.post("/system/db/migrate", tags=["System"])
def trigger_db_migration(secret_key: str):
    """Trigger Alembic migrations from external request (e.g. Postman)."""
    if secret_key != "fintrade_migrate_2026":
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    try:
        # pyrefly: ignore [missing-import]
        from alembic.config import Config   
        # pyrefly: ignore [missing-import]
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
            "009_add_lecture_registrations.py",
            "009_force_drop_video_type.py",
            "010_add_user_city.py",
            "011_add_lecture_recordings.py",
            "012_add_is_popular_to_courses.py",
            "013_repair_payment_transactions_schema.py",
            "014_add_commission_wallet_tables.py",
            "015_add_referral_leads.py",
            "016_add_ib_self_registration_fields.py",
            "017_make_student_referral_course_nullable.py",
            "3abe91512295_add_author_name_to_newsarticle.py",
            "621bf7ebb607_add_feedback_forms.py",
            "de8dc5db081f_merge_all_heads.py",
            "df05f2889739_add_ai_tables.py",
            "021_add_offline_payment_columns.py",
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
        # pyrefly: ignore [missing-import]
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
        # pyrefly: ignore [missing-import]
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
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa

    statements = [
        """
        CREATE TABLE IF NOT EXISTS news_articles (
            id SERIAL PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            type VARCHAR(50) NOT NULL DEFAULT 'Blog Story',
            description TEXT,
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
        "UPDATE news_articles SET status = 'published' WHERE status IS NULL OR status::varchar = ''",
        "UPDATE news_articles SET views_count = 0 WHERE views_count IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_news_articles_id ON news_articles (id)"
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


async def _repair_users_schema_async(db):
    """Repair users table columns expected by the current auth model."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa

    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSON",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
        "ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)",
    ]

    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            import logging
            logging.getLogger(__name__).warning(
                f"Users schema repair statement failed: {statement.strip()[:60]}... error: {e}"
            )


async def _repair_courses_schema_async(db):
    """Repair courses table columns expected by the current course model."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa

    statements = [
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS is_popular BOOLEAN DEFAULT false",
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS is_batch_only BOOLEAN DEFAULT false",
        "UPDATE courses SET is_batch_only = false WHERE is_batch_only IS NULL",
    ]

    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            import logging
            logging.getLogger(__name__).warning(
                f"Courses schema repair statement failed: {statement.strip()[:60]}... error: {e}"
            )


async def _repair_payment_transactions_schema_async(db):
    """Repair payment_transactions table to add batch_id column if not exists."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa

    statements = [
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS batch_id INTEGER REFERENCES batches(id) ON DELETE SET NULL",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS reference_number VARCHAR(255)",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS payment_date TIMESTAMPTZ",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255)",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS branch_name VARCHAR(255)",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS account_holder_name VARCHAR(255)",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS cheque_image_url VARCHAR(500)",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS remarks VARCHAR(1000)",
    ]

    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            import logging
            logging.getLogger(__name__).warning(
                f"payment_transactions schema repair statement failed: {statement.strip()[:60]}... error: {e}"
            )


async def _repair_feedback_schema_async(db):
    """Repair feedback table columns expected by the current feedback model."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa

    statements = [
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS form_id INTEGER REFERENCES feedback_forms(id) ON DELETE SET NULL",
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)",
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS show_on_landing_page BOOLEAN DEFAULT false",
    ]

    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            import logging
            logging.getLogger(__name__).warning(
                f"Feedback schema repair statement failed: {statement.strip()[:60]}... error: {e}"
            )


async def _repair_news_schema_async(db):
    """Repair production news schema asynchronously."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa

    statements = [
        """
        CREATE TABLE IF NOT EXISTS news_articles (
            id SERIAL PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            type VARCHAR(50) NOT NULL DEFAULT 'Blog Story',
            description TEXT,
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
        "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS video_url TEXT",
        "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS thumbnail_url TEXT",
        "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'published'",
        "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS views_count INTEGER DEFAULT 0",
        "ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS author_name VARCHAR(255)",
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
        "UPDATE news_articles SET status = 'published' WHERE status IS NULL OR status::varchar = ''",
        "UPDATE news_articles SET views_count = 0 WHERE views_count IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_news_articles_id ON news_articles (id)"
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

async def _repair_lectures_schema_async(db):
    """Repair lecture registrations table to add one_hour_email_sent column if not exists."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa
    statements = [
        "ALTER TABLE lecture_registrations ADD COLUMN IF NOT EXISTS one_hour_email_sent BOOLEAN DEFAULT false",
    ]
    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            import logging
            logging.getLogger(__name__).warning(
                f"Lectures schema repair statement failed: {statement.strip()[:60]}... error: {e}"
            )

async def _repair_certificates_schema_async(db):
    """Repair certificates table to add module_id column if not exists."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa
    statements = [
        "ALTER TABLE certificates ADD COLUMN module_id INTEGER REFERENCES course_modules(id) ON DELETE CASCADE",
    ]
    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            # If the column already exists, this is expected and fine to skip.
            err_msg = str(e)
            if "duplicate column" not in err_msg.lower() and "already exists" not in err_msg.lower():
                import logging
                logging.getLogger(__name__).warning(
                    f"Certificates schema repair statement failed: {statement.strip()[:60]}... error: {e}"
                )

async def _repair_batches_schema_async(db):
    """Repair batch tables to add template_module_id and template_lesson_id columns."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa
    statements = [
        "ALTER TABLE batch_modules ADD COLUMN IF NOT EXISTS template_module_id INTEGER REFERENCES course_modules(id) ON DELETE SET NULL",
        "ALTER TABLE batch_lessons ADD COLUMN IF NOT EXISTS template_lesson_id INTEGER REFERENCES lessons(id) ON DELETE SET NULL",
        "ALTER TABLE batch_lectures ADD COLUMN IF NOT EXISTS instructor_name VARCHAR(255)",
        "ALTER TABLE batch_lectures ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ",
    ]
    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            err_msg = str(e)
            if "duplicate column" not in err_msg.lower() and "already exists" not in err_msg.lower():
                import logging
                logging.getLogger(__name__).warning(
                    f"Batches schema repair statement failed: {statement.strip()[:60]}... error: {e}"
                )


async def _repair_doubts_schema_async(db):
    """Create doubt_forms and doubt_submissions tables if they don't exist."""
    # pyrefly: ignore [missing-import]
    import sqlalchemy as sa
    statements = [
        """
        CREATE TABLE IF NOT EXISTS doubt_forms (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
            end_date TIMESTAMPTZ NOT NULL,
            is_active BOOLEAN DEFAULT true NOT NULL,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_doubt_forms_id ON doubt_forms (id)",
        """
        CREATE TABLE IF NOT EXISTS doubt_submissions (
            id SERIAL PRIMARY KEY,
            form_id INTEGER NOT NULL REFERENCES doubt_forms(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            topic VARCHAR(255),
            doubt_text TEXT NOT NULL,
            submitted_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_doubt_submissions_id ON doubt_submissions (id)",
    ]
    for statement in statements:
        try:
            await db.execute(sa.text(statement))
            await db.commit()
        except Exception as e:
            await db.rollback()
            err_msg = str(e)
            if "already exists" not in err_msg.lower():
                import logging
                logging.getLogger(__name__).warning(
                    f"Doubts schema repair statement failed: {statement.strip()[:60]}... error: {e}"
                )


# Mount static uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health / readiness probe."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
