from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    # pool_pre_ping checks if connection is alive before executing query
    pool_pre_ping=True
)

# Create sessionmaker factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for database models
Base = declarative_base()

# Dependency generator to fetch DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
