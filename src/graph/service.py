from __future__ import annotations

from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.consents import UserConsentsRepository
from src.graph.bootstrap import register_foundation_stage_graphs
from src.graph.registry import registry
from src.graph.router import StageGraphRouter
from src.graph.runtime import compile_stage_graph
from src.graph.stages.candidate import (
    build_candidate_cv_reply_node,
    detect_candidate_cv_intent_node,
    load_candidate_cv_context_node,
    load_candidate_cv_knowledge_node,
)
from src.graph.stages.entry import (
    build_entry_reply_node,
    detect_entry_intent_node,
    load_entry_context_node,
    load_entry_knowledge_node,
)
from src.orchestrator.policy import resolve_state_context


class LangGraphStageAgentService:
    ENTRY_STAGES = {"CONTACT_REQUIRED", "CONSENT_REQUIRED", "ROLE_SELECTION"}
    CANDIDATE_STAGES = {"CV_PENDING"}

    def __init__(self, session):
        self.session = session
        self.candidates = CandidateProfilesRepository(session)
        self.consents = UserConsentsRepository(session)
        self.router = StageGraphRouter()
        register_foundation_stage_graphs()
        self._compiled_graphs = {}
        self._register_entry_stage_nodes()
        self._register_candidate_stage_nodes()

    def maybe_build_entry_reply(
        self,
        *,
        user,
        latest_user_message: str,
        latest_message_type: str = "text",
    ) -> str | None:
        if latest_message_type != "text" or not latest_user_message.strip():
            return None
        stage = self._resolve_entry_stage(user)
        if stage not in self.ENTRY_STAGES:
            return None
        compiled = self._get_compiled_graph(stage)
        context_stage = self.router.build_initial_state(
            stage=stage,
            user_id=str(getattr(user, "id", "")) or None,
            telegram_chat_id=str(getattr(user, "telegram_chat_id", "")) or None,
            role=self._resolve_role(user),
            latest_user_message=latest_user_message,
            latest_message_type=latest_message_type,
            allowed_actions=[],
            missing_requirements=[],
        )
        result = compiled.invoke(context_stage.as_dict())
        return result.get("reply_text")

    def maybe_build_stage_reply(
        self,
        *,
        user,
        latest_user_message: str,
        latest_message_type: str = "text",
    ) -> str | None:
        if latest_message_type != "text" or not latest_user_message.strip():
            return None
        stage = self._resolve_supported_stage(user)
        if stage is None:
            return None
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
        )
        result = compiled.invoke(state_input.as_dict())
        return result.get("reply_text")

    def _resolve_role(self, user) -> str | None:
        if getattr(user, "is_candidate", False):
            return "candidate"
        if getattr(user, "is_hiring_manager", False):
            return "hiring_manager"
        return None

    def _resolve_entry_stage(self, user) -> str | None:
        if not getattr(user, "phone_number", None):
            return "CONTACT_REQUIRED"
        if not self.consents.has_granted(user.id, "data_processing"):
            return "CONSENT_REQUIRED"
        if not getattr(user, "is_candidate", False) and not getattr(user, "is_hiring_manager", False):
            return "ROLE_SELECTION"
        return None

    def _resolve_candidate_stage(self, user) -> str | None:
        if not getattr(user, "is_candidate", False):
            return None
        candidate = self.candidates.get_active_by_user_id(user.id)
        if candidate is None:
            return None
        if candidate.state in self.CANDIDATE_STAGES:
            return candidate.state
        return None

    def _resolve_supported_stage(self, user) -> str | None:
        return self._resolve_entry_stage(user) or self._resolve_candidate_stage(user)

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
                    "detect_intent": detect_entry_intent_node,
                    "propose_action": build_entry_reply_node(self.session),
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
                    "load_context": load_candidate_cv_context_node,
                    "load_knowledge": load_candidate_cv_knowledge_node,
                    "detect_intent": detect_candidate_cv_intent_node,
                    "propose_action": build_candidate_cv_reply_node(self.session),
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
