from __future__ import annotations

from src.candidate_profile.question_prompts import QUESTION_LABELS
from src.candidate_profile.questions import (
    enrich_candidate_question_payload_for_current_question,
)
from src.candidate_profile.verification import format_verification_phrase_feedback
from src.db.repositories.candidate_verifications import CandidateVerificationsRepository
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.interviews import InterviewsRepository
from src.graph.state import HellyGraphState
from src.llm.service import (
    safe_candidate_cv_decision,
    safe_candidate_cv_processing_decision,
    safe_candidate_ready_decision,
    safe_candidate_questions_decision,
    safe_candidate_summary_review_decision,
    safe_candidate_vacancy_review_decision,
    safe_candidate_verification_decision,
    safe_interview_invitation_decision,
    safe_interview_in_progress_decision,
    safe_parse_candidate_questions,
    safe_state_assistance_decision,
)
from src.orchestrator.policy import resolve_state_context
from src.shared.text import normalize_command_text


def _combined_recent_context(state: HellyGraphState) -> list[str]:
    combined: list[str] = []
    for item in list(state.recent_context) + list(state.knowledge_snippets):
        if item and item not in combined:
            combined.append(item)
    return combined


def _looks_like_questions_help_question(text: str) -> bool:
    normalized = normalize_command_text(text)
    lowered = (text or "").strip().lower()
    if not normalized:
        return True
    if (text or "").strip().endswith("?"):
        return True
    return any(
        token in lowered
        for token in [
            "why",
            "how",
            "help",
            "what next",
            "what happens after",
            "gross or net",
            "net or gross",
            "which currency",
            "what currency",
            "how should i answer",
            "почему",
            "зачем",
            "как ответить",
            "что дальше",
            "что потом",
            "пример",
            "валюта",
            "gross or net",
            "net or gross",
        ]
    )


def _looks_like_questions_non_answer(text: str) -> bool:
    normalized = normalize_command_text(text)
    if not normalized:
        return True
    if _looks_like_questions_help_question(text):
        return True
    return normalized in {
        "ok",
        "okay",
        "ок",
        "окей",
        "next",
        "continue",
        "дальше",
        "далее",
        "понял",
        "поняла",
        "ясно",
        "продолжай",
    }


def _current_question_repeat_text(state: HellyGraphState) -> str:
    label = QUESTION_LABELS.get(state.current_question_key or "", "current question")
    return (
        f"I still need your {label}. "
        "Send just the answer to the current question in one message and I’ll move on."
    )


def load_candidate_stage_context_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    state.allowed_actions = list(context.allowed_actions)
    state.missing_requirements = list(context.missing_requirements)
    if context.guidance_text and context.guidance_text not in state.recent_context:
        state.recent_context.append(context.guidance_text)
    return state


def load_candidate_stage_knowledge_node(state: HellyGraphState) -> HellyGraphState:
    context = resolve_state_context(role=state.role, state=state.active_stage)
    snippets = [context.goal, context.guidance_text]
    if context.help_text:
        snippets.append(context.help_text)
    state.knowledge_snippets = [item for item in snippets if item]
    return state

