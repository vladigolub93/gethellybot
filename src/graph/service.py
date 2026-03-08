from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config.logging import get_logger
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.interviews import InterviewsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.raw_messages import RawMessagesRepository
from src.db.repositories.vacancies import VacanciesRepository
from src.graph.bootstrap import register_foundation_stage_graphs
from src.identity.rules import has_primary_contact_channel
from src.graph.registry import registry
from src.graph.router import StageGraphRouter
from src.graph.runtime import compile_stage_graph
from src.graph.stages.candidate import (
    build_candidate_stage_reply_node,
    build_candidate_stage_detect_node,
    detect_candidate_stage_intent_node,
    load_candidate_stage_context_node,
    load_candidate_stage_knowledge_node,
)
from src.graph.stages.entry import (
    build_entry_reply_node,
    build_entry_detect_node,
    load_entry_context_node,
    load_entry_knowledge_node,
)
from src.graph.stages.deletion import (
    build_delete_stage_reply_node,
    detect_delete_stage_intent_node,
    load_delete_stage_context_node,
    load_delete_stage_knowledge_node,
)
from src.graph.stages.manager import (
    build_manager_stage_detect_node,
    build_manager_stage_reply_node,
    detect_manager_stage_intent_node,
    load_manager_stage_context_node,
    load_manager_stage_knowledge_node,
)
from src.orchestrator.policy import resolve_state_context


logger = get_logger(__name__)


@dataclass(frozen=True)
class StageAgentExecutionResult:
    stage: str
    reply_text: str | None
    stage_status: str | None
    proposed_action: str | None
    action_accepted: bool
    structured_payload: dict[str, Any] = field(default_factory=dict)
    validation_result: dict[str, Any] = field(default_factory=dict)


