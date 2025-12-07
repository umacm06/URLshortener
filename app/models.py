# app/models.py
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .database import Base

class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String(32), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    click_count = Column(Integer, default=0)


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    detail = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
