#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class SmokeSection:
    key: str
    title: str
    commands: tuple[list[str], ...]


def _python_bin() -> str:
    return str(ROOT / ".venv" / "bin" / "python")


def _pytest_bin() -> str:
    return str(ROOT / ".venv" / "bin" / "pytest")


SECTIONS: tuple[SmokeSection, ...] = (
    SmokeSection(
        key="frontend",
        title="Frontend Assets",
        commands=(
            ["node", "--check", "src/webapp/static/app.js"],
            ["node", "--check", "src/webapp/static/cv-challenge.js"],
        ),
    ),
    SmokeSection(
        key="graph",
        title="Graph Stage Flow",
        commands=(
            [
                _pytest_bin(),
                "-q",
                "tests/test_graph_stage_flows.py::test_candidate_graph_flow_progresses_across_stage_sequence",
                "tests/test_graph_stage_flows.py::test_manager_graph_flow_progresses_across_stage_sequence",
            ],
        ),
    ),
    SmokeSection(
        key="telegram",
        title="Telegram Routing Flow",
        commands=(
            [
                _pytest_bin(),
                "-q",
                "tests/test_telegram_graph_owned_flows.py::test_graph_owned_candidate_text_flow_routes_entry_cv_and_questions",
                "tests/test_telegram_graph_owned_flows.py::test_graph_owned_manager_text_flow_routes_entry_intake_and_clarifications",
                "tests/test_telegram_graph_owned_flows.py::test_graph_owned_interaction_flow_routes_accept_answer_and_manager_approve",
            ],
        ),
    ),
    SmokeSection(
        key="matching",
        title="Matching Flow",
        commands=(
            [
                _pytest_bin(),
                "-q",
                "tests/test_matching_processing.py::test_matching_processing_dispatches_manager_pre_interview_batch_for_vacancy_open",
                "tests/test_matching_processing.py::test_matching_processing_dispatches_candidate_vacancy_batch_for_candidate_ready",
                "tests/test_matching_review_service.py::test_dispatch_manager_batch_for_vacancy_prefers_strong_fit_candidates_first",
                "tests/test_matching_review_service.py::test_dispatch_manager_batch_for_vacancy_moves_to_medium_fit_when_no_strong_left",
                "tests/test_matching_review_service.py::test_execute_candidate_pre_interview_action_applies_and_notifies_manager",
                "tests/test_matching_review_service.py::test_execute_manager_pre_interview_action_shares_contacts_immediately_when_candidate_already_applied",
                "tests/test_matching_review_service.py::test_execute_candidate_pre_interview_action_shares_contacts_immediately_when_manager_already_approved",
            ],
        ),
    ),
    SmokeSection(
        key="webapp",
        title="WebApp Flow",
        commands=(
            [
                _pytest_bin(),
                "-q",
                "tests/test_webapp_service.py::test_list_candidate_opportunities_includes_challenge_card_and_serialized_matches",
                "tests/test_webapp_service.py::test_candidate_opportunity_detail_includes_why_this_role",
                "tests/test_webapp_service.py::test_manager_webapp_payloads_follow_direct_contact_flow",
                "tests/test_webapp_service.py::test_manager_match_detail_includes_real_rationale_and_concerns",
                "tests/test_webapp_router.py",
            ],
        ),
    ),
    SmokeSection(
        key="game",
        title="CV Challenge Flow",
        commands=(
            [
                _pytest_bin(),
                "-q",
                "tests/test_cv_challenge_service.py::test_cv_challenge_service_builds_bootstrap_for_eligible_candidate",
                "tests/test_cv_challenge_service.py::test_cv_challenge_service_uses_full_cv_skills_not_only_summary_skills",
                "tests/test_cv_challenge_service.py::test_cv_challenge_service_never_uses_cv_skill_as_distractor",
                "tests/test_cv_challenge_service.py::test_cv_challenge_service_returns_best_completed_result_not_only_latest",
            ],
        ),
    ),
)


def _run_command(command: list[str]) -> None:
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, cwd=ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _selected_sections(selected: list[str] | None) -> list[SmokeSection]:
    if not selected:
        return list(SECTIONS)

    selected_set = set(selected)
    chosen = [section for section in SECTIONS if section.key in selected_set]
    missing = sorted(selected_set - {section.key for section in SECTIONS})
    if missing:
        raise SystemExit(f"Unknown section(s): {', '.join(missing)}")
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a high-signal smoke check for the main Helly product flow."
    )
    parser.add_argument(
        "--section",
        action="append",
        choices=[section.key for section in SECTIONS],
        help="Run only the selected smoke section. Can be passed multiple times.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available smoke sections and exit.",
    )
    args = parser.parse_args()

    if args.list:
        for section in SECTIONS:
            print(f"{section.key}: {section.title}")
        return 0

    print("Helly product smoke run")
    print(f"Workspace: {ROOT}")
    print(f"Python: {_python_bin()}")
    print("")

    for section in _selected_sections(args.section):
        print(f"== {section.title} ==")
        for command in section.commands:
            _run_command(command)
        print("")

    print("Smoke run passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