class LangGraphStageAgentService:
    ENTRY_STAGES = {"CONTACT_REQUIRED", "ROLE_SELECTION"}
    SHARED_STAGES = {"DELETE_CONFIRMATION"}
    CANDIDATE_STAGES = {
        "CV_PENDING",
        "SUMMARY_REVIEW",
        "QUESTIONS_PENDING",
        "VERIFICATION_PENDING",
        "READY",
        "INTERVIEW_INVITED",
        "INTERVIEW_IN_PROGRESS",
    }
    MANAGER_STAGES = {
        "INTAKE_PENDING",
        "VACANCY_SUMMARY_REVIEW",
        "CLARIFICATION_QA",
        "OPEN",
        "MANAGER_REVIEW",
    }

    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.interviews = InterviewsRepository(session)
        self.matches = MatchingRepository(session)
        self.raw_messages = RawMessagesRepository(session)
        self.vacancies = VacanciesRepository(session)
        self.router = StageGraphRouter()
        register_foundation_stage_graphs()
        self._compiled_graphs = {}
        self._register_entry_stage_nodes()
        self._register_shared_stage_nodes()
        self._register_candidate_stage_nodes()
        self._register_manager_stage_nodes()

    def maybe_build_entry_reply(
        self,
        *,
        user,
        latest_user_message: str,
        latest_message_type: str = "text",
    ) -> str | None:
        result = self.maybe_run_entry_stage(
            user=user,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
        )
        return result.reply_text if result is not None else None

    def maybe_run_entry_stage(
        self,
        *,
        user,
        latest_user_message: str,
        latest_message_type: str = "text",
    ) -> StageAgentExecutionResult | None:
        if latest_message_type != "text" or not latest_user_message.strip():
            return None
        stage = self._resolve_entry_stage(user)
        if stage not in self.ENTRY_STAGES:
            return None
        result = self._run_stage_graph(
            user=user,
            stage=stage,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
        )
        execution_result = StageAgentExecutionResult(
            stage=stage,
            reply_text=result.get("reply_text"),
            stage_status=result.get("stage_status"),
            proposed_action=result.get("proposed_action"),
            action_accepted=bool(result.get("validation_result", {}).get("accepted")),
            structured_payload=result.get("structured_payload") or {},
            validation_result=result.get("validation_result") or {},
        )
        self._log_stage_execution(
            user=user,
            latest_message_type=latest_message_type,
            execution_result=execution_result,
        )
        return execution_result

    def resolve_current_stage_context(self, *, user):
        stage = self._resolve_supported_stage(user)
        role = self._resolve_role(user)
        return resolve_state_context(role=role, state=stage)

    def maybe_build_stage_reply(
        self,
        *,
        user,
        latest_user_message: str,
        latest_message_type: str = "text",
    ) -> str | None:
        result = self.maybe_run_stage(
            user=user,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
        )
        if result is None or result.action_accepted:
            return None
        return result.reply_text

    def maybe_run_stage(
        self,
        *,
        user,
        latest_user_message: str,
        latest_message_type: str = "text",
    ) -> StageAgentExecutionResult | None:
        if latest_message_type == "text" and not latest_user_message.strip():
            return None
        if latest_message_type != "text":
            stage = self._resolve_supported_stage(user)
            if stage != "VERIFICATION_PENDING" or latest_message_type != "video":
                return None
        if latest_message_type == "text":
            stage = self._resolve_supported_stage(user)
        else:
            stage = self._resolve_supported_stage(user)
        if stage is None:
            return None
        result = self._run_stage_graph(
            user=user,
            stage=stage,
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
        )
        execution_result = StageAgentExecutionResult(
            stage=stage,
            reply_text=result.get("reply_text"),
            stage_status=result.get("stage_status"),
            proposed_action=result.get("proposed_action"),
            action_accepted=bool(result.get("validation_result", {}).get("accepted")),
            structured_payload=result.get("structured_payload") or {},
            validation_result=result.get("validation_result") or {},
        )
        self._log_stage_execution(
            user=user,
            latest_message_type=latest_message_type,
            execution_result=execution_result,
        )
        return execution_result

    def _resolve_role(self, user) -> str | None:
        if getattr(user, "is_candidate", False):
            return "candidate"
        if getattr(user, "is_hiring_manager", False):
            return "hiring_manager"
        return None

    def _resolve_entry_stage(self, user) -> str | None:
        if not has_primary_contact_channel(user):
            return "CONTACT_REQUIRED"
        if not getattr(user, "is_candidate", False) and not getattr(user, "is_hiring_manager", False):
            return "ROLE_SELECTION"
        return None

    def _resolve_candidate_stage(self, user) -> str | None:
        if not getattr(user, "is_candidate", False):
            return None
        candidate = self.candidates.get_active_by_user_id(user.id)
        if candidate is None:
            return None
        if self._has_pending_deletion(candidate):
            return "DELETE_CONFIRMATION"
        active_session = self.interviews.get_active_session_for_candidate(candidate.id)
        if active_session is not None:
            return "INTERVIEW_IN_PROGRESS"
        invited_match = self.matches.get_latest_invited_for_candidate(candidate.id)
        if invited_match is not None:
            return "INTERVIEW_INVITED"
        if candidate.state in self.CANDIDATE_STAGES:
            return candidate.state
        return None

    def _resolve_supported_stage(self, user) -> str | None:
        return self._resolve_entry_stage(user) or self._resolve_candidate_stage(user) or self._resolve_manager_stage(user)

    def _log_stage_execution(
        self,
        *,
        user,
        latest_message_type: str,
        execution_result: StageAgentExecutionResult,
    ) -> None:
        logger.info(
            "graph_stage_executed",
            user_id=str(getattr(user, "id", "")),
            telegram_user_id=getattr(user, "telegram_user_id", None),
            stage=execution_result.stage,
            stage_status=execution_result.stage_status,
            proposed_action=execution_result.proposed_action,
            action_accepted=execution_result.action_accepted,
            latest_message_type=latest_message_type,
        )

    def _resolve_manager_stage(self, user) -> str | None:
        if not getattr(user, "is_hiring_manager", False):
            return None
        manager_vacancies = self.vacancies.get_by_manager_user_id(user.id)
        latest_active_vacancy = self.vacancies.get_latest_active_by_manager_user_id(user.id)
        if latest_active_vacancy is not None and self._has_pending_deletion(latest_active_vacancy):
            return "DELETE_CONFIRMATION"
        manager_review_match = self.matches.get_latest_manager_review_for_manager(
            [vacancy.id for vacancy in manager_vacancies]
        )
        if manager_review_match is not None:
            return "MANAGER_REVIEW"
        vacancy = latest_active_vacancy
        if vacancy is None:
            return None
        if vacancy.state in self.MANAGER_STAGES:
            return vacancy.state
        return None

    def _register_entry_stage_nodes(self) -> None:
        for stage in self.ENTRY_STAGES:
            definition = registry.get_definition(stage)
            if definition is None:
                continue
            registry.register_stage(
                definition=definition,
                nodes={
                    "load_context": load_entry_context_node,
                    "load_knowledge": load_entry_knowledge_node,
                    "detect_intent": build_entry_detect_node(self.session),
                    "propose_action": build_entry_reply_node(self.session),
                    "validate_action": registry.get_nodes(stage).get("validate_action")
                    or (lambda state: state),
                    "emit_side_effects": registry.get_nodes(stage).get("emit_side_effects")
                    or (lambda state: state),
                },
            )

    def _register_shared_stage_nodes(self) -> None:
        for stage in self.SHARED_STAGES:
            definition = registry.get_definition(stage)
            if definition is None:
                continue
            registry.register_stage(
                definition=definition,
                nodes={
                    "load_context": load_delete_stage_context_node,
                    "load_knowledge": load_delete_stage_knowledge_node,
                    "detect_intent": detect_delete_stage_intent_node,
                    "propose_action": build_delete_stage_reply_node(self.session),
                    "validate_action": registry.get_nodes(stage).get("validate_action")
                    or (lambda state: state),
                    "emit_side_effects": registry.get_nodes(stage).get("emit_side_effects")
                    or (lambda state: state),
                },
            )

    def _register_candidate_stage_nodes(self) -> None:
        for stage in self.CANDIDATE_STAGES:
            definition = registry.get_definition(stage)
            if definition is None:
                continue
            registry.register_stage(
                definition=definition,
                nodes={
                    "load_context": load_candidate_stage_context_node,
                    "load_knowledge": load_candidate_stage_knowledge_node,
                    "detect_intent": build_candidate_stage_detect_node(self.session),
                    "propose_action": build_candidate_stage_reply_node(self.session),
                    "validate_action": registry.get_nodes(stage).get("validate_action")
                    or (lambda state: state),
                    "emit_side_effects": registry.get_nodes(stage).get("emit_side_effects")
                    or (lambda state: state),
                },
            )

    def _register_manager_stage_nodes(self) -> None:
        for stage in self.MANAGER_STAGES:
            definition = registry.get_definition(stage)
            if definition is None:
                continue
            registry.register_stage(
                definition=definition,
                nodes={
                    "load_context": load_manager_stage_context_node,
                    "load_knowledge": load_manager_stage_knowledge_node,
                    "detect_intent": build_manager_stage_detect_node(self.session),
                    "propose_action": build_manager_stage_reply_node(self.session),
                    "validate_action": registry.get_nodes(stage).get("validate_action")
                    or (lambda state: state),
                    "emit_side_effects": registry.get_nodes(stage).get("emit_side_effects")
                    or (lambda state: state),
                },
            )

    def _get_compiled_graph(self, stage: str):
        compiled = self._compiled_graphs.get(stage)
        if compiled is not None:
            return compiled
        definition = registry.get_definition(stage)
        if definition is None:
            raise ValueError(f"Stage graph is not registered: {stage}")
        compiled = compile_stage_graph(
            definition=definition,
            nodes=registry.get_nodes(stage),
        )
        self._compiled_graphs[stage] = compiled
        return compiled

    def _run_stage_graph(
        self,
        *,
        user,
        stage: str,
        latest_user_message: str,
        latest_message_type: str,
    ) -> dict[str, Any]:
        compiled = self._get_compiled_graph(stage)
        context = resolve_state_context(role=self._resolve_role(user), state=stage)
        state_input = self.router.build_initial_state(
            stage=stage,
            user_id=str(getattr(user, "id", "")) or None,
            telegram_chat_id=str(getattr(user, "telegram_chat_id", "")) or None,
            role=self._resolve_role(user),
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
            allowed_actions=context.allowed_actions,
            missing_requirements=context.missing_requirements,
            recent_context=self._load_recent_turn_context(user),
        )
        return compiled.invoke(state_input.as_dict())

    @staticmethod
    def _has_pending_deletion(entity) -> bool:
        context = getattr(entity, "questions_context_json", {}) or {}
        deletion = context.get("deletion") or {}
        return bool(deletion.get("pending"))

    def _load_recent_turn_context(self, user) -> list[str]:
        user_id = getattr(user, "id", None)
        if user_id is None:
            return []
        try:
            return self.raw_messages.list_recent_text_context(user_id=user_id, limit=6)
        except Exception:
            return []