def build_candidate_stage_detect_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        text = state.latest_user_message or ""
        if state.active_stage == "CV_PENDING":
            decision = safe_candidate_cv_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("cv_text"):
                state.structured_payload = {"cv_text": payload.get("cv_text")}
            else:
                state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        if state.active_stage == "CV_PROCESSING":
            decision = safe_candidate_cv_processing_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            state.parsed_input["intent"] = "help"
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "SUMMARY_REVIEW":
            decision = safe_candidate_summary_review_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            elif state.intent == "needs_clarification":
                state.parsed_input["intent"] = "needs_clarification"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("edit_text"):
                state.structured_payload = {"edit_text": payload.get("edit_text")}
            else:
                state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "QUESTIONS_PENDING":
            decision = safe_candidate_questions_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            answer_text = payload.get("answer_text") or text
            parsed_payload = dict(safe_parse_candidate_questions(session, answer_text).payload or {})
            parsed_payload = enrich_candidate_question_payload_for_current_question(
                parsed=parsed_payload,
                text=answer_text,
                current_question_key=state.current_question_key,
            )
            if parsed_payload and not _looks_like_questions_non_answer(answer_text):
                state.proposed_action = "send_salary_location_work_format"
                state.structured_payload = parsed_payload
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text") or _current_question_repeat_text(state)
            return state
        elif state.active_stage == "VERIFICATION_PENDING":
            if state.latest_message_type == "video":
                state.intent = "stage_completion_input"
                state.parsed_input["intent"] = "stage_completion_input"
                state.proposed_action = "send_verification_video"
                state.structured_payload = {"submission_type": "video"}
                return state
            decision = safe_candidate_verification_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") == "show_last_verification_transcript":
                profiles = CandidateProfilesRepository(session)
                verifications = CandidateVerificationsRepository(session)
                profile = profiles.get_active_by_user_id(state.user_id)
                transcript_text = None
                verification = None
                if profile is not None:
                    verification = verifications.get_pending_by_profile_id(profile.id)
                    if verification is not None:
                        transcript_text = (
                            (verification.review_notes_json or {}).get("transcript_text")
                            if verification.review_notes_json
                            else None
                        )
                if transcript_text and verification is not None:
                    state.reply_text = (
                        f"{format_verification_phrase_feedback(expected_phrase=verification.phrase_text, spoken_text=transcript_text)} "
                        "If that looks wrong, resend the selfie video a bit slower and in a quieter place."
                    )
                elif verification is not None:
                    state.reply_text = (
                        "I do not have a usable transcript saved from the last video. "
                        f'You were supposed to say: "{verification.phrase_text}". '
                        "Please resend a short selfie video and say the phrase slowly in one take."
                    )
                else:
                    state.reply_text = (
                        "I do not have a usable transcript saved from the last video. "
                        "Please resend a short selfie video and say the phrase slowly in one take."
                    )
                state.parsed_input["intent"] = "help"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "READY":
            decision = safe_candidate_ready_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") == "update_matching_preferences":
                answer_text = payload.get("answer_text") or text
                parsed_payload = safe_parse_candidate_questions(session, answer_text).payload
                if parsed_payload:
                    state.proposed_action = "update_matching_preferences"
                    state.parsed_input["intent"] = "stage_completion_input"
                    state.structured_payload = parsed_payload
                else:
                    state.parsed_input["intent"] = "help"
                    state.follow_up_needed = True
                    state.follow_up_question = (
                        payload.get("response_text")
                        or "Tell me exactly what you want to change in salary, format, location, English, domains, or assessment preferences."
                    )
            elif payload.get("proposed_action") == "record_matching_feedback":
                state.proposed_action = "record_matching_feedback"
                state.parsed_input["intent"] = "stage_completion_input"
                state.structured_payload = {
                    "feedback_text": payload.get("answer_text") or text,
                    "source_stage": "READY",
                }
            elif payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
                state.structured_payload = {}
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "VACANCY_REVIEW":
            decision = safe_candidate_vacancy_review_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") == "update_matching_preferences":
                answer_text = payload.get("answer_text") or text
                parsed_payload = safe_parse_candidate_questions(session, answer_text).payload
                if parsed_payload:
                    state.proposed_action = "update_matching_preferences"
                    state.structured_payload = parsed_payload
                    state.parsed_input["intent"] = "stage_completion_input"
                else:
                    state.parsed_input["intent"] = "help"
                    state.follow_up_needed = True
                    state.follow_up_question = (
                        payload.get("response_text")
                        or "Tell me exactly what to change in salary, format, location, English, domains, or assessment preferences."
                    )
            elif payload.get("proposed_action") == "record_matching_feedback":
                state.proposed_action = "record_matching_feedback"
                state.structured_payload = {
                    "feedback_text": payload.get("answer_text") or text,
                    "source_stage": "VACANCY_REVIEW",
                }
                state.parsed_input["intent"] = "stage_completion_input"
            elif payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.structured_payload = {"vacancy_slot": payload.get("vacancy_slot")}
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "INTERVIEW_INVITED":
            decision = safe_interview_invitation_decision(
                session,
                latest_user_message=text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
            state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        elif state.active_stage == "INTERVIEW_IN_PROGRESS":
            current_question_text = None
            try:
                candidates = CandidateProfilesRepository(session)
                interviews = InterviewsRepository(session)
                candidate = candidates.get_active_by_user_id(state.user_id)
                if candidate is not None:
                    active_session = interviews.get_active_session_for_candidate(candidate.id)
                    if active_session is not None:
                        question = interviews.get_question_by_order(
                            active_session.id,
                            active_session.current_question_order,
                        )
                        if question is not None:
                            current_question_text = question.question_text
            except Exception:
                current_question_text = None

            decision = safe_interview_in_progress_decision(
                session,
                latest_user_message=text,
                current_question_text=current_question_text,
                current_step_guidance=state.follow_up_question or (state.recent_context[-1] if state.recent_context else None),
                recent_context=_combined_recent_context(state),
            )
            payload = dict(decision.payload or {})
            state.intent = payload.get("intent") or "help"
            state.reply_text = payload.get("response_text")
            state.parsed_input["agent_reason_code"] = payload.get("reason_code")
            if payload.get("proposed_action") is not None:
                state.proposed_action = payload.get("proposed_action")
                state.parsed_input["intent"] = "stage_completion_input"
            else:
                state.parsed_input["intent"] = "help"
            if payload.get("answer_text"):
                state.structured_payload = {"answer_text": payload.get("answer_text")}
            else:
                state.structured_payload = {}
            if payload.get("needs_follow_up"):
                state.follow_up_needed = True
                state.follow_up_question = payload.get("response_text")
            return state
        else:
            is_help = False
        state.parsed_input["intent"] = "help" if is_help else "candidate_input"
        return state

    return _node


def detect_candidate_stage_intent_node(state: HellyGraphState) -> HellyGraphState:
    text = state.latest_user_message or ""
    if state.active_stage == "CV_PENDING":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "CV_PROCESSING":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "SUMMARY_REVIEW":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "QUESTIONS_PENDING":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "VERIFICATION_PENDING":
        if state.latest_message_type == "video":
            state.intent = "stage_completion_input"
            state.parsed_input["intent"] = "stage_completion_input"
            state.proposed_action = "send_verification_video"
            state.structured_payload = {"submission_type": "video"}
            return state
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "READY":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "VACANCY_REVIEW":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "INTERVIEW_INVITED":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    elif state.active_stage == "INTERVIEW_IN_PROGRESS":
        state.intent = "help"
        state.parsed_input["intent"] = "help"
        return state
    else:
        is_help = False
    state.parsed_input["intent"] = "help" if is_help else "candidate_input"
    return state


def build_candidate_stage_reply_node(session):
    def _node(state: HellyGraphState) -> HellyGraphState:
        context = resolve_state_context(role=state.role, state=state.active_stage)
        state.stage_status = "in_progress"
        state.follow_up_needed = False
        state.confidence = 0.85
        if state.parsed_input.get("intent") == "help":
            if state.active_stage == "QUESTIONS_PENDING":
                if _looks_like_questions_help_question(state.latest_user_message):
                    state.reply_text = state.reply_text or _current_question_repeat_text(state)
                else:
                    state.reply_text = _current_question_repeat_text(state)
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
                return state
            if state.active_stage == "INTERVIEW_IN_PROGRESS" and state.reply_text:
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
                return state
            result = safe_state_assistance_decision(
                session,
                context=context,
                latest_user_message=state.latest_user_message,
                recent_context=_combined_recent_context(state),
            )
            state.reply_text = result.payload.get("response_text") or context.help_text or context.guidance_text
            state.follow_up_needed = True
            state.follow_up_question = context.guidance_text
            return state

        if state.active_stage == "CV_PENDING" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            state.reply_text = "Thanks. I will use this experience summary to prepare your profile."
            state.confidence = 0.9
            return state

        if state.active_stage == "SUMMARY_REVIEW":
            if state.parsed_input.get("intent") == "needs_clarification":
                state.reply_text = "Tell me exactly what is incorrect in the summary, and I will update it once."
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
                return state
            if state.parsed_input.get("intent") == "help":
                state.reply_text = state.reply_text or context.help_text or context.guidance_text
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
                return state
            if state.parsed_input.get("intent") == "stage_completion_input":
                state.stage_status = "ready_for_transition"
                if state.proposed_action == "approve_summary":
                    state.reply_text = state.reply_text or "Thanks. I will approve the summary and move to the next step."
                else:
                    state.reply_text = state.reply_text or "Thanks. I will update the summary based on your correction."
                state.confidence = 0.9
                return state

        if state.active_stage == "QUESTIONS_PENDING":
            if state.parsed_input.get("intent") == "stage_completion_input" and state.proposed_action == "send_salary_location_work_format":
                state.stage_status = "ready_for_transition"
                state.reply_text = "Thanks. I will update your profile details from this answer."
                state.confidence = 0.9
            else:
                state.reply_text = state.reply_text or context.guidance_text
                state.follow_up_needed = True
                state.follow_up_question = state.reply_text
            return state

        if (
            state.active_stage == "VERIFICATION_PENDING"
            and state.parsed_input.get("intent") == "stage_completion_input"
            and state.latest_message_type == "video"
        ):
            state.stage_status = "ready_for_transition"
            state.reply_text = "Thanks. I will use this video to complete your verification step."
            state.confidence = 0.95
            return state

        if state.active_stage == "READY" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            # Let the downstream candidate service produce the user-facing reply for
            # READY-stage actions so we don't emit a duplicate transport message.
            state.reply_text = None
            state.confidence = 0.9
            return state

        if state.active_stage == "VACANCY_REVIEW" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            state.reply_text = None
            state.confidence = 0.9
            return state

        if state.active_stage == "INTERVIEW_INVITED" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            if state.proposed_action == "accept_interview":
                state.reply_text = "Thanks. I will start the interview."
            else:
                state.reply_text = "Understood. I will skip this opportunity."
            state.confidence = 0.9
            return state

        if state.active_stage == "INTERVIEW_IN_PROGRESS" and state.parsed_input.get("intent") == "stage_completion_input":
            state.stage_status = "ready_for_transition"
            if state.proposed_action == "answer_current_question":
                state.reply_text = "Thanks. I will use this answer and continue the interview."
            else:
                state.reply_text = None
            state.confidence = 0.9
            return state

        state.reply_text = None
        state.proposed_action = None
        return state

    return _node
