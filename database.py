import os
import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID

# PostgreSQL connection string
# Fallback to local postgres if not provided
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/codeagent")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    # Use UUID for postgres primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    
    # OAuth Identifiers
    github_id = Column(String, unique=True, index=True, nullable=True)
    google_id = Column(String, unique=True, index=True, nullable=True)
    
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Subscription / Tiers
    current_tier = Column(String, default="Trial")  # "Trial", "Basic", "Pro"
    
    # Relationship to usage logs
    usage_logs = relationship("UsageLog", back_populates="user")

class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    date = Column(Date, default=datetime.utcnow().date, index=True)
    review_count = Column(Integer, default=0)

    user = relationship("User", back_populates="usage_logs")

# Helper to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
