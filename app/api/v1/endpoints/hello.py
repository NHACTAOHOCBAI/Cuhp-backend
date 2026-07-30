from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger
from app.core.database import get_db

router = APIRouter()

@router.get("", response_model=dict)
async def get_hello(db: Session = Depends(get_db)):
    db_connected = False
    try:
        # Run a quick diagnostic test query
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:
        logger.error(f"Database connection healthcheck failed: {e}")
        
    return {
        "message": "Hello, World!",
        "database_connected": db_connected
    }
