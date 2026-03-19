#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import text

from src.candidate_profile.question_parser import parse_candidate_questions
from src.candidate_profile.question_prompts import follow_up_prompt as candidate_follow_up_prompt
from src.candidate_profile.question_prompts import question_prompt as candidate_question_prompt
from src.candidate_profile.questions import (
    enrich_candidate_question_payload_for_current_question,
    filter_candidate_question_payload,
)
from src.db.session import get_engine
from src.vacancy.question_parser import parse_vacancy_clarifications
from src.vacancy.question_prompts import follow_up_prompt as vacancy_follow_up_prompt
from src.vacancy.question_prompts import question_prompt as vacancy_question_prompt
from src.vacancy.questions import (
    enrich_vacancy_clarification_payload_for_current_question,
    filter_vacancy_clarification_payload,
)


@dataclass(frozen=True)
class ReplayFinding:
    created_at: str
    role: str
    question_key: str
    classification: str
    telegram_user_id: int | None
    display_name: str | None
    prompt_text: str
    answer_text: str
    baseline_payload: dict[str, Any]
    enriched_payload: dict[str, Any]


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _contains_prompt_fragment(prompt_text: str, fragment: str) -> bool:
    prompt = _normalize_text(prompt_text)
    needle = _normalize_text(fragment)
    return bool(prompt and needle and needle in prompt)


@lru_cache(maxsize=1)
def _prompt_markers() -> list[tuple[int, str, str, str]]:
    markers: list[tuple[str, str, str]] = []

    def _add(role: str, question_key: str, fragment: str) -> None:
        normalized = _normalize_text(fragment)
        if normalized:
            markers.append((role, question_key, normalized))

    for question_key in ("salary", "work_format", "english_level", "preferred_domains", "assessment_preferences"):
        _add("candidate", question_key, candidate_question_prompt(question_key, work_formats=["remote", "hybrid", "office"]))
        _add("candidate", question_key, candidate_follow_up_prompt(question_key, work_formats=["remote", "hybrid", "office"]))
    _add("candidate", "location", candidate_question_prompt("location", work_formats=["remote"]))
    _add("candidate", "location", candidate_question_prompt("location", work_formats=["hybrid"]))
    _add("candidate", "location", candidate_follow_up_prompt("location", work_formats=["remote"]))
    _add("candidate", "location", candidate_follow_up_prompt("location", work_formats=["hybrid"]))

    for question_key in (
        "budget",
        "work_format",
        "office_city",
        "english_level",
        "assessment",
        "hiring_stages",
        "team_size",
        "project_description",
        "primary_tech_stack",
    ):
        _add("manager", question_key, vacancy_question_prompt(question_key, work_format="remote", has_take_home_task=True))
        _add("manager", question_key, vacancy_follow_up_prompt(question_key, work_format="remote", has_take_home_task=True))
    _add("manager", "countries", vacancy_question_prompt("countries", work_format="remote", has_take_home_task=True))
    _add("manager", "countries", vacancy_question_prompt("countries", work_format="hybrid", has_take_home_task=True))
    _add("manager", "countries", vacancy_follow_up_prompt("countries", work_format="remote", has_take_home_task=True))
    _add("manager", "countries", vacancy_follow_up_prompt("countries", work_format="hybrid", has_take_home_task=True))
    _add("manager", "take_home_paid", vacancy_question_prompt("take_home_paid", work_format="remote", has_take_home_task=True))
    _add("manager", "take_home_paid", vacancy_follow_up_prompt("take_home_paid", work_format="remote", has_take_home_task=True))

    for role, question_key, fragment in (
        ("candidate", "work_format", "i still need your preferred work format"),
        ("candidate", "english_level", "i still need your english level"),
        ("candidate", "english_level", "english level for matching"),
        ("candidate", "preferred_domains", "name the domains you prefer"),
        ("candidate", "preferred_domains", "say any if you have no preference"),
        ("candidate", "assessment_preferences", "i still need your assessment preferences"),
        ("candidate", "assessment_preferences", "show roles with take-home tasks and with live coding"),
        ("candidate", "assessment_preferences", "should i show you roles with live coding or not"),
        ("manager", "budget", "please answer the current vacancy question"),
        ("manager", "budget", "what budget range are you hiring with"),
        ("manager", "office_city", "which office or hybrid city"),
        ("manager", "english_level", "required english level"),
        ("manager", "assessment", "does this process include a take-home task, live coding, both, or neither"),
        ("manager", "take_home_paid", "is the take-home task paid or unpaid"),
        ("manager", "team_size", "what is the team size"),
        ("manager", "project_description", "describe the project"),
        ("manager", "primary_tech_stack", "what is the primary tech stack"),
    ):
        _add(role, question_key, fragment)

    deduped = {
        (role, question_key, fragment)
        for role, question_key, fragment in markers
    }
    return sorted(
        ((len(fragment), role, question_key, fragment) for role, question_key, fragment in deduped),
        reverse=True,
    )


