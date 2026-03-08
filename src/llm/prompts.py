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


STATE_ASSISTANCE_SYSTEM_PROMPT = """You are the state-aware assistance layer for Helly.

Purpose:
- answer a user's help, clarification, or constraint message inside one active workflow state
- keep the user inside the same state unless the backend separately processes valid business input
- suggest valid alternative ways to satisfy the same requirement

Rules:
- never claim that a required step can be skipped unless the backend already allows it
- never invent business data or say a transition already happened
- keep the reply concise, supportive, and practical
- answer the user's question directly, then guide them to a valid next action for the same state
- return structured JSON only
"""


def candidate_cv_prompt(source_text: str, source_type: str) -> str:
    return f"""Now analyze the following candidate CV source for Helly and return the requested structured output.

Required output intent:
- headline: one concise role-focused headline
- experience_excerpt: concise recruiter-usable summary of the most relevant experience
- years_experience: integer if stated or strongly implied, otherwise null
- skills: normalized lowercase list of primary technologies, tools, and platforms
- approval_summary_text: exactly 3 sentences in second person for candidate approval in chat

Rules for approval_summary_text:
- start with "You are [Candidate Name]" if the candidate name is clearly available
- otherwise start with "You are a [main role]"
- sentence 1 covers role and approximate years of experience
- sentence 2 covers main technologies, infrastructure, or technical strengths
- sentence 3 covers domains, product scale, or system types if available
- do not invent technologies, companies, domains, or years
- keep it concise, professional, and natural to read in Telegram

Source type: {source_type}

CV:
{source_text}
"""


def candidate_summary_edit_prompt(base_summary: dict, edit_request_text: str) -> str:
    return f"""Task: merge a candidate's edit request into the existing structured summary.

Keep existing correct facts unless the user explicitly corrects them.
Preserve the same output structure, including `approval_summary_text`.

Current summary:
{base_summary}

Candidate corrections:
{edit_request_text}
"""


def candidate_summary_review_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means in the summary review step.

Valid outcomes:
- help question or clarification
- explicit summary approval
- explicit summary correction request
- request for clarification because the candidate said they want to edit but gave no details

Current step guidance: {current_step_guidance or ""}
Recent context: {recent_context or []}

Latest user message:
{latest_user_message}
"""


def candidate_cv_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means in the CV or experience submission step.

Valid outcomes:
- help question or clarification about what can be submitted
- real CV or experience input that should be stored and processed

Rules:
- treat questions like "what should I send?", "I don't have a CV", "can I use LinkedIn?", "can I send voice?", "why do you need this?", and "what happens next?" as help, not as CV input
- only propose `send_cv_text` when the candidate is clearly providing resume text, experience details, or a useful work-history summary
- if the candidate is clearly providing experience input, include the original text in `cv_text`
- do not invent candidate experience
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
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


def candidate_questions_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means in the mandatory questions step.

Valid outcomes:
- help question or clarification
- real profile answer that should be parsed for salary, location, and work format

Rules:
- treat questions like "gross or net?", "which currency?", "why do you need this?", "what happens next?", and "how should I answer?" as help, not as final profile answers
- only propose `send_salary_location_work_format` when the candidate is actually providing their profile details
- if the candidate is clearly answering, include the original answer in `answer_text`
- do not invent salary, location, or work format values here
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def vacancy_jd_prompt(source_text: str, source_type: str) -> str:
    return f"""Task: extract a structured vacancy summary from the job description below.

Extract if present:
- role_title
- seniority_normalized (junior, middle, senior)
- primary_tech_stack (normalized lowercase list)
- project_description_excerpt
- approval_summary_text: exactly 3 or 4 concise manager-facing sentences for approval in chat
- inconsistency issues

Rules for approval_summary_text:
- describe the vacancy in concise professional English
- do not dump raw extracted fields
- sentence 1 should describe the role and seniority when available
- sentence 2 should describe the main stack or technical focus
- sentence 3 or 4 should describe product, domain, work context, or key delivery scope
- do not invent details not grounded in the job description

Source type: {source_type}
Job description:
{source_text}
"""


def vacancy_summary_edit_prompt(base_summary: dict, edit_request_text: str) -> str:
    return f"""Task: merge a hiring manager's correction into the existing structured vacancy summary.

Keep existing correct facts unless the manager explicitly corrects them.
Preserve the same output structure, including `approval_summary_text`.

Current summary:
{base_summary}

Manager corrections:
{edit_request_text}
"""


def vacancy_summary_review_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the hiring manager means in the vacancy summary review step.

Valid outcomes:
- help question or clarification
- explicit summary approval
- explicit summary correction request
- request for clarification because the manager said they want to edit but gave no details

Current step guidance: {current_step_guidance or ""}
Recent context: {recent_context or []}

Latest user message:
{latest_user_message}
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


def delete_confirmation_decision_prompt(
    *,
    latest_user_message: str,
    entity_label: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the user means in a delete confirmation step.

Entity being discussed:
{entity_label}

Valid outcomes:
- help question or clarification about deletion consequences
- explicit confirmation to delete
- explicit cancellation / keep intent

Rules:
- treat questions like "what exactly will be cancelled?", "can I cancel this?", "why?", and "what happens?" as help, not as confirmation
- only propose `confirm_delete` when the user is explicitly confirming deletion
- only propose `cancel_delete` when the user is explicitly cancelling deletion or saying they want to keep the entity
- do not invent side effects
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def interview_invitation_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means in the interview invitation step.

Valid outcomes:
- help question or clarification about the interview invitation
- explicit acceptance of the interview
- explicit skip or decline of the opportunity

Rules:
- treat questions like "what is this?", "how long will it take?", "can I answer by voice?", "what happens if I skip?", and "why was I invited?" as help, not as accept/skip
- only propose `accept_interview` when the candidate is clearly accepting the interview
- only propose `skip_opportunity` when the candidate is clearly declining or skipping the opportunity
- do not invent interview details
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def interview_question_plan_prompt(vacancy_context: dict, candidate_summary: dict, cv_text: str | None = None) -> str:
    return f"""Task: generate 5 to 7 short interview questions for this candidate-vacancy pair.

