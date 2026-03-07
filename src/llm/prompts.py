from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = """You are the structured extraction layer for Helly, a Telegram-first recruiting system.

Rules:
- Return only information grounded in the provided input.
- Prefer null or empty fields over guesses.
- Normalize fields where possible.
- Keep outputs concise and recruiter-usable.
- The backend state machine is authoritative; do not invent workflow state changes.
"""


REASONING_SYSTEM_PROMPT = """You are the structured reasoning layer for Helly, a recruiting system.

Rules:
- Evaluate only against the provided candidate, vacancy, and interview context.
- Be strict, concise, and evidence-based.
- Prefer explicit risks over vague praise.
- Return only the requested structured fields.
"""


def candidate_cv_prompt(source_text: str, source_type: str) -> str:
    return f"""Task: extract a structured candidate profile summary from the source below.

Required output intent:
- headline: 1 short sentence describing the candidate
- experience_excerpt: concise summary of the most relevant experience
- years_experience: integer if stated or strongly implied, otherwise null
- skills: normalized lowercase list of primary technologies, tools, and platforms

Source type: {source_type}
Candidate source:
{source_text}
"""


def candidate_summary_edit_prompt(base_summary: dict, edit_request_text: str) -> str:
    return f"""Task: merge a candidate's edit request into the existing structured summary.

Keep existing correct facts unless the user explicitly corrects them.
Preserve the same output structure.

Current summary:
{base_summary}

Candidate corrections:
{edit_request_text}
"""


def candidate_questions_prompt(text: str) -> str:
    return f"""Task: parse candidate mandatory profile answers from the text below.

Extract if present:
- salary_min
- salary_max
- salary_currency (USD, EUR, GBP)
- salary_period (month, year)
- location_text
- city
- country_code (ISO alpha-2)
- work_format (remote, hybrid, office)

Text:
{text}
"""


def vacancy_jd_prompt(source_text: str, source_type: str) -> str:
    return f"""Task: extract a structured vacancy summary from the job description below.

Extract if present:
- role_title
- seniority_normalized (junior, middle, senior)
- primary_tech_stack (normalized lowercase list)
- project_description_excerpt
- inconsistency issues

Source type: {source_type}
Job description:
{source_text}
"""


def vacancy_clarifications_prompt(text: str) -> str:
    return f"""Task: parse vacancy clarification answers from the text below.

Extract if present:
- role_title
- seniority_normalized (junior, middle, senior)
- budget_min
- budget_max
- budget_currency (USD, EUR, GBP)
- budget_period (month, year)
- countries_allowed_json (ISO alpha-2 codes)
- work_format (remote, hybrid, office)
- team_size
- project_description
- primary_tech_stack_json (normalized lowercase list)

Text:
{text}
"""


def interview_question_plan_prompt(vacancy_context: dict, candidate_summary: dict) -> str:
    return f"""Task: generate 5 to 7 short interview questions for this candidate-vacancy pair.

Requirements:
- questions must be specific to the vacancy
- questions must probe relevant experience, technical depth, delivery tradeoffs, and fit
- no greetings or meta commentary
- each question must be standalone and concise

Vacancy context:
{vacancy_context}

Candidate summary:
{candidate_summary}
"""


def interview_evaluation_prompt(
    candidate_summary: dict,
    vacancy_context: dict,
    answer_texts: list[str],
) -> str:
    return f"""Task: evaluate this interviewed candidate for the vacancy.

Return:
- final_score from 0.0 to 1.0
- strengths: short evidence-based bullets
- risks: short evidence-based bullets
- recommendation: advance or reject
- interview_summary: concise synthesis of the interview

Candidate summary:
{candidate_summary}

Vacancy context:
{vacancy_context}

Interview answers:
{answer_texts}
"""


def bot_controller_prompt(
    *,
    role: str | None,
    state: str | None,
    allowed_actions: list[str],
    latest_user_message: str,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: classify the latest user message and draft a workflow-safe Telegram reply.

Current role: {role}
Current state: {state}
Allowed actions: {allowed_actions}
Recent context: {recent_context or []}
Latest user message:
{latest_user_message}
"""


def interview_answer_parse_prompt(
    *,
    question_text: str,
    candidate_answer: str,
    candidate_summary: dict | None = None,
) -> str:
    return f"""Task: parse the interview answer into structured evidence.

Question:
{question_text}

Candidate answer:
{candidate_answer}

Candidate summary:
{candidate_summary or {}}
"""


def interview_followup_decision_prompt(
    *,
    question_text: str,
    question_kind: str,
    candidate_answer: str,
    candidate_summary: dict | None,
    vacancy_context: dict | None,
    follow_up_already_used: bool,
    answer_parse: dict | None,
) -> str:
    return f"""Task: decide whether this answer deserves one follow-up question.

Question kind: {question_kind}
Question:
{question_text}

Candidate answer:
{candidate_answer}

Candidate summary:
{candidate_summary or {}}

Vacancy context:
{vacancy_context or {}}

Parsed answer evidence:
{answer_parse or {}}

Follow-up already used for this topic: {follow_up_already_used}
"""
