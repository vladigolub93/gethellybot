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
    approval_summary_text: Optional[str] = None
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
    approval_summary_text: Optional[str] = None
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


class InterviewQuestionItemSchema(BaseModel):
    id: int
    type: str
    question: str


class InterviewQuestionPlanSchema(BaseModel):
    questions: List[InterviewQuestionItemSchema] = Field(default_factory=list)
    fallback_used: bool = False


class InterviewEvaluationSchema(BaseModel):
    final_score: float
    strengths: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommendation: str
    interview_summary: str


class InterviewFollowupDecisionSchema(BaseModel):
    answer_quality: str
    ask_followup: bool
    followup_reason: Optional[str] = None
    followup_question: Optional[str] = None


class InterviewAnswerParseSchema(BaseModel):
    answer_summary: str
    technologies: List[str] = Field(default_factory=list)
    systems_or_projects: List[str] = Field(default_factory=list)
    ownership_level: str
    is_concrete: bool
    possible_profile_conflict: bool


class BotControllerDecisionSchema(BaseModel):
    intent: str
    tone: str
    response_mode: str
    keep_current_state: bool
    proposed_action: Optional[str] = None
    response_text: Optional[str] = None
    reason_code: Optional[str] = None


class StateAssistanceDecisionSchema(BaseModel):
    response_text: str
    intent: str
    keep_current_state: bool = True
    suggested_action: Optional[str] = None
    reason_code: Optional[str] = None


class InterviewSessionConductorTurnSchema(BaseModel):
    mode: str
    utterance: str
    current_question_id: Optional[int] = None
    current_question_type: Optional[str] = None
    answer_quality: Optional[str] = None
    follow_up_used: bool = False
    follow_up_reason: Optional[str] = None
    move_to_next_question: bool = False
    interview_complete: bool = False


class CandidateRerankItemSchema(BaseModel):
    candidate_ref: str
    rank: int
    fit_score: float
    rationale: str


class CandidateRerankSchema(BaseModel):
    ranked_candidates: List[CandidateRerankItemSchema] = Field(default_factory=list)


class VacancyInconsistencyFindingSchema(BaseModel):
    severity: str
    category: str
    finding: str


class VacancyInconsistencySchema(BaseModel):
    findings: List[VacancyInconsistencyFindingSchema] = Field(default_factory=list)


class ResponseCopywriterSchema(BaseModel):
    message: str


class DeletionConfirmationSchema(BaseModel):
    message: str
    is_explicit_confirmation_required: bool