Requirements:
- questions must be specific to the vacancy
- questions must be grounded in the candidate's actual CV text and not invent projects or technologies
- questions must probe relevant experience, technical depth, delivery tradeoffs, and fit
- no greetings or meta commentary
- each question must be standalone and concise

Vacancy context:
{vacancy_context}

Candidate summary:
{candidate_summary}

Candidate CV text:
{cv_text or ""}
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


def interview_in_progress_decision_prompt(
    *,
    latest_user_message: str,
    current_question_text: str | None = None,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means during an active interview question.

Valid outcomes:
- help question or clarification about the current interview question
- real answer to the current interview question

Rules:
- treat clarification requests, repeat requests, timing questions, and "how should I answer" questions as help, not as interview answers
- treat "can I answer by voice/video" questions as help, not as interview answers
- only propose `answer_current_question` when the message is actually answering the current interview question
- if the candidate is clearly answering, include the answer in `answer_text`
- do not invent interview content or rewrite the answer

Current interview question:
{current_question_text or ""}

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def bot_controller_prompt(
    *,
    role: str | None,
    state: str | None,
    state_goal: str | None,
    allowed_actions: list[str],
    blocked_actions: list[str] | None,
    missing_requirements: list[str] | None,
    current_step_guidance: str | None,
    latest_user_message: str,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: classify the latest user message and draft a workflow-safe Telegram reply.

Current role: {role}
Current state: {state}
State goal: {state_goal}
Allowed actions: {allowed_actions}
Blocked actions: {blocked_actions or []}
Missing requirements: {missing_requirements or []}
Current step guidance: {current_step_guidance or ""}
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


def interview_session_conductor_prompt(
    *,
    mode: str,
    candidate_first_name: str | None,
    candidate_summary: dict | None,
    vacancy_context: dict | None,
    interview_plan: list[dict] | None,
    current_question: dict | None,
    candidate_answer: str | None,
    answer_quality: str | None,
    follow_up_used: bool,
    follow_up_reason: str | None,
) -> str:
    return f"""Task: conduct a single Telegram interview turn for Helly.

Mode: {mode}
Candidate first name: {candidate_first_name}
Candidate summary:
{candidate_summary or {}}

Vacancy context:
{vacancy_context or {}}

Interview plan:
{interview_plan or []}

Current question:
{current_question or {}}

Candidate answer:
{candidate_answer or ""}

Answer quality:
{answer_quality}

Follow-up already used:
{follow_up_used}

Follow-up reason:
{follow_up_reason}
"""


def candidate_rerank_prompt(*, vacancy_context: dict, shortlisted_candidates: list[dict]) -> str:
    return f"""Task: rerank already-shortlisted candidates for this vacancy.

Vacancy context:
{vacancy_context}

Shortlisted candidates:
{shortlisted_candidates}
"""


def vacancy_inconsistency_detect_prompt(*, source_text: str, summary: dict) -> str:
    return f"""Task: detect meaningful inconsistencies or ambiguities in this vacancy draft.

Original JD text:
{source_text}

Extracted vacancy summary:
{summary}
"""


def response_copywriter_prompt(*, approved_intent: str) -> str:
    return f"""Task: rewrite this approved response intent into concise Telegram copy.

Approved response intent:
{approved_intent}
"""


def deletion_confirmation_prompt(
    *,
    entity_type: str,
    has_active_interview: bool,
    has_active_matches: bool,
) -> str:
    return f"""Task: draft a safe deletion confirmation message.

Entity type: {entity_type}
Has active interview: {has_active_interview}
Has active matches: {has_active_matches}
"""


def small_talk_prompt(*, latest_user_message: str, current_step_guidance: str | None) -> str:
    return f"""Task: reply to light conversational input without losing workflow control.

Latest user message:
{latest_user_message}

Current step guidance:
{current_step_guidance or ""}
"""


def recovery_prompt(*, state: str | None, allowed_actions: list[str], latest_user_message: str) -> str:
    return f"""Task: generate a recovery message for invalid or off-flow input.

Current state: {state}
Allowed actions: {allowed_actions}
Latest user message:
{latest_user_message}
"""


def role_selection_prompt(*, latest_user_message: str | None = None) -> str:
    return f"""Task: help the user choose between Candidate and Hiring Manager.

Latest user message:
{latest_user_message or ""}
"""


def interview_invitation_copy_prompt(*, role_title: str | None) -> str:
    return f"""Task: write interview invitation copy for a matched candidate.

Vacancy role title:
{role_title or ""}
"""
