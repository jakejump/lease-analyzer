from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    score: Optional[int] = Field(default=None)
    explanation: str


class UploadResponse(BaseModel):
    message: str
    doc_id: str
    risks: Dict[str, RiskAssessment]


class AskResponse(BaseModel):
    answer: str


class Abnormality(BaseModel):
    text: str
    impact: Literal["beneficial", "harmful", "neutral"]


class AbnormalitiesResponse(BaseModel):
    abnormalities: List[Abnormality]


class ClausesResponse(BaseModel):
    clauses: List[str]


# Project/Version schemas
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class VersionCreate(BaseModel):
    label: Optional[str] = None


class LeaseVersionOut(BaseModel):
    id: str
    project_id: str
    label: Optional[str] = None
    status: str
    created_at: Optional[str] = None


