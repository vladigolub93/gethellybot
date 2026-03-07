from src.graph.bootstrap import register_foundation_stage_graphs
from src.graph.registry import registry
from src.graph.router import StageGraphRouter


def setup_module() -> None:
    register_foundation_stage_graphs()


def test_foundation_registers_expected_stage_graphs() -> None:
    for stage in (
        "CONTACT_REQUIRED",
        "CONSENT_REQUIRED",
        "ROLE_SELECTION",
        "CV_PENDING",
        "INTAKE_PENDING",
        "INTERVIEW_IN_PROGRESS",
        "DELETE_CONFIRMATION",
    ):
        definition = registry.get_definition(stage)
        assert definition is not None
        assert definition.entry_node_name == "load_context"


def test_stage_graph_router_builds_initial_state() -> None:
    router = StageGraphRouter()
    state = router.build_initial_state(
        stage="CV_PENDING",
        user_id="u1",
        telegram_chat_id="t1",
        role="candidate",
        latest_user_message="I do not have a CV",
        latest_message_type="text",
        allowed_actions=["send_cv_text", "send_cv_document", "send_cv_voice"],
        missing_requirements=["candidate_experience_source"],
    )

    assert state.active_stage == "CV_PENDING"
    assert state.role == "candidate"
    assert state.allowed_actions == ["send_cv_text", "send_cv_document", "send_cv_voice"]
    assert state.missing_requirements == ["candidate_experience_source"]
    assert state.latest_user_message == "I do not have a CV"
