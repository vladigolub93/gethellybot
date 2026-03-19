from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.candidate_profile.question_prompts import (
    QUESTION_KEYS,
    follow_up_prompt,
    initial_questions_prompt,
    missing_questions_prompt,
    question_prompt,
)
from src.candidate_profile.questions import (
    current_candidate_question_key,
    enrich_candidate_question_payload_for_current_question,
    filter_candidate_question_payload,
    missing_candidate_question_keys,
)
from src.candidate_profile.work_formats import candidate_work_formats
from src.candidate_profile.verification import build_verification_phrase
from src.candidate_profile.verification import format_verification_phrase_feedback
from src.candidate_profile.verification import phrase_matches_verification
from src.cv_challenge.service import CandidateCvChallengeService
from src.candidate_profile.states import (
    CANDIDATE_STATE_CONSENTED,
    CANDIDATE_STATE_CONTACT_COLLECTED,
    CANDIDATE_STATE_CV_PENDING,
    CANDIDATE_STATE_CV_PROCESSING,
    CANDIDATE_STATE_NEW,
    CANDIDATE_STATE_QUESTIONS_PENDING,
    CANDIDATE_STATE_READY,
    CANDIDATE_STATE_ROLE_CONFIRMED,
    CANDIDATE_STATE_SUMMARY_REVIEW,
    CANDIDATE_STATE_VERIFICATION_PENDING,
)
from src.db.repositories.candidate_verifications import CandidateVerificationsRepository
from src.db.repositories.files import FilesRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.ingestion.service import ContentIngestionService, ContentQualityError
from src.jobs.db_queue import DatabaseQueueClient
from src.jobs.queue import JobMessage
from src.llm.service import safe_build_deletion_confirmation, safe_parse_candidate_questions
from src.messaging.service import MessagingService
from src.state.service import StateService
from src.telegram.keyboards import candidate_cv_challenge_keyboard


@dataclass(frozen=True)
class CandidateIntakeResult:
    status: str
    notification_template: str


@dataclass(frozen=True)
class CandidateSummaryReviewResult:
    status: str
    notification_template: str


@dataclass(frozen=True)
class CandidateQuestionsResult:
    status: str
    notification_template: str
    notification_text: str


@dataclass(frozen=True)
class CandidateVerificationResult:
    status: str
    notification_template: str
    notification_text: str


@dataclass(frozen=True)
class CandidateDeletionResult:
    status: str
    notification_template: str
    notification_text: str


@dataclass(frozen=True)
class CandidateReadyActionResult:
    status: str
    notification_template: str
    notification_text: str
    reply_markup: Optional[dict] = None


