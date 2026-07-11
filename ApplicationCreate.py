from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from app.models import JobType, WorkMode, Source


class ApplicaitonCreate(BaseModel):
    company: str
    role: str
    job_url: Optional[str] = None
    location: Optional[str] = None
    job_type: JobType
    work_mode: Optional[WorkMode] = None
    date_applied: date
    source: Source
    is_referral: bool = False
    referral_name: Optional[str] = None
    resume_version: Optional[str] = None
    next_follow_up_date: Optional[date] = None
    notes: Optional[str] = None
    
    