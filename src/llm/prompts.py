from __future__ import annotations

import json

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


def contact_required_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the user means in the contact-required step.

Valid outcomes:
- help question or clarification
- unsupported free text that should be redirected back to sharing contact

Rules:
- treat questions like "why do you need my contact?", "can I skip?", "what if I do not want to share it?", and "what happens next?" as help
- do not pretend the user has already shared contact when they have not
- do not invent alternative completion methods if the product still requires contact at this step
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def role_selection_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the user means in the role-selection step.

Valid outcomes:
- help question or clarification
- explicit candidate role selection
- explicit hiring-manager role selection

Rules:
- treat questions like "what is the difference?", "which one should I choose?", and "what happens next?" as help
- only propose `candidate` when the user is clearly selecting the candidate role
- only propose `hiring_manager` when the user is clearly selecting the hiring manager role
- do not invent a role choice if the user is still undecided
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def manager_review_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the hiring manager means in the manager-review step.

Valid outcomes:
- help question or clarification
- explicit approve-candidate intent
- explicit reject-candidate intent

Rules:
- treat questions like "what does this mean?", "what are the risks?", "what are the strengths?", and "what happens if I approve?" as help
- only propose `approve_candidate` when the manager is clearly approving
- only propose `reject_candidate` when the manager is clearly rejecting
- do not invent an approval decision if the manager is still asking questions
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def pre_interview_review_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the hiring manager means in the candidate review step before direct contact sharing.

Valid outcomes:
- help question or clarification
- explicit connect-candidate intent for one numbered candidate
- explicit skip-candidate intent for one numbered candidate
- explicit update-vacancy intent

Rules:
- if the manager uses text instead of tapping buttons, they may still write things like `Connect 1`, `Approve 2`, `Interview 1`, or `Skip 3`
- only propose `interview_candidate` when the manager is clearly approving that numbered candidate for the next step
- only propose `skip_candidate` when the manager is clearly skipping that numbered candidate
- propose `update_vacancy_preferences` when the manager is clearly changing budget, format, city, countries, English, hiring stages, assessment requirements, project description, or stack after reviewing candidates
- if the manager is clearly updating the vacancy, include the original update request in `answer_text`
- extract the numbered candidate slot into `candidate_slot`
- treat questions like "what does this mean?", "why was candidate 1 selected?", and "what happens after connect?" as help
- do not invent a slot number if the manager did not specify one
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
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

Rules:
- this step is only about the generated summary of the candidate's role, experience, stack, domains, or responsibilities
- treat questions like "what happens next?", "why do you need approval?", "where did this come from?", and "what should I change?" as help
- treat messages about salary, work format, location, English level, domain preferences, assessment preferences, or verification as help, not as summary edits
- only propose `approve_summary` when the candidate is clearly approving the current summary
- only propose `request_summary_change` when the candidate is clearly correcting facts in the summary itself
- if the candidate says "edit it", "change it", or similar but gives no concrete correction, return the clarification outcome
- if the candidate is clearly requesting a correction, include the exact correction request in `edit_text`
- do not invent corrections
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

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
- treat coordination-only text like "here is my CV", "I will send it now", or "see attached" as help, not as CV input
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


def candidate_cv_processing_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means while Helly is still processing a CV or experience input.

Valid outcomes:
- help question or clarification about timing, what is happening now, or what comes next
- generic impatience / check-in message that should be answered without changing stage

Rules:
- do not treat the message as a new CV submission while processing is still in progress
- do not restart the flow
- do not redirect the user back to role selection
- explain briefly that the CV is still being processed and that a summary will be shown next
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
- work_format (remote, hybrid, office)
- location_text
- city
- country_code (ISO alpha-2)
- english_level (A1, A2, B1, B2, C1, C2, native)
- preferred_domains_json (use ["any"] if the candidate says there is no preference)
- show_take_home_task_roles
- show_live_coding_roles

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
- real profile answer that should be parsed for salary, work format, location, English level, domain preferences, or assessment preferences

Rules:
- this stage collects matching preferences one question at a time, but the candidate may answer several of them in one message
- treat questions like "gross or net?", "which currency?", "why do you need this?", "what happens next?", "how should I answer?", and "can I answer later?" as help, not as final profile answers
- treat short coordination-only messages like "ok", "next", "continue", or "got it" as help, not as profile answers
- only propose `send_salary_location_work_format` when the candidate is actually providing profile details for the current question or intentionally giving multiple matching-preference fields at once
- if the candidate is clearly answering, include the original answer in `answer_text`
- if the candidate is clearly answering the location question for office or hybrid work, city and country matter more than a vague location string
- do not assume missing profile values and do not convert generic agreement into structured data
- do not invent profile values here
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def candidate_ready_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means in the ready-for-matching step.

Valid outcomes:
- help question or status question
- explicit find-vacancies intent
- explicit update-preferences intent
- explicit delete-profile intent

