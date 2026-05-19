"""FItTrade LMS — FastAPI application entry point."""

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

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Trading Education LMS — Phase 1 Backend",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
origins = settings.cors_origins_list
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


import os
from fastapi.staticfiles import StaticFiles

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

# ── System Routes (External API) ────────────────────────────────────
import subprocess
from fastapi import HTTPException

@app.post("/system/db/migrate", tags=["System"])
async def trigger_db_migration(secret_key: str):
    """Trigger Alembic migrations from external request (e.g. Postman)."""
    if secret_key != "fintrade_migrate_2026":
        raise HTTPException(status_code=403, detail="Invalid secret key")
    
    try:
        # Run alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True
        )
        return {
            "status": "success",
            "message": "Migration completed successfully",
            "output": result.stdout
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Migration failed. Exit code: {e.returncode}. Output: {e.stdout}. Error: {e.stderr}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# Mount static uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health / readiness probe."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
