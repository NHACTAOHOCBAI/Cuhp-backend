from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer, Date, Float, Boolean
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
    daily_target = Column(Integer, default=10, nullable=False)
    current_streak = Column(Integer, default=0, nullable=False)
    last_reviewed_date = Column(Date, nullable=True)
    words_reviewed_today = Column(Integer, default=0, nullable=False)
    last_streak_increment_date = Column(Date, nullable=True)

    # Sleep Settings
    sleep_bedtime = Column(String, default="22:00", nullable=False)
    sleep_waketime = Column(String, default="06:00", nullable=False)
    sleep_reminder_enabled = Column(Boolean, default=True, nullable=False)

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

    # Relationships
    comments = relationship("AudioComment", back_populates="audio", cascade="all, delete-orphan")



class Vocabulary(Base):
    __tablename__ = "vocabularies"

    id = Column(String, primary_key=True, index=True)
    word = Column(String, nullable=False, index=True)
    pronunciation = Column(String, nullable=True)
    meaning = Column(String, nullable=False)
    word_type = Column(String(64), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    context_sentence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    box_number = Column(Integer, default=1, nullable=False)
    next_review_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User")


class ReadingPassage(Base):
    __tablename__ = "reading_passages"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    level = Column(String(32), nullable=True)
    category = Column(String(64), nullable=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    comments = relationship("ReadingComment", back_populates="passage", cascade="all, delete-orphan")
    translations = relationship("TranslationPractice", back_populates="passage", cascade="all, delete-orphan")


class TranslationPractice(Base):
    __tablename__ = "translation_practices"

    id = Column(String, primary_key=True, index=True)
    passage_id = Column(String, ForeignKey("reading_passages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    translation_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    passage = relationship("ReadingPassage", back_populates="translations")
    user = relationship("User")


class ReadingComment(Base):
    __tablename__ = "reading_comments"

    id = Column(String, primary_key=True, index=True)
    passage_id = Column(String, ForeignKey("reading_passages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    selected_text = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    passage = relationship("ReadingPassage", back_populates="comments")
    user = relationship("User")


class AudioComment(Base):
    __tablename__ = "audio_comments"

    id = Column(String, primary_key=True, index=True)
    audio_id = Column(String, ForeignKey("audios.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    selected_text = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    audio = relationship("Audio", back_populates="comments")
    user = relationship("User")


class WorkoutCategory(Base):
    __tablename__ = "workout_categories"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False, default="emerald")  # e.g., emerald, blue, violet, rose, amber, cyan
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    exercises = relationship("WorkoutExercise", back_populates="category", cascade="all, delete-orphan")


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(String, ForeignKey("workout_categories.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False, index=True)
    sets = Column(Integer, default=3, nullable=False)
    reps = Column(Integer, default=10, nullable=False)
    weight = Column(Float, nullable=True)  # Weight in kg, nullable for cardio/bodyweight
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    category = relationship("WorkoutCategory", back_populates="exercises")


class TodoTask(Base):
    """A single task placed in one of the four Eisenhower matrix quadrants.

    Quadrant values (see app/schemas/todo.py for the canonical list):
      - "do"        : urgent + important        -> làm ngay
      - "schedule"  : important, not urgent     -> lên lịch
      - "delegate"  : urgent, not important     -> ủy thác
      - "eliminate" : neither                   -> loại bỏ

    Tasks are a rolling backlog: they are not bound to a single day. An
    optional `due_date` drives the "Hôm nay / Tuần này / Tất cả" filters and
    the overdue badge, and an unfinished task stays visible until completed.
    """

    __tablename__ = "todo_tasks"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    quadrant = Column(String(16), nullable=False, default="do", index=True)
    due_date = Column(Date, nullable=True, index=True)
    scheduled_date = Column(Date, nullable=True, index=True)
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    estimated_time = Column(Integer, nullable=True) # Estimated time in minutes
    # Ordering inside a quadrant; smaller comes first. Reassigned on drag-drop.
    position = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")


class SleepLog(Base):
    __tablename__ = "sleep_logs"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sleep_date = Column(Date, nullable=False, index=True)
    sleep_time_actual = Column(DateTime, nullable=False)
    wake_time_actual = Column(DateTime, nullable=False)
    duration_minutes = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User")