class CandidateProfileService:
    _TEXT_CV_META_PREFIXES = (
        "here is my cv",
        "here's my cv",
        "here is my resume",
        "here's my resume",
        "sending my cv",
        "sending my resume",
        "i will send my cv",
        "i'll send my cv",
        "i will send it now",
        "i'll send it now",
        "send it now",
        "one sec",
        "one second",
        "wait a sec",
        "hold on",
        "see attached",
        "attached here",
        "cv attached",
        "resume attached",
    )

    def __init__(self, session: Session):
        self.session = session
        self.repo = CandidateProfilesRepository(session)
        self.verifications = CandidateVerificationsRepository(session)
        self.files = FilesRepository(session)
        self.interviews = InterviewsRepository(session)
        self.matching = MatchingRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.messaging = MessagingService(session)
        self.state_service = StateService(session)
        self.queue = DatabaseQueueClient(session)
        self.cv_challenge = CandidateCvChallengeService(session)

    def _copy(self, approved_intent: str) -> str:
        return self.messaging.compose(approved_intent)

    @staticmethod
    def _normalize_text_cv_input(text: Optional[str]) -> str:
        return " ".join((text or "").split()).strip()

    @classmethod
    def _text_cv_needs_more_detail(cls, text: Optional[str]) -> bool:
        normalized = cls._normalize_text_cv_input(text)
        lowered = normalized.lower()
        if not normalized:
            return True
        if lowered in cls._TEXT_CV_META_PREFIXES:
            return True
        if any(
            lowered.startswith(f"{prefix}.") or lowered.startswith(f"{prefix},")
            for prefix in cls._TEXT_CV_META_PREFIXES
        ):
            return True
        return len(normalized) < 24 and len(normalized.split()) < 4

    def ensure_profile_for_user(self, user) -> object:
        profile = self.repo.get_active_by_user_id(user.id)
        if profile is not None:
            return profile

        profile = self.repo.create(user_id=user.id, state=CANDIDATE_STATE_NEW)
        self.state_service.record_transition(
            entity_type="candidate_profile",
            entity_id=profile.id,
            from_state=None,
            to_state=CANDIDATE_STATE_NEW,
            trigger_type="system",
            actor_user_id=user.id,
            metadata_json={"reason": "candidate profile created"},
        )
        return profile

    def start_onboarding(self, user, *, trigger_ref_id=None) -> object:
        profile = self.ensure_profile_for_user(user)

        if profile.state == CANDIDATE_STATE_NEW:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_CONTACT_COLLECTED,
                trigger_type="system",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
                metadata_json={"reason": "contact already collected before candidate profile creation"},
            )

        if profile.state == CANDIDATE_STATE_CONTACT_COLLECTED:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_CONSENTED,
                trigger_type="system",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
                metadata_json={"reason": "consent already collected before candidate profile creation"},
            )

        if profile.state == CANDIDATE_STATE_CONSENTED:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_ROLE_CONFIRMED,
                trigger_type="user_action",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
                metadata_json={"role": "candidate"},
            )

        if profile.state == CANDIDATE_STATE_ROLE_CONFIRMED:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_CV_PENDING,
                trigger_type="system",
                trigger_ref_id=trigger_ref_id,
                actor_user_id=user.id,
            )

        return profile

    def handle_cv_intake(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        text: Optional[str] = None,
        file_id=None,
    ) -> CandidateIntakeResult:
        profile = self.ensure_profile_for_user(user)

        if profile.state != CANDIDATE_STATE_CV_PENDING:
            return CandidateIntakeResult(
                status="ignored",
                notification_template="candidate_input_not_expected",
            )

        source_type = {
            "text": "pasted_text",
            "document": "document_upload",
            "voice": "voice_description",
        }.get(content_type, "unsupported")

        if source_type == "unsupported":
            return CandidateIntakeResult(
                status="unsupported",
                notification_template="candidate_input_unsupported",
            )

        if content_type == "text":
            text = self._normalize_text_cv_input(text)
            if self._text_cv_needs_more_detail(text):
                return CandidateIntakeResult(
                    status="needs_more_detail",
                    notification_template="candidate_cv_needs_more_detail",
                )

        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state=CANDIDATE_STATE_CV_PROCESSING,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
            metadata_json={"content_type": content_type},
        )

        version = self.repo.create_version(
            profile_id=profile.id,
            version_no=self.repo.next_version_no(profile.id),
            source_type=source_type,
            source_file_id=file_id,
            source_raw_message_id=raw_message_id,
            extracted_text=text if content_type == "text" else None,
            transcript_text=text if content_type == "voice" else None,
        )
        self.repo.set_current_version(profile, version.id)
        self.queue.enqueue(
            JobMessage(
                job_type="candidate_cv_extract_v1",
                payload={
                    "candidate_profile_id": str(profile.id),
                    "candidate_profile_version_id": str(version.id),
                    "source_type": source_type,
                },
                idempotency_key=f"candidate_cv_extract_v1:{version.id}",
                entity_type="candidate_profile_version",
                entity_id=version.id,
            )
        )

        return CandidateIntakeResult(
            status="accepted",
            notification_template="candidate_cv_received_processing",
        )

    def execute_summary_review_action(
        self,
        *,
        user,
        raw_message_id,
        action: str | None,
        structured_payload: dict | None = None,
    ) -> Optional[CandidateSummaryReviewResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_SUMMARY_REVIEW:
            return None

        payload = dict(structured_payload or {})
        if action is None and not payload:
            return CandidateSummaryReviewResult(
                status="empty",
                notification_template="candidate_summary_review_help",
            )

        if action == "approve_summary":
            current_version = self.repo.get_current_version(profile)
            if current_version is None:
                return CandidateSummaryReviewResult(
                    status="missing",
                    notification_template="candidate_summary_not_available",
                )

            self.repo.mark_version_approved(current_version)
            questions_context = self._ensure_questions_context(profile)
            questions_context["current_question_key"] = self._next_missing_question_key(profile)
            self.repo.update_questions_context(profile, questions_context)
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_QUESTIONS_PENDING,
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=user.id,
                metadata_json={"action": "approve_summary"},
            )
            return CandidateSummaryReviewResult(
                status="approved",
                notification_template="candidate_summary_approved",
            )

        correction_count = self.repo.count_versions_by_source_type(profile.id, "summary_user_edit")
        if correction_count >= 1:
            return CandidateSummaryReviewResult(
                status="limit_reached",
                notification_template="candidate_summary_edit_limit_reached",
            )

        if payload.get("needs_edit_details"):
            return CandidateSummaryReviewResult(
                status="awaiting_edit_details",
                notification_template="candidate_summary_edit_empty",
            )

        edit_text = (payload.get("edit_text") or "").strip()
        if not edit_text:
            return CandidateSummaryReviewResult(
                status="empty_edit",
                notification_template="candidate_summary_edit_empty",
            )

        current_version = self.repo.get_current_version(profile)
        if current_version is None:
            return CandidateSummaryReviewResult(
                status="missing",
                notification_template="candidate_summary_not_available",
            )

        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state=CANDIDATE_STATE_CV_PROCESSING,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
            metadata_json={"action": "edit_summary"},
        )
        new_version = self.repo.create_version(
            profile_id=profile.id,
            version_no=self.repo.next_version_no(profile.id),
            source_type="summary_user_edit",
            source_raw_message_id=raw_message_id,
            summary_json={
                "edit_request_text": edit_text,
                "base_version_id": str(current_version.id),
            },
            normalization_json={"edit_request_text": edit_text},
        )
        self.repo.set_current_version(profile, new_version.id)
        self.queue.enqueue(
            JobMessage(
                job_type="candidate_summary_edit_apply_v1",
                payload={
                    "candidate_profile_id": str(profile.id),
                    "candidate_profile_version_id": str(new_version.id),
                    "base_version_id": str(current_version.id),
                    "edit_request_text": edit_text,
                },
                idempotency_key=f"candidate_summary_edit_apply_v1:{new_version.id}",
                entity_type="candidate_profile_version",
                entity_id=new_version.id,
            )
        )
        return CandidateSummaryReviewResult(
            status="accepted",
            notification_template="candidate_summary_edit_processing",
        )

    def handle_questions_answer(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        text: Optional[str] = None,
        file_id=None,
    ) -> Optional[CandidateQuestionsResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_QUESTIONS_PENDING:
            return None

        if content_type == "text":
            return self._apply_question_answer_text(
                profile=profile,
                raw_message_id=raw_message_id,
                text=text,
                actor_user_id=user.id,
                trigger_type="user_action",
            )

        if content_type in {"voice", "video"}:
            self.queue.enqueue(
                JobMessage(
                    job_type="candidate_questions_parse_v1",
                    payload={
                        "candidate_profile_id": str(profile.id),
                        "raw_message_id": str(raw_message_id),
                        "file_id": str(file_id) if file_id is not None else None,
                        "content_type": content_type,
                    },
                    idempotency_key=f"candidate_questions_parse_v1:{raw_message_id}",
                    entity_type="candidate_profile",
                    entity_id=profile.id,
                )
            )
            return CandidateQuestionsResult(
                status="queued",
                notification_template="candidate_questions_processing",
                notification_text="Got it. I’m processing those profile details now.",
            )

        return CandidateQuestionsResult(
            status="unsupported",
            notification_template="candidate_questions_unsupported",
            notification_text="Reply in text, voice, or video and I’ll parse it.",
        )

    def process_question_answer_text(
        self,
        *,
        profile,
        raw_message_id,
        text: Optional[str],
        actor_user_id=None,
        trigger_type: str,
    ) -> CandidateQuestionsResult:
        return self._apply_question_answer_text(
            profile=profile,
            raw_message_id=raw_message_id,
            text=text,
            actor_user_id=actor_user_id,
            trigger_type=trigger_type,
        )

    def handle_questions_parsed_payload(
        self,
        *,
        user,
        raw_message_id,
        parsed_payload: dict,
    ) -> Optional[CandidateQuestionsResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_QUESTIONS_PENDING:
            return None
        return self._apply_question_payload(
            profile=profile,
            raw_message_id=raw_message_id,
            parsed=dict(parsed_payload or {}),
            actor_user_id=user.id,
            trigger_type="user_action",
        )

    def _apply_question_answer_text(
        self,
        *,
        profile,
        raw_message_id,
        text: Optional[str],
        actor_user_id=None,
        trigger_type: str,
    ) -> CandidateQuestionsResult:
        normalized_text = (text or "").strip()
        if not normalized_text:
            return CandidateQuestionsResult(
                status="empty",
                notification_template="candidate_questions_help",
                notification_text=initial_questions_prompt(),
            )

        llm_result = safe_parse_candidate_questions(self.session, normalized_text)
        parsed = dict(llm_result.payload or {})
        current_question_key = current_candidate_question_key(profile)
        parsed = enrich_candidate_question_payload_for_current_question(
            parsed=parsed,
            text=normalized_text,
            current_question_key=current_question_key,
        )
        return self._apply_question_payload(
            profile=profile,
            raw_message_id=raw_message_id,
            parsed=parsed,
            actor_user_id=actor_user_id,
            trigger_type=trigger_type,
        )

    def _apply_question_payload(
        self,
        *,
        profile,
        raw_message_id,
        parsed: dict,
        actor_user_id=None,
        trigger_type: str,
    ) -> CandidateQuestionsResult:
        missing_before = self._missing_question_keys(profile)
        questions_context = self._ensure_questions_context(profile)
        current_question_key = questions_context.get("current_question_key")
        if current_question_key not in QUESTION_KEYS:
            current_question_key = current_candidate_question_key(profile)

        parsed = self._filter_question_payload(parsed, current_question_key)
        if parsed:
            self.repo.update_question_answers(profile, **parsed)

        missing_keys = self._missing_question_keys(profile)
        if not missing_keys:
            self.state_service.transition(
                entity_type="candidate_profile",
                entity=profile,
                to_state=CANDIDATE_STATE_VERIFICATION_PENDING,
                trigger_type=trigger_type,
                trigger_ref_id=raw_message_id,
                actor_user_id=actor_user_id,
                metadata_json={"action": "mandatory_questions_completed"},
            )
            verification = self._issue_verification(profile)
            return CandidateQuestionsResult(
                status="completed",
                notification_template="candidate_questions_completed",
                notification_text=(
                    "Great, I have the matching basics. "
                    f"Next, send a short video and say: '{verification.phrase_text}'."
                ),
            )

        next_question_key = missing_keys[0]
        questions_context["current_question_key"] = next_question_key
        self.repo.update_questions_context(profile, questions_context)

        if current_question_key is not None and current_question_key in missing_before and current_question_key not in missing_keys:
            return CandidateQuestionsResult(
                status="next_question",
                notification_template="candidate_questions_follow_up",
                notification_text=question_prompt(next_question_key, work_formats=candidate_work_formats(profile)),
            )

        if parsed:
            return CandidateQuestionsResult(
                status="follow_up",
                notification_template="candidate_questions_follow_up",
                notification_text=follow_up_prompt(current_question_key, work_formats=candidate_work_formats(profile)),
            )

        return CandidateQuestionsResult(
            status="incomplete",
            notification_template="candidate_questions_missing",
            notification_text=question_prompt(next_question_key, work_formats=candidate_work_formats(profile)),
        )

    def _filter_question_payload(self, parsed: dict, current_question_key: str | None) -> dict:
        return filter_candidate_question_payload(parsed, current_question_key)

    def _missing_question_keys(self, profile) -> list[str]:
        return missing_candidate_question_keys(profile)

    def _ensure_questions_context(self, profile) -> dict:
        current = dict(profile.questions_context_json or {})
        follow_up_used = dict(current.get("follow_up_used") or {})
        for key in QUESTION_KEYS:
            follow_up_used.setdefault(key, False)
        current["follow_up_used"] = follow_up_used
        return current

    def _next_follow_up_key(self, questions_context: dict, missing_keys: list[str]) -> Optional[str]:
        follow_up_used = questions_context.get("follow_up_used") or {}
        for key in missing_keys:
            if not follow_up_used.get(key, False):
                return key
        return None

    def _next_missing_question_key(self, profile) -> Optional[str]:
        return current_candidate_question_key(profile)

    def execute_deletion_action(
        self,
        *,
        user,
        raw_message_id,
        action: str | None,
    ) -> Optional[CandidateDeletionResult]:
        profile = self.repo.get_active_by_user_id(user.id)
        if profile is None:
            return None

        deletion_context = self._ensure_deletion_context(profile)
        pending = bool((deletion_context.get("deletion") or {}).get("pending"))

        if action == "cancel_delete" and pending:
            deletion_context["deletion"]["pending"] = False
            self._update_deletion_context(profile, deletion_context)
            return CandidateDeletionResult(
                status="cancelled",
                notification_template="candidate_deletion_cancelled",
                notification_text=self._copy("Okay, profile stays active."),
            )

        active_matches = self.matching.list_active_for_candidate(profile.id)
        has_active_interview = any(
            self.interviews.get_active_by_match_id(match.id) is not None for match in active_matches
        )

        if action == "confirm_delete" and pending:
            return self._execute_deletion(
                profile=profile,
                raw_message_id=raw_message_id,
                actor_user_id=user.id,
                active_matches=active_matches,
            )

        if action == "delete_profile":
            deletion_context["deletion"]["pending"] = True
            self._update_deletion_context(profile, deletion_context)
            confirmation = safe_build_deletion_confirmation(
                self.session,
                entity_type="candidate_profile",
                has_active_interview=has_active_interview,
                has_active_matches=bool(active_matches),
            )
            return CandidateDeletionResult(
                status="confirmation_required",
                notification_template="candidate_deletion_confirmation_required",
                notification_text=confirmation.payload["message"],
            )
        return None

    def execute_ready_action(
        self,
        *,
        user,
        raw_message_id,
        action: str | None,
        structured_payload: dict | None = None,
    ) -> Optional[CandidateReadyActionResult]:
        profile = self.repo.get_active_by_user_id(user.id)
        if profile is None:
            return None

        if action == "record_matching_feedback":
            feedback_text = self._normalize_matching_feedback_text((structured_payload or {}).get("feedback_text"))
            if not feedback_text:
                return CandidateReadyActionResult(
                    status="matching_feedback_missing",
                    notification_template="candidate_ready",
                    notification_text=self._copy(
                        "Tell me what feels off in these roles and I’ll save that feedback for matching."
                    ),
                )
            categories = self._categorize_matching_feedback(feedback_text)
            self._store_matching_feedback(
                profile,
                feedback_text=feedback_text,
                categories=categories,
                source_stage=(structured_payload or {}).get("source_stage") or "READY",
            )
            return CandidateReadyActionResult(
                status="matching_feedback_recorded",
                notification_template="candidate_ready",
                notification_text=self._copy(self._matching_feedback_acknowledgement(categories)),
            )

        if action == "update_matching_preferences":
            parsed = dict(structured_payload or {})
            if not parsed:
                return CandidateReadyActionResult(
                    status="preferences_update_missing",
                    notification_template="candidate_ready",
                    notification_text=self._copy(
                        "Tell me exactly what you want to change in salary, format, location, English, domains, or assessment preferences."
                    ),
                )
            self.repo.update_question_answers(profile, **parsed)
            updated_labels = self._describe_ready_updates(parsed)
            missing_keys = self._missing_question_keys(profile)
            if missing_keys:
                next_key = missing_keys[0]
                questions_context = self._ensure_questions_context(profile)
                questions_context["current_question_key"] = next_key
                self.repo.update_questions_context(profile, questions_context)
                lead = (
                    f"I updated your {', '.join(updated_labels)}."
                    if updated_labels
                    else "I updated your matching preferences."
                )
                return CandidateReadyActionResult(
                    status="preferences_updated_needs_follow_up",
                    notification_template="candidate_ready",
                    notification_text=self._copy(
                        f"{lead} To use this cleanly in matching, I still need one more thing: "
                        f"{question_prompt(next_key, work_formats=candidate_work_formats(profile))}"
                    ),
                )
            open_vacancies = self.vacancies.get_open_vacancies()
            if not open_vacancies:
                return CandidateReadyActionResult(
                    status="preferences_updated_no_open_vacancies",
                    notification_template="candidate_ready",
                    notification_text=self._copy(
                        (
                            f"I updated your {', '.join(updated_labels)}."
                            if updated_labels
                            else "I updated your matching preferences."
                        )
                        + " There are no open roles right now, but I’ll use these settings as soon as new ones appear."
                    ),
                )
            self._enqueue_ready_matching(profile=profile, raw_message_id=raw_message_id)
            return CandidateReadyActionResult(
                status="preferences_updated_matching_requested",
                notification_template="candidate_ready",
                notification_text=self._copy(
                    (
                        f"I updated your {', '.join(updated_labels)}."
                        if updated_labels
                        else "I updated your matching preferences."
                    )
                    + " I’m rechecking open roles for your profile now."
                ),
            )

        if action != "find_matching_vacancies":
            return None

        open_vacancies = self.vacancies.get_open_vacancies()
        if not open_vacancies:
            challenge_payload = self.cv_challenge.build_invitation_payload(user.id)
            return CandidateReadyActionResult(
                status="no_open_vacancies",
                notification_template="candidate_ready",
                notification_text=self._copy(
                    "I checked current open roles. Nothing is open right now, but I’ll keep watching and message you when a strong match appears."
                    + (
                        " While you wait, you can also open Helly CV Challenge and play a quick round."
                        if challenge_payload is not None
                        else ""
                    )
                ),
                reply_markup=(
                    candidate_cv_challenge_keyboard(challenge_payload["launchUrl"])
                    if challenge_payload is not None
                    else None
                ),
            )

        self._enqueue_ready_matching(profile=profile, raw_message_id=raw_message_id)

        return CandidateReadyActionResult(
            status="matching_requested",
            notification_template="candidate_ready",
            notification_text=self._copy("Got it. I’m checking current open roles for your profile now."),
        )

    def _enqueue_ready_matching(self, *, profile, raw_message_id) -> None:
        for vacancy in self.vacancies.get_open_vacancies():
            self.queue.enqueue(
                JobMessage(
                    job_type="matching_run_for_vacancy_v1",
                    payload={
                        "vacancy_id": str(vacancy.id),
                        "trigger_type": "candidate_manual_request",
                        "trigger_candidate_profile_id": str(profile.id),
                        "candidate_manual_request_id": str(raw_message_id),
                    },
                    idempotency_key=f"matching_run_for_vacancy_v1:{vacancy.id}:candidate:{profile.id}:manual:{raw_message_id}",
                    entity_type="vacancy",
                    entity_id=vacancy.id,
                )
            )

    def _describe_ready_updates(self, parsed: dict) -> list[str]:
        labels = []
        if any(key in parsed for key in {"salary_min", "salary_max", "salary_currency", "salary_period"}):
            labels.append("salary preferences")
        if any(key in parsed for key in {"work_format", "work_formats_json"}):
            labels.append("work format")
        if any(key in parsed for key in {"location_text", "country_code", "city"}):
            labels.append("location")
        if "english_level" in parsed:
            labels.append("English preference")
        if "preferred_domains_json" in parsed:
            labels.append("domain preferences")
        if any(key in parsed for key in {"show_take_home_task_roles", "show_live_coding_roles"}):
            labels.append("assessment preferences")
        return labels

    @staticmethod
    def _normalize_matching_feedback_text(value: str | None) -> str | None:
        if not value:
            return None
        text = " ".join(str(value).split()).strip()
        return text or None

    @classmethod
    def _categorize_matching_feedback(cls, text: str) -> list[str]:
        lowered = text.lower()
        categories: list[str] = []
        category_markers = {
            "compensation": ["salary", "money", "pay", "budget", "compensation", "дорого", "дешево", "мало", "маловато", "зарплат", "денег", "low paid", "too low"],
            "location": ["remote", "hybrid", "office", "onsite", "relocate", "location", "city", "country", "remote only", "офис", "гибрид", "гібрид", "локац", "город", "місто", "країн"],
            "english": ["english", "b2", "c1", "c2", "англий", "англій", "english level"],
            "domain": ["domain", "fintech", "saas", "ecommerce", "healthtech", "gaming", "ai", "не мой домен", "домен"],
            "process": ["take-home", "take home", "test task", "live coding", "interview stages", "too many stages", "процесс", "процес", "тестов", "лайвкод", "етап", "этап"],
            "stack": ["stack", "technology", "technologies", "tech", "tooling", "language", "framework", "react", "node", "python", "java", "стек", "технолог", "фреймворк"],
            "role": ["seniority", "junior", "middle", "senior", "staff", "lead", "role", "позици", "роль", "сеньор", "мидл", "джун"],
        }
        for category, markers in category_markers.items():
            if any(marker in lowered for marker in markers):
                categories.append(category)
        return categories

    def _store_matching_feedback(self, profile, *, feedback_text: str, categories: list[str], source_stage: str) -> None:
        current = dict(profile.questions_context_json or {})
        matching_feedback = dict(current.get("matching_feedback") or {})
        events = list(matching_feedback.get("candidate_feedback_events") or [])
        events.append(
            {
                "text": feedback_text,
                "categories": categories,
                "source_stage": source_stage,
            }
        )
        matching_feedback["candidate_feedback_events"] = events[-6:]
        current["matching_feedback"] = matching_feedback
        self.repo.update_questions_context(profile, current)

    @staticmethod
    def _matching_feedback_acknowledgement(categories: list[str]) -> str:
        label_map = {
            "compensation": "compensation",
            "location": "location",
            "english": "English",
            "domain": "domain",
            "process": "hiring process",
            "stack": "stack",
            "role": "role level",
        }
        labels = [label_map[key] for key in categories if key in label_map]
        if labels:
            if len(labels) == 1:
                summary = labels[0]
            elif len(labels) == 2:
                summary = f"{labels[0]} and {labels[1]}"
            else:
                summary = f"{', '.join(labels[:-1])}, and {labels[-1]}"
            return (
                f"Got it. I saved that these roles keep missing on {summary}. "
                "If you want, I can also turn that into a concrete preference update right here."
            )
        return (
            "Got it. I saved that feedback for future matching. "
            "If you want, I can also turn it into a concrete preference update right here."
        )

    def _ensure_deletion_context(self, profile) -> dict:
        current = dict(profile.questions_context_json or {})
        deletion = dict(current.get("deletion") or {})
        deletion.setdefault("pending", False)
        current["deletion"] = deletion
        return current

    def _update_deletion_context(self, profile, context: dict) -> None:
        self.repo.update_questions_context(profile, context)

    def _execute_deletion(self, *, profile, raw_message_id, actor_user_id, active_matches) -> CandidateDeletionResult:
        deletion_context = self._ensure_deletion_context(profile)
        deletion_context["deletion"]["pending"] = False
        self._update_deletion_context(profile, deletion_context)

        cancelled_matches = 0
        cancelled_interviews = 0
        for match in active_matches:
            session = self.interviews.get_active_by_match_id(match.id)
            if session is not None:
                self.state_service.transition(
                    entity_type="interview_session",
                    entity=session,
                    to_state="CANCELLED",
                    trigger_type="user_action",
                    trigger_ref_id=raw_message_id,
                    actor_user_id=actor_user_id,
                    metadata_json={"reason": "candidate_deleted"},
                )
                cancelled_interviews += 1
            self.state_service.transition(
                entity_type="match",
                entity=match,
                to_state="cancelled",
                trigger_type="user_action",
                trigger_ref_id=raw_message_id,
                actor_user_id=actor_user_id,
                metadata_json={"reason": "candidate_deleted"},
                state_field="status",
            )
            cancelled_matches += 1

        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state="DELETED",
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=actor_user_id,
            metadata_json={
                "cancelled_matches": cancelled_matches,
                "cancelled_interviews": cancelled_interviews,
            },
        )
        self.repo.soft_delete(profile)
        self.queue.enqueue(
            JobMessage(
                job_type="cleanup_candidate_deletion_v1",
                payload={"candidate_profile_id": str(profile.id)},
                idempotency_key=f"cleanup_candidate_deletion_v1:{profile.id}",
                entity_type="candidate_profile",
                entity_id=profile.id,
            )
        )
        details = []
        if cancelled_matches:
            details.append(f"{cancelled_matches} active match(es)")
        if cancelled_interviews:
            details.append(f"{cancelled_interviews} interview(s)")
        details_text = ""
        if details:
            details_text = " Cancelled: " + ", ".join(details) + "."
        return CandidateDeletionResult(
            status="deleted",
            notification_template="candidate_deleted",
            notification_text=self._copy(f"Done. Your profile is deleted and out of the active flow.{details_text}"),
        )

    def handle_verification_submission(
        self,
        *,
        user,
        raw_message_id,
        content_type: str,
        file_id=None,
    ) -> Optional[CandidateVerificationResult]:
        profile = self.ensure_profile_for_user(user)
        if profile.state != CANDIDATE_STATE_VERIFICATION_PENDING:
            return None

        verification = self.verifications.get_pending_by_profile_id(profile.id)
        if verification is None:
            verification = self._issue_verification(profile)

        if content_type != "video" or file_id is None:
            if content_type == "voice":
                instruction = (
                    "Need a short selfie video here, not a voice note 🙂 "
                    f"Record a quick video in Telegram and clearly say: '{verification.phrase_text}'."
                )
            else:
                instruction = (
                    "Need a short selfie video here, not text 🙂 "
                    f"Record a quick video in Telegram and clearly say: '{verification.phrase_text}'."
                )
            return CandidateVerificationResult(
                status="instruction",
                notification_template="candidate_verification_instructions",
                notification_text=instruction,
            )

        file_row = self.files.get_by_id(file_id)
        if file_row is None:
            return CandidateVerificationResult(
                status="instruction",
                notification_template="candidate_verification_instructions",
                notification_text=(
                    "I couldn't read that upload yet. "
                    f"Please send a short selfie video and clearly say: '{verification.phrase_text}'."
                ),
            )

        try:
            ingestion = ContentIngestionService(self.session)
            transcript_result = ingestion.ingest_file(file_row, prompt_text=verification.phrase_text)
            spoken_text = transcript_result.text
        except ContentQualityError as exc:
            spoken_text = str((exc.metadata or {}).get("transcript_text") or "").strip()
            verification.review_notes_json = {
                "transcript_text": spoken_text,
                "phrase_matched": False,
                "quality_error_code": exc.code,
                "raw_message_id": str(raw_message_id) if raw_message_id is not None else None,
                "video_file_id": str(file_id) if file_id is not None else None,
            }
            self.session.flush()
            phrase_feedback = format_verification_phrase_feedback(
                expected_phrase=verification.phrase_text,
                spoken_text=spoken_text,
            )
            return CandidateVerificationResult(
                status="retry_required",
                notification_template="candidate_verification_instructions",
                notification_text=(
                    "I couldn't verify the phrase from that video because the audio was too noisy. "
                    f"{phrase_feedback} "
                    "Please resend a clearer selfie video and say it in one take."
                ),
            )
        except Exception:
            verification.review_notes_json = {
                "transcript_text": None,
                "phrase_matched": False,
                "processing_error_code": "verification_transcription_failed",
                "raw_message_id": str(raw_message_id) if raw_message_id is not None else None,
                "video_file_id": str(file_id) if file_id is not None else None,
            }
            self.session.flush()
            return CandidateVerificationResult(
                status="retry_required",
                notification_template="candidate_verification_instructions",
                notification_text=(
                    "I couldn't transcribe that video well enough to compare the phrase. "
                    f'You were supposed to say: "{verification.phrase_text}". '
                    "Please resend a short selfie video and say it clearly in one take."
                ),
            )

        verification.review_notes_json = {
            "transcript_text": spoken_text,
            "phrase_matched": phrase_matches_verification(
                expected_phrase=verification.phrase_text,
                spoken_text=spoken_text,
            ),
            "raw_message_id": str(raw_message_id) if raw_message_id is not None else None,
            "video_file_id": str(file_id) if file_id is not None else None,
        }
        self.session.flush()

        if not verification.review_notes_json["phrase_matched"]:
            phrase_feedback = format_verification_phrase_feedback(
                expected_phrase=verification.phrase_text,
                spoken_text=spoken_text,
            )
            return CandidateVerificationResult(
                status="phrase_mismatch",
                notification_template="candidate_verification_instructions",
                notification_text=(
                    f"{phrase_feedback} "
                    "Please record one more short selfie video and say it exactly in one take."
                ),
            )

        self.verifications.mark_submitted(verification, video_file_id=file_id)
        self.state_service.transition(
            entity_type="candidate_profile",
            entity=profile,
            to_state=CANDIDATE_STATE_READY,
            trigger_type="user_action",
            trigger_ref_id=raw_message_id,
            actor_user_id=user.id,
            metadata_json={
                "action": "verification_submitted",
                "candidate_verification_id": str(verification.id),
            },
        )
        self.repo.mark_ready(profile)
        self.queue.enqueue(
            JobMessage(
                job_type="matching_candidate_ready_v1",
                payload={
                    "candidate_profile_id": str(profile.id),
                },
                idempotency_key=f"matching_candidate_ready_v1:{profile.id}",
                entity_type="candidate_profile",
                entity_id=profile.id,
            )
        )
        return CandidateVerificationResult(
            status="completed",
            notification_template="candidate_ready",
            notification_text="Nice, verification is in. Your profile is now ready for matching.",
        )

    def _issue_verification(self, profile):
        existing = self.verifications.get_pending_by_profile_id(profile.id)
        if existing is not None:
            return existing

        attempt_no = self.verifications.next_attempt_no(profile.id)
        phrase_text = build_verification_phrase(
            profile_id=profile.id,
            attempt_no=attempt_no,
        )
        return self.verifications.create(
            profile_id=profile.id,
            attempt_no=attempt_no,
            phrase_text=phrase_text,
        )
