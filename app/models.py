import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class JobType(str, enum.Enum):
    internship = "Internship"
    full_time = "Full Time"
    co_op = "Co-Op"
    
class WorkMode(str,enum.Enum):
    onsite = "Onsite"
    hybrid = "Hybrid"
    remote = "Remote"

class Source(str, enum.Enum):
    linkedin = "linkedin"
    company_site = "company_site"
    handshake = "handshake"
    career_fair = "career_fair"
    other = "other"


class Status(str, enum.Enum):
    applied = "applied"
    interviewing = "interviewing"
    rejected = "rejected"
    offer = "offer"

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    job_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    job_type = Column(Enum(JobType), nullable=False)
    work_mode = Column(Enum(WorkMode), nullable=True)
    date_applied = Column(Date, nullable=False)
    source = Column(Enum(Source), nullable=False)
    is_referral = Column(Boolean, default=False, nullable=False)
    referral_name = Column(String, nullable=True)
    resume_version = Column(String, nullable=True)
    current_status = Column(Enum(Status), nullable=False, default=Status.applied)
    next_follow_up_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    history = relationship("StatusHistory", back_populates="application", cascade="all, delete-orphan")
    
class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    status = Column(Enum(Status), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    note = Column(Text, nullable=True)

    application = relationship("Application", back_populates="history")
    
    
                           