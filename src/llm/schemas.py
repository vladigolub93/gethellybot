from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CandidateSummarySchema(BaseModel):
    status: str = "draft"
    source_type: Optional[str] = None
    headline: Optional[str] = None
    experience_excerpt: Optional[str] = None
    years_experience: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    candidate_edit_notes: Optional[str] = None


class CandidateQuestionParseSchema(BaseModel):
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_period: Optional[str] = None
    location_text: Optional[str] = None
    city: Optional[str] = None
    country_code: Optional[str] = None
    work_format: Optional[str] = None


class VacancySummarySchema(BaseModel):
    status: str = "draft"
    source_type: Optional[str] = None
    role_title: Optional[str] = None
    seniority_normalized: Optional[str] = None
    primary_tech_stack: List[str] = Field(default_factory=list)
    project_description_excerpt: Optional[str] = None
    inconsistency_issues: List[str] = Field(default_factory=list)


class VacancyClarificationSchema(BaseModel):
    role_title: Optional[str] = None
    seniority_normalized: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    budget_currency: Optional[str] = None
    budget_period: Optional[str] = None
    countries_allowed_json: List[str] = Field(default_factory=list)
    work_format: Optional[str] = None
    team_size: Optional[int] = None
    project_description: Optional[str] = None
    primary_tech_stack_json: List[str] = Field(default_factory=list)


class InterviewQuestionPlanSchema(BaseModel):
    questions: List[str] = Field(default_factory=list)


class InterviewEvaluationSchema(BaseModel):
    final_score: float
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommendation: str
    interview_summary: str
