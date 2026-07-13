from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List
from app.models import JobType, WorkMode, Source, Status


class ApplicationCreate(BaseModel):
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

class StatusUpdate(BaseModel):
    current_status:  Status
    
class StatusHistoryResponse(BaseModel):
    id: int
    status: Status
    changed_at: datetime
    note: Optional[str] = None

    class Config:
        from_attributes = True  # use `orm_mode = True` instead if you're on Pydantic v1


class ApplicationResponse(BaseModel):
    id: int
    company: str
    role: str
    job_url: Optional[str] = None
    location: Optional[str] = None
    job_type: JobType
    work_mode: Optional[WorkMode] = None
    date_applied: date
    source: Source
    is_referral: bool
    referral_name: Optional[str] = None
    resume_version: Optional[str] = None
    current_status: Status
    next_follow_up_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    history: List[StatusHistoryResponse] = []

    class Config:
        from_attributes = True
        
class UserCreate(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str