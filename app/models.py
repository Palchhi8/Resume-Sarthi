"""Pydantic data models for candidate profiling, evaluation, and API schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class Experience(BaseModel):
    """Candidate work experience entry."""
    company: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    is_current: bool = False


class Education(BaseModel):
    """Candidate education entry."""
    degree: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[str] = None
    field_of_study: Optional[str] = None


class CandidateProfile(BaseModel):
    """Structured candidate profile extracted from resume."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    years_of_experience: Optional[float] = None
    employment_gaps: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    raw_text: Optional[str] = None


class HiringEvaluation(BaseModel):
    """Corporate Hiring Evaluation Form."""
    candidate_name: str
    email: Optional[str] = None
    primary_skillset: list[str] = Field(default_factory=list)
    years_of_experience: Optional[float] = None
    education: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    employment_gaps: list[str] = Field(default_factory=list)
    ambiguities_missing_info: list[str] = Field(default_factory=list)
    recommended_role: str
    evaluation_summary: str
    strengths: list[str] = Field(default_factory=list)
    areas_for_investigation: list[str] = Field(default_factory=list)
    decision_recommendation: str = "Proceed to Technical Interview"


class WorkflowStep(BaseModel):
    """Track individual step in the agentic workflow."""
    name: str
    status: str = "completed"
    detail: Optional[str] = None


class WorkflowResult(BaseModel):
    """Result of running the agentic evaluation workflow."""
    success: bool
    candidate: CandidateProfile
    evaluation: HiringEvaluation
    pdf_path: Optional[str] = None
    pdf_filename: Optional[str] = None
    steps: list[WorkflowStep] = Field(default_factory=list)
    error: Optional[str] = None


# API Schemas
class AskRequest(BaseModel):
    """Request payload for natural language Q&A."""
    question: str
    candidate: Optional[CandidateProfile] = None
    resume_text: str


class AskResponse(BaseModel):
    """Response payload for natural language Q&A."""
    answer: str
    grounded: bool = True


class UploadResponse(BaseModel):
    """Response payload for resume upload."""
    filename: str
    file_type: str
    extracted_text: str
    candidate: CandidateProfile


class EvaluateRequest(BaseModel):
    """Request payload to trigger evaluation workflow."""
    resume_text: str
    candidate: Optional[CandidateProfile] = None


class DispatchRequest(BaseModel):
    """Request payload to dispatch evaluation to HR."""
    file_path: Optional[str] = None
    filename: Optional[str] = None
    recipient: Optional[str] = None


class DispatchResponse(BaseModel):
    """Response payload for email dispatch."""
    status: str
    recipient: str
    attachment: str
    timestamp: str
    message: str
