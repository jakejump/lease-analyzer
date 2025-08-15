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


