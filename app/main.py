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

def ensure_vocabulary_columns():
    """Idempotently add new columns to the vocabularies table without Alembic."""
    inspector = inspect(engine)
    if "vocabularies" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("vocabularies")}
    statements = []
    if "word_type" not in existing:
        statements.append("ALTER TABLE vocabularies ADD COLUMN IF NOT EXISTS word_type VARCHAR(64)")
    if "box_number" not in existing:
        statements.append("ALTER TABLE vocabularies ADD COLUMN IF NOT EXISTS box_number INTEGER DEFAULT 1")
    if "next_review_at" not in existing:
        statements.append("ALTER TABLE vocabularies ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info(f"Applied vocabulary table migrations: {statements}")

def ensure_user_columns():
    """Idempotently add new columns to the users table without Alembic."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("users")}
    statements = []
    if "daily_target" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_target INTEGER DEFAULT 10")
    if "current_streak" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS current_streak INTEGER DEFAULT 0")
    if "last_reviewed_date" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_reviewed_date DATE")
    if "words_reviewed_today" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS words_reviewed_today INTEGER DEFAULT 0")
    if "last_streak_increment_date" not in existing:
        statements.append("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_streak_increment_date DATE")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info(f"Applied user table migrations: {statements}")


def ensure_reading_comment_columns():
    """Idempotently add selected_text column to reading_comments table without Alembic."""
    inspector = inspect(engine)
    if "reading_comments" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("reading_comments")}
    statements = []
    if "selected_text" not in existing:
        statements.append("ALTER TABLE reading_comments ADD COLUMN IF NOT EXISTS selected_text VARCHAR")

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    logger.info(f"Applied reading_comments table migrations: {statements}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions: Recreate tables only if they don't exist to preserve data across reloads
    Base.metadata.create_all(bind=engine)
    ensure_audio_columns()
    ensure_vocabulary_columns()
    ensure_user_columns()
    ensure_reading_comment_columns()

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
