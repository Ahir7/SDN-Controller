# [cite_start]This file defines the Pydantic/SQLAlchemy models based on Table 2 [cite: 191-194]
# and the database connection.

from sqlalchemy import create_engine, Column, String, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import os
import time
import logging

log = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable must be set")

# Create engine with connection pooling and retry logic
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,   # Recycle connections after 1 hour
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# SQLAlchemy Model for the DB
class PolicyDB(Base):
    __tablename__ = "policies"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    priority = Column(Integer, default=1000)
    source = Column(JSON, nullable=False)
    destination = Column(JSON, nullable=False)
    service = Column(JSON, nullable=True)
    action = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ENABLED")


# Create the table with retry logic for initial connection
max_retries = 5
for attempt in range(max_retries):
    try:
        Base.metadata.create_all(bind=engine)
        log.info("Successfully connected to database and created tables.")
        break
    except OperationalError as e:
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # Exponential backoff
            log.warning(f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}. "
                       f"Retrying in {wait_time}s...")
            time.sleep(wait_time)
        else:
            log.error(f"Failed to connect to database after {max_retries} attempts.")
            raise


# --- Pydantic Schemas for API Validation ---
# [cite_start]Based on Table 2 [cite: 191-194]


class LabelSelector(BaseModel):
    env: Optional[str]
    app: Optional[str]


class Selector(BaseModel):
    label_selector: Optional[LabelSelector]
    ip_block: Optional[str]


class Service(BaseModel):
    protocol: Literal["TCP", "UDP", "ICMP"]
    port: Optional[int] = Field(None, ge=1, le=65535)


class PolicySchema(BaseModel):
    name: str = Field(..., example="Isolate-Prod-DB-from-Dev")
    priority: int = Field(1000, example=5000)
    source: Selector
    destination: Selector
    service: Optional[List[Service]]
    action: Literal["ALLOW", "DENY"]
    status: Literal["ENABLED", "DISABLED"]


class PolicyResponse(PolicySchema):
    id: str

    class Config:
        orm_mode = True


