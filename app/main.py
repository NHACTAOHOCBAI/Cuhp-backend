from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import hashlib
from loguru import logger
from sqlalchemy import inspect, text
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app import models

def get_password_hash(password: str) -> str:
    salt = "chat_pepper_123"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

def seed_database():
    db = SessionLocal()
    try:
        # Check if users already exist
        if db.query(models.User).first() is None:
            # Seed Admin
            admin_pwd = get_password_hash("admin")
            admin_user = models.User(
                id="usr-admin",
                username="admin",
                hashed_password=admin_pwd,
                name="Support Admin",
                initials="AD",
                role="admin",
                status="offline"
            )

            db.add(admin_user)
            db.commit()
    finally:
        db.close()

def ensure_audio_columns():
    """Idempotently add new columns to the audios table without Alembic.

    Safe to run on every startup: skips columns that already exist.
    Uses PostgreSQL's ``ADD COLUMN IF NOT EXISTS`` (Postgres 9.6+).
    """
    inspector = inspect(engine)
    if "audios" not in inspector.get_table_names():
        return  # create_all() will create the table with all columns

    existing = {col["name"] for col in inspector.get_columns("audios")}
    statements = []
    if "description" not in existing:
        statements.append("ALTER TABLE audios ADD COLUMN IF NOT EXISTS description TEXT")
    if "level" not in existing:
        statements.append("ALTER TABLE audios ADD COLUMN IF NOT EXISTS level VARCHAR(32)")
    if "category" not in existing:
        statements.append("ALTER TABLE audios ADD COLUMN IF NOT EXISTS category VARCHAR(64)")
    if "transcript" not in existing:
        statements.append("ALTER TABLE audios ADD COLUMN IF NOT EXISTS transcript TEXT")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info(f"Applied audio table migrations: {statements}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions: Recreate tables only if they don't exist to preserve data across reloads
    Base.metadata.create_all(bind=engine)
    ensure_audio_columns()

    seed_database()
    logger.info("Database initialized and admin user seeded.")
    yield
    # Shutdown actions (if any)

app = FastAPI(
    title=settings.app_name,
    description="Backend microservice.",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for mobile app requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register central API router under /api prefix
app.include_router(api_router, prefix="/api")