Rules:
- treat questions like "what happens now?", "what should I do next?", "when will I hear back?", "when will I get opportunities?", and "do I need to do anything else?" as help, not as delete intent
- treat comments or questions about the Helly WebApp, CV Challenge, waiting time, or recent game results as help, not as delete intent
- propose `find_matching_vacancies` when the candidate is clearly asking to check current vacancies, look for jobs now, or see whether there is anything suitable right now
- propose `update_matching_preferences` when the candidate is clearly changing saved salary, work format, location, English, domain preferences, or assessment preferences
- if the candidate is clearly updating preferences, include the original update request in `answer_text`
- only propose `delete_profile` when the candidate is clearly asking to remove their profile
- do not invent matching outcomes or timelines
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def candidate_vacancy_review_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means in the matched-vacancy review step.

Valid outcomes:
- help question or clarification
- explicit apply intent for one numbered vacancy
- explicit skip intent for one numbered vacancy
- explicit update-preferences intent

Rules:
- if the candidate uses text instead of tapping buttons, they may still write things like `Apply 1`, `Connect 1`, `Skip 2`, or `Apply vacancy 3`
- only propose `apply_to_vacancy` when the candidate is clearly applying to or connecting with that numbered vacancy
- only propose `skip_vacancy` when the candidate is clearly skipping that numbered vacancy
- propose `update_matching_preferences` when the candidate is clearly changing salary, work format, location, English, domain preferences, or assessment preferences after reviewing roles
- if the candidate is clearly updating preferences, include the original update request in `answer_text`
- extract the numbered vacancy slot into `vacancy_slot`
- treat questions like "what does this mean?", "what happens after I apply?", "what happens after I connect?", and "how does this work?" as help
- do not invent a slot number if the candidate did not specify one
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def candidate_verification_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the candidate means in the verification-video step.

Valid outcomes:
- help question or clarification
- unsupported text that should stay in the verification step
- transcript debug request when the candidate asks what you actually heard in the last verification video

Rules:
- treat questions like "why do I need a video?", "what phrase should I say?", "can I do this later?", "I am on desktop", and "what happens after this?" as help
- treat questions like "what did you hear?", "what did you transcribe?", "what transcript did you get?", and similar wording as transcript debug requests
- do not claim verification is complete from text alone
- do not invent alternative completion methods unless they are already part of the current step guidance
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

Rules:
- this step is only about the generated vacancy summary of the role, seniority, stack, product context, or delivery scope
- treat questions like "what happens next?", "why do you need approval?", "where did this come from?", and "what should I change?" as help
- treat messages about budget, work format, office city, countries, English level, assessments, hiring stages, team details, or project clarifications as help, not as summary edits
- only propose `approve_summary` when the manager is clearly approving the current vacancy summary
- only propose `request_summary_change` when the manager is clearly correcting facts in the summary itself
- if the manager says "edit it", "change it", or similar but gives no concrete correction, return the clarification outcome
- if the manager is clearly requesting a correction, include the exact correction request in `edit_text`
- do not invent corrections
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def vacancy_intake_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the hiring manager means in the job description intake step.

Valid outcomes:
- help question or clarification about what can be sent
- real job description or role context that should be stored and processed

Rules:
- treat questions like "can I just paste the job details here?", "I don't have a formal JD", "what should I include?", "can I send voice?", "why do you need this?", and "what happens next?" as help, not as job description input
- only propose `send_job_description_text` when the manager is clearly providing the role description, requirements, stack, product context, or hiring details
- if the manager is clearly providing job-description input, include the original text in `job_description_text`
- do not invent vacancy details
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def vacancy_jd_processing_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the hiring manager means while Helly is still processing the job description.

Valid outcomes:
- help question or clarification about timing, what is happening now, or what comes next
- generic check-in message that should be answered without changing stage

Rules:
- do not treat the message as a new JD submission while processing is still in progress
- do not redirect the user back to role selection
- explain briefly that the vacancy summary is still being prepared and will appear next
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def vacancy_clarification_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the hiring manager means in the vacancy clarification step.

Valid outcomes:
- help question or clarification
- real clarification answer that should be parsed for vacancy details

Rules:
- this stage collects the remaining vacancy constraints one question at a time, but the manager may answer several of them in one message
- the possible fields here include budget, work format, office city, countries, required English, assessment steps, take-home payment, hiring stages, team size, project context, and primary stack
- treat questions like "what exactly do you still need?", "gross or net?", "which currency?", "what countries?", "what should I include?", "how should I answer?", "are approximate values okay?", and "what happens next?" as help, not as final clarification answers
- treat short coordination-only messages like "ok", "next", "continue", or "got it" as help, not as clarification answers
- only propose `send_vacancy_clarifications` when the manager is actually providing vacancy details for the current question or intentionally giving multiple vacancy constraints at once
- if the manager is clearly answering, include the original answer in `answer_text`
- do not assume missing vacancy values and do not convert generic agreement into structured data
- do not invent vacancy details
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

Latest user message:
{latest_user_message}
"""


def vacancy_open_decision_prompt(
    *,
    latest_user_message: str,
    current_step_guidance: str | None = None,
    recent_context: list[str] | None = None,
) -> str:
    return f"""Task: decide what the hiring manager means in the vacancy open step.

