import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Stage(str, enum.Enum):
    applied = "applied"
    oa = "oa"
    phone_screen = "phone_screen"
    interview = "interview"
    final_round = "final_round"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class Source(str, enum.Enum):
    cold_apply = "cold_apply"
    referral = "referral"
    career_fair = "career_fair"
    recruiter = "recruiter"
    other = "other"


class CompanyCreate(BaseModel):
    name: str
    website: Optional[str] = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    website: Optional[str] = None
    created_at: datetime


class ApplicationCreate(BaseModel):
    company_name: str
    company_website: Optional[str] = None
    role_title: str
    source: Source = Source.cold_apply
    job_url: Optional[str] = None
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None


class ApplicationResponse(BaseModel):
    id: int
    company_id: int
    company_name: str
    role_title: str
    source: Source
    job_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    current_stage: Optional[Stage] = None
    current_stage_at: Optional[datetime] = None


class StageEventCreate(BaseModel):
    stage: Stage
    occurred_at: Optional[datetime] = None
    notes: Optional[str] = None


class StageEventResponse(BaseModel):
    id: int
    application_id: int
    stage: Stage
    occurred_at: datetime
    notes: Optional[str] = None


class StageCount(BaseModel):
    stage: Stage
    count: int


class FunnelStage(BaseModel):
    stage: Stage
    reached: int
    still_pending: int
    conversion_to_next: Optional[float] = None


class StageTransition(BaseModel):
    from_stage: Stage
    to_stage: Stage
    transitions: int
    avg_days: float


class SourceStats(BaseModel):
    source: Source
    total: int
    responded: int
    response_rate: float