def infer_prompt_context(prompt_text: str | None) -> tuple[str, str] | None:
    normalized = _normalize_text(prompt_text)
    if not normalized:
        return None
    for _, role, question_key, fragment in _prompt_markers():
        if fragment in normalized:
            return role, question_key
    return None


def classify_payload_delta(
    *,
    baseline_payload: dict[str, Any],
    enriched_payload: dict[str, Any],
) -> str:
    if not baseline_payload and enriched_payload:
        return "recovered"
    if baseline_payload and enriched_payload != baseline_payload:
        return "improved"
    if baseline_payload:
        return "baseline"
    return "unparsed"


def evaluate_prompt_answer_pair(prompt_text: str, answer_text: str) -> ReplayFinding | None:
    context = infer_prompt_context(prompt_text)
    if context is None:
        return None

    role, question_key = context
    if role == "candidate":
        baseline = filter_candidate_question_payload(parse_candidate_questions(answer_text), question_key)
        enriched = enrich_candidate_question_payload_for_current_question(
            parsed=parse_candidate_questions(answer_text),
            text=answer_text,
            current_question_key=question_key,
        )
    else:
        baseline = filter_vacancy_clarification_payload(parse_vacancy_clarifications(answer_text), question_key)
        enriched = enrich_vacancy_clarification_payload_for_current_question(
            parsed=parse_vacancy_clarifications(answer_text),
            text=answer_text,
            current_question_key=question_key,
        )

    return ReplayFinding(
        created_at="",
        role=role,
        question_key=question_key,
        classification=classify_payload_delta(
            baseline_payload=baseline,
            enriched_payload=enriched,
        ),
        telegram_user_id=None,
        display_name=None,
        prompt_text=prompt_text,
        answer_text=answer_text,
        baseline_payload=baseline,
        enriched_payload=enriched,
    )


def _load_recent_text_messages(
    *,
    telegram_user_id: int | None,
    telegram_chat_id: int | None,
    hours: int,
) -> list[dict[str, Any]]:
    filters = ["rm.content_type = 'text'", "rm.created_at >= now() - (:hours * interval '1 hour')"]
    params: dict[str, Any] = {"hours": hours}
    if telegram_user_id is not None:
        filters.append("u.telegram_user_id = :telegram_user_id")
        params["telegram_user_id"] = telegram_user_id
    if telegram_chat_id is not None:
        filters.append("u.telegram_chat_id = :telegram_chat_id")
        params["telegram_chat_id"] = telegram_chat_id

    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                f"""
                select
                    rm.id,
                    rm.user_id,
                    u.telegram_user_id,
                    u.telegram_chat_id,
                    u.display_name,
                    rm.created_at,
                    rm.direction,
                    rm.text_content
                from raw_messages rm
                join users u on u.id = rm.user_id
                where {' and '.join(filters)}
                order by rm.user_id asc, rm.created_at asc
                """
            ),
            params,
        ).mappings().all()
    return [dict(row) for row in rows]


