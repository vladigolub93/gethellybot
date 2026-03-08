from __future__ import annotations

from pathlib import Path

from src.graph.service import LangGraphStageAgentService
from src.llm.assets import load_system_prompt
from src.orchestrator.policy import STATE_POLICY_DEFINITIONS


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_ROOT = REPO_ROOT / "prompts"


def test_all_graph_owned_stages_have_state_assistance_prompt_assets() -> None:
    graph_stages = (
        LangGraphStageAgentService.ENTRY_STAGES
        | LangGraphStageAgentService.SHARED_STAGES
        | LangGraphStageAgentService.CANDIDATE_STAGES
        | LangGraphStageAgentService.MANAGER_STAGES
    )

    missing = []
    for stage in sorted(graph_stages):
        definition = STATE_POLICY_DEFINITIONS.get(stage)
        if definition is None or not definition.assistance_prompt_slug:
            missing.append(stage)
            continue

        system_prompt_path = (
            PROMPTS_ROOT
            / "orchestrator"
            / "state_assistance"
            / definition.assistance_prompt_slug
            / "SYSTEM.md"
        )
        if not system_prompt_path.exists():
            missing.append(f"{stage}:{definition.assistance_prompt_slug}")

    assert missing == []


def test_core_prompt_families_exist() -> None:
    required_prompt_paths = [
        ("orchestrator", "bot_controller"),
        ("candidate", "cv_extract"),
        ("candidate", "cv_pending_decision"),
        ("candidate", "summary_review_decision"),
        ("candidate", "questions_decision"),
        ("candidate", "summary_merge"),
        ("candidate", "mandatory_field_parse"),
        ("vacancy", "jd_extract"),
        ("vacancy", "intake_pending_decision"),
        ("vacancy", "summary_review_decision"),
        ("vacancy", "summary_merge"),
        ("vacancy", "clarification_parse"),
        ("vacancy", "inconsistency_detect"),
        ("deletion", "confirmation_decision"),
        ("interview", "invitation_decision"),
        ("interview", "question_plan"),
        ("interview", "in_progress_decision"),
        ("interview", "followup_decision"),
        ("interview", "answer_parse"),
        ("interview", "session_conductor"),
        ("matching", "candidate_rerank"),
        ("evaluation", "candidate_evaluate"),
        ("messaging", "recovery"),
        ("messaging", "small_talk"),
        ("messaging", "role_selection"),
        ("messaging", "deletion_confirmation"),
        ("messaging", "interview_invitation_copy"),
        ("messaging", "response_copywriter"),
    ]

    missing = [
        "/".join(parts)
        for parts in required_prompt_paths
        if not (PROMPTS_ROOT.joinpath(*parts, "SYSTEM.md")).exists()
    ]

    assert missing == []


def test_shared_telegram_style_is_appended_to_system_prompts() -> None:
    prompt = load_system_prompt("orchestrator", "state_assistance", "contact_required")

    assert "Shared Telegram Delivery Rules:" in prompt
    assert "You are communicating inside Telegram" in prompt
    assert "friendly AI recruiter" in prompt
