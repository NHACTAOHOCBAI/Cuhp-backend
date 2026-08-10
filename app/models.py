from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    initials = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")  # "admin" or "user"
    status = Column(String, default="offline")  # "online", "offline", "away"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")


class Token(Base):
    __tablename__ = "tokens"

    token = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="tokens")


class Audio(Base):
    __tablename__ = "audios"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    url = Column(String, nullable=False)
    r2_key = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=True)
    level = Column(String(32), nullable=True)
    category = Column(String(64), nullable=True)
    transcript = Column(Text, nullable=True)


class Vocabulary(Base):
    __tablename__ = "vocabularies"

    id = Column(String, primary_key=True, index=True)
    word = Column(String, nullable=False, index=True)
    pronunciation = Column(String, nullable=True)
    meaning = Column(String, nullable=False)
    word_type = Column(String(64), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Relationships
    user = relationship("User")