def analyze_recent_question_answers(
    *,
    telegram_user_id: int | None,
    telegram_chat_id: int | None,
    hours: int,
    include_baseline: bool = False,
    role: str | None = None,
    question_key: str | None = None,
    classification: str | None = None,
) -> list[ReplayFinding]:
    rows = _load_recent_text_messages(
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        hours=hours,
    )

    findings: list[ReplayFinding] = []
    latest_outbound_by_user: dict[str, dict[str, Any]] = {}
    for row in rows:
        user_id = str(row["user_id"])
        direction = row["direction"]
        text_value = row.get("text_content") or ""
        if direction == "outbound":
            latest_outbound_by_user[user_id] = row
            continue
        if direction != "inbound":
            continue
        prompt_row = latest_outbound_by_user.get(user_id)
        if prompt_row is None or not prompt_row.get("text_content"):
            continue

        finding = evaluate_prompt_answer_pair(prompt_row["text_content"], text_value)
        if finding is None:
            continue
        if not include_baseline and finding.classification == "baseline":
            continue
        if role is not None and finding.role != role:
            continue
        if question_key is not None and finding.question_key != question_key:
            continue
        if classification is not None and finding.classification != classification:
            continue

        findings.append(
            ReplayFinding(
                created_at=str(row["created_at"]),
                role=finding.role,
                question_key=finding.question_key,
                classification=finding.classification,
                telegram_user_id=row.get("telegram_user_id"),
                display_name=row.get("display_name"),
                prompt_text=prompt_row["text_content"],
                answer_text=text_value,
                baseline_payload=finding.baseline_payload,
                enriched_payload=finding.enriched_payload,
            )
        )
    return findings


def _print_text(findings: list[ReplayFinding], *, top: int) -> None:
    if not findings:
        print("status: no_findings")
        return

    counts = Counter((item.role, item.question_key, item.classification) for item in findings)
    print("status: found")
    print(f"findings: {len(findings)}")
    print("summary:")
    for (role, question_key, classification), count in sorted(counts.items()):
        print(f"- {role}/{question_key}/{classification}: {count}")

    for idx, item in enumerate(findings[:top], start=1):
        print(f"{idx}. [{item.role}/{item.question_key}/{item.classification}] {item.created_at}")
        print(f"   user: {item.telegram_user_id} {item.display_name or ''}".rstrip())
        print(f"   prompt: {item.prompt_text}")
        print(f"   answer: {item.answer_text}")
        print(f"   baseline: {json.dumps(item.baseline_payload, ensure_ascii=False, default=str)}")
        print(f"   enriched: {json.dumps(item.enriched_payload, ensure_ascii=False, default=str)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay recent question-answer pairs from Telegram raw_messages and show where current-question enrichment recovers or improves parsing."
    )
    parser.add_argument("--telegram-user-id", type=int, default=None)
    parser.add_argument("--telegram-chat-id", type=int, default=None)
    parser.add_argument("--hours", type=int, default=72)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--include-baseline", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--role", choices=("candidate", "manager"), default=None)
    parser.add_argument("--question-key", default=None)
    parser.add_argument("--classification", choices=("baseline", "recovered", "improved", "unparsed"), default=None)
    args = parser.parse_args()

    findings = analyze_recent_question_answers(
        telegram_user_id=args.telegram_user_id,
        telegram_chat_id=args.telegram_chat_id,
        hours=args.hours,
        include_baseline=args.include_baseline,
        role=args.role,
        question_key=args.question_key,
        classification=args.classification,
    )

    if args.format == "json":
        print(json.dumps([asdict(item) for item in findings[: args.top]], ensure_ascii=False, indent=2, default=str))
        return
    _print_text(findings, top=args.top)


if __name__ == "__main__":
    main()