Valid outcomes:
- help question or status question
- explicit find-candidates intent
- explicit update-vacancy intent
- explicit create-another-vacancy intent
- explicit list-open-vacancies intent
- explicit delete-vacancy intent

Rules:
- treat questions like "what happens now?", "when will I see candidates?", "how does matching work?", and "do I need to do anything else?" as help, not as delete intent
- propose `find_matching_candidates` when the manager is clearly asking to search for candidates now, refresh matching, or check whether suitable candidates are available right now
- propose `update_vacancy_preferences` when the manager is clearly changing budget, format, city, countries, English, hiring stages, assessment requirements, project description, team size, or stack
- if the manager is clearly updating vacancy details, include the original update request in `answer_text`
- propose `create_new_vacancy` when the manager is clearly asking to open another vacancy, add one more role, or create a second vacancy
- propose `list_open_vacancies` when the manager is clearly asking to see, list, or review their active/open vacancies
- only propose `delete_vacancy` when the manager is clearly asking to remove the vacancy
- do not invent candidates or claim matching already produced results
- do not transition stages yourself

Current step guidance:
{current_step_guidance or ""}

Recent context:
{recent_context or []}

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
- work_format (remote, hybrid, office)
- office_city
- countries_allowed_json (ISO alpha-2 codes)
- required_english_level (A1, A2, B1, B2, C1, C2, native)
- has_take_home_task
- take_home_paid
- has_live_coding
- hiring_stages_json (normalized stage labels)
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
- if the candidate uses text instead of tapping buttons, they may still send `Accept interview` or `Skip opportunity`
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
    candidate_summary_json = json.dumps(candidate_summary or {}, ensure_ascii=False, indent=2)
    vacancy_context_json = json.dumps(vacancy_context or {}, ensure_ascii=False, indent=2)
    answer_texts_json = json.dumps(answer_texts or [], ensure_ascii=False, indent=2)
    return f"""Evaluate this interviewed candidate for the vacancy.

Use the available project inputs exactly as provided:
- `candidate_summary`: structured resume context derived from the CV/profile
- `vacancy_context`: role and hiring context
- `interview_answers`: ordered transcript-like answers from the interview

Return:
- final_score from 0.0 to 1.0
- strengths: short evidence-based bullets tied to fit for this vacancy
- risks: short evidence-based bullets tied to missing or weak signals for this vacancy
- recommendation: advance or reject
- interview_summary: recruiter-style 2-paragraph note

Candidate summary:
```json
{candidate_summary_json}
```

Vacancy context:
```json
{vacancy_context_json}
```

Interview answers:
```json
{answer_texts_json}
```
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
- explicit accept/skip decision for another pending interview invitation
- explicit cancel request for the current interview

Rules:
- treat clarification requests, repeat requests, timing questions, and "how should I answer" questions as help, not as interview answers
- treat "can I answer by voice/video" questions as help, not as interview answers
- only propose `accept_interview` or `skip_opportunity` when the candidate is explicitly responding to another interview invitation while this interview is active
- only propose `cancel_interview` when the candidate is explicitly asking to stop the current interview
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

Use the vacancy context, candidate profile snapshots, and deterministic scoring signals below.
Do not invent missing resume or vacancy facts.

Vacancy context:
{vacancy_context}

Shortlisted candidates:
{shortlisted_candidates}

Output requirements for each candidate:
- keep `rationale` to one concise sentence
- list up to 3 grounded `matched_signals`
- list up to 2 grounded `concerns`
- only mention concerns when they are real tradeoffs, not hidden rejections
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


def match_card_copy_prompt(
    *,
    audience: str,
    role_title: str | None,
    candidate_name: str | None = None,
    candidate_summary: str | None = None,
    project_summary: str | None = None,
    fit_reason: str | None = None,
    compensation_details: str | None = None,
    process_details: str | None = None,
    fit_band_label: str | None = None,
    gap_context: str | None = None,
    action_hint: str | None = None,
) -> str:
    return f"""Task: write a concise Telegram match card for Helly.

Audience: {audience}
Role title: {role_title or ""}
Candidate name: {candidate_name or ""}
Candidate summary: {candidate_summary or ""}
Project summary: {project_summary or ""}
Why it fits: {fit_reason or ""}
Compensation and work details: {compensation_details or ""}
Hiring/process details: {process_details or ""}
Fit level: {fit_band_label or ""}
Tradeoff or gap context: {gap_context or ""}
Action hint: {action_hint or ""}

Writing requirements:
- usually write 2 short paragraphs
- paragraph 1 should explain who or what was found and why it looks relevant
- paragraph 2 should include the key decision facts: money, format, location, English, or process, depending on the audience
- if there is a tradeoff, mention it naturally as an FYI, not as a robotic label
- keep it compact but decision-useful
- do not use bullets, labels, or markdown
"""


def deletion_confirmation_prompt(
    *,
    entity_type: str,
    entity_label: str | None,
    has_active_interview: bool,
    has_active_matches: bool,
) -> str:
    return f"""Task: draft a safe deletion confirmation message.

Entity type: {entity_type}
Entity label: {entity_label or ""}
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
