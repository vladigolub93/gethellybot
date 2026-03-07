from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StatePolicyDefinition:
    state: str
    goal: str
    allowed_actions: list[str]
    guidance_text: str
    assistance_prompt_slug: str | None = None
    help_text: str | None = None
    missing_requirements: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedStateContext:
    role: str | None
    state: str
    goal: str
    allowed_actions: list[str]
    guidance_text: str
    assistance_prompt_slug: str | None
    help_text: str | None
    missing_requirements: list[str]
    blocked_actions: list[str]


STATE_POLICY_DEFINITIONS: dict[str, StatePolicyDefinition] = {
    "CONTACT_REQUIRED": StatePolicyDefinition(
        state="CONTACT_REQUIRED",
        goal="Collect a valid Telegram contact before onboarding begins.",
        allowed_actions=["share_contact"],
        assistance_prompt_slug="contact_required",
        guidance_text="Please share your contact using the button below to continue.",
        help_text=(
            "Helly needs your contact so it can link your Telegram account to one profile and continue onboarding. "
            "Please share your contact using the button below to continue."
        ),
        missing_requirements=["contact"],
    ),
    "CONSENT_REQUIRED": StatePolicyDefinition(
        state="CONSENT_REQUIRED",
        goal="Collect explicit data-processing consent before profile creation.",
        allowed_actions=["reply_i_agree"],
        assistance_prompt_slug="consent_required",
        guidance_text="Please confirm data processing consent to continue.",
        help_text="Helly needs your consent before storing profile data. Please confirm data processing consent to continue.",
        missing_requirements=["data_processing_consent"],
    ),
    "ROLE_SELECTION": StatePolicyDefinition(
        state="ROLE_SELECTION",
        goal="Choose whether the user is onboarding as a candidate or hiring manager.",
        allowed_actions=["candidate", "hiring manager"],
        assistance_prompt_slug="role_selection",
        guidance_text="Choose your role: Candidate or Hiring Manager.",
        help_text="Choose Candidate if you are looking for a job, or Hiring Manager if you want to hire for a role.",
        missing_requirements=["role_selection"],
    ),
    "CV_PENDING": StatePolicyDefinition(
        state="CV_PENDING",
        goal="Collect usable candidate experience input.",
        allowed_actions=["send_cv_text", "send_cv_document", "send_cv_voice"],
        assistance_prompt_slug="candidate_cv_pending",
        guidance_text=(
            "You can upload a CV, paste your work experience as text, send a voice description, "
            "or export your LinkedIn profile as PDF and send it here."
        ),
        help_text=(
            "No problem if you do not have a CV. You can paste your work experience as text, "
            "send a voice description, or export your LinkedIn profile as PDF and send it here."
        ),
        missing_requirements=["candidate_experience_source"],
    ),
    "CV_PROCESSING": StatePolicyDefinition(
        state="CV_PROCESSING",
        goal="Wait for CV parsing and summary generation to complete.",
        allowed_actions=["wait_for_summary"],
        guidance_text="Your experience is being processed. Please wait a moment while I prepare the summary.",
        help_text="Your experience is being processed right now. Please wait a moment while I prepare the summary.",
    ),
    "SUMMARY_REVIEW": StatePolicyDefinition(
        state="SUMMARY_REVIEW",
        goal="Get approval for the generated summary or collect one correction round.",
        allowed_actions=["approve_summary", "request_summary_change"],
        assistance_prompt_slug="candidate_summary_review",
        guidance_text=(
            "Review the summary and either approve it or tell me exactly what is incorrect. "
            "You can request one correction round."
        ),
        help_text=(
            "Review the summary and either approve it or tell me exactly what is incorrect. "
            "You can request one correction round before final approval."
        ),
        missing_requirements=["summary_approval"],
    ),
    "QUESTIONS_PENDING": StatePolicyDefinition(
        state="QUESTIONS_PENDING",
        goal="Collect salary expectations, location, and preferred work format.",
        allowed_actions=["send_salary_location_work_format"],
        assistance_prompt_slug="candidate_questions_pending",
        guidance_text=(
            "Send your salary expectations, current location, and preferred work format "
            "(remote, hybrid, or office). You can answer in one message."
        ),
        help_text=(
            "I need your salary expectations, current location, and preferred work format "
            "to match you with relevant roles correctly. You can answer in one message."
        ),
        missing_requirements=["salary", "location", "work_format"],
    ),
    "VERIFICATION_PENDING": StatePolicyDefinition(
        state="VERIFICATION_PENDING",
        goal="Collect a verification video with the required phrase.",
        allowed_actions=["send_verification_video"],
        assistance_prompt_slug="candidate_verification_pending",
        guidance_text="Please record a short verification video saying the phrase shown in the chat.",
        help_text=(
            "Verification helps confirm that a real candidate is completing the profile. "
            "Please record a short video saying the phrase shown in the chat."
        ),
        missing_requirements=["verification_video"],
    ),
    "READY": StatePolicyDefinition(
        state="READY",
        goal="Keep the candidate profile ready for matching.",
        allowed_actions=["wait_for_match", "delete_profile"],
        assistance_prompt_slug="candidate_ready",
        guidance_text="Your profile is ready. Helly will contact you when a strong match is found.",
        help_text="Your profile is ready. Helly will contact you only when a strong match is found.",
    ),
    "INTAKE_PENDING": StatePolicyDefinition(
        state="INTAKE_PENDING",
        goal="Collect a usable job description source.",
        allowed_actions=["send_job_description_text", "send_job_description_document", "send_job_description_voice"],
        assistance_prompt_slug="vacancy_intake_pending",
        guidance_text=(
            "You can send a formal JD, paste the role details as text, or send a voice description "
            "of the position and requirements."
        ),
        help_text=(
            "If you do not have a formal JD, you can paste the role details as text or send a voice description "
            "of the position, stack, and hiring constraints."
        ),
        missing_requirements=["job_description_source"],
    ),
    "JD_PROCESSING": StatePolicyDefinition(
        state="JD_PROCESSING",
        goal="Wait for JD parsing and vacancy draft generation to complete.",
        allowed_actions=["wait_for_vacancy_analysis"],
        guidance_text="The job description is being processed. Clarification questions will follow if needed.",
        help_text="The job description is being processed. Clarification questions will follow if needed.",
    ),
    "CLARIFICATION_QA": StatePolicyDefinition(
        state="CLARIFICATION_QA",
        goal="Resolve mandatory vacancy fields before opening the vacancy.",
        allowed_actions=["send_vacancy_clarifications"],
        assistance_prompt_slug="vacancy_clarification_qa",
        guidance_text=(
            "Please provide the missing vacancy details such as budget, countries, work format, "
            "team context, project description, and main stack."
        ),
        help_text=(
            "I need the missing vacancy details so Helly can match correctly. "
            "That usually includes budget, countries, work format, team context, project description, and main stack."
        ),
        missing_requirements=["vacancy_clarifications"],
    ),
    "OPEN": StatePolicyDefinition(
        state="OPEN",
        goal="Keep the vacancy active for matching and candidate review.",
        allowed_actions=["wait_for_matches", "delete_vacancy"],
        assistance_prompt_slug="vacancy_open",
        guidance_text="The vacancy is open. Helly is matching candidates and will only send qualified profiles.",
        help_text="The vacancy is open. Helly is matching candidates and will only send qualified profiles.",
    ),
    "INTERVIEW_INVITED": StatePolicyDefinition(
        state="INTERVIEW_INVITED",
        goal="Get a clear accept or skip decision for the interview invitation.",
        allowed_actions=["accept_interview", "skip_opportunity"],
        assistance_prompt_slug="interview_invited",
        guidance_text="You can accept the interview or skip this opportunity.",
        help_text="You can accept the interview or skip this opportunity. The interview is short and happens inside Telegram.",
        missing_requirements=["interview_invitation_response"],
    ),
    "INTERVIEW_IN_PROGRESS": StatePolicyDefinition(
        state="INTERVIEW_IN_PROGRESS",
        goal="Complete the active interview one question at a time.",
        allowed_actions=["answer_current_question"],
        assistance_prompt_slug="interview_in_progress",
        guidance_text="Please answer the current interview question. You can reply in text, voice, or video.",
        help_text="Please answer the current interview question. You can reply in text, voice, or video.",
        missing_requirements=["current_interview_answer"],
    ),
    "MANAGER_REVIEW": StatePolicyDefinition(
        state="MANAGER_REVIEW",
        goal="Get a clear approve or reject decision for the reviewed candidate.",
        allowed_actions=["approve_candidate", "reject_candidate"],
        assistance_prompt_slug="manager_review",
        guidance_text="Review the candidate package and reply with approve or reject.",
        help_text=(
            "Review the candidate package and decide whether to approve or reject the candidate. "
            "You can also ask what the evaluation means before deciding."
        ),
        missing_requirements=["manager_decision"],
    ),
    "DELETE_CONFIRMATION": StatePolicyDefinition(
        state="DELETE_CONFIRMATION",
        goal="Get an explicit confirm or cancel decision before destructive deletion.",
        allowed_actions=["confirm_delete", "cancel_delete"],
        assistance_prompt_slug="delete_confirmation",
        guidance_text="Please confirm deletion or cancel it.",
        help_text=(
            "Deletion requires explicit confirmation. You can confirm deletion or cancel it if you want to keep the current profile or vacancy."
        ),
        missing_requirements=["explicit_delete_confirmation"],
    ),
}


def resolve_state_context(*, role: str | None, state: str | None) -> ResolvedStateContext:
    effective_state = state or "ROLE_SELECTION"
    definition = STATE_POLICY_DEFINITIONS.get(
        effective_state,
        StatePolicyDefinition(
            state=effective_state,
            goal="Continue the current workflow step safely.",
            allowed_actions=[],
            guidance_text="Please continue with the current step.",
        ),
    )
    return ResolvedStateContext(
        role=role,
        state=definition.state,
        goal=definition.goal,
        allowed_actions=list(definition.allowed_actions),
        guidance_text=definition.guidance_text,
        assistance_prompt_slug=definition.assistance_prompt_slug,
        help_text=definition.help_text,
        missing_requirements=list(definition.missing_requirements),
        blocked_actions=list(definition.blocked_actions),
    )
