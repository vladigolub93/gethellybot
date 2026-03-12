from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from src.candidate_profile.skills_inventory import (
    candidate_version_full_hard_skills,
    display_skill as inventory_display_skill,
    display_skill_list as inventory_display_skill_list,
    normalize_skill_token as inventory_normalize_skill_token,
    text_contains_skill,
)
from src.candidate_profile.states import CANDIDATE_READY_LIKE_STATES
from src.config.settings import get_settings
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.cv_challenge import CandidateCvChallengeAttemptsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.users import UsersRepository
from src.matching.policy import (
    MATCH_STATUS_ACCEPTED,
    MATCH_STATUS_CANDIDATE_DECISION_PENDING,
    MATCH_STATUS_INTERVIEW_QUEUED,
    MATCH_STATUS_INVITED,
    MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
    MATCH_STATUS_SHORTLISTED,
)


MIN_CV_CHALLENGE_SKILL_COUNT = 3
CV_CHALLENGE_TOTAL_LIVES = 3
CV_CHALLENGE_STAGE_CONFIG = (
    {
        "index": 1,
        "label": "Stage 1",
        "durationMs": 15000,
        "spawnIntervalMs": 1080,
        "speedMin": 72,
        "speedMax": 92,
        "correctChance": 0.72,
        "bonusChance": 0.08,
        "shieldChance": 0.05,
        "trapChance": 0.05,
    },
    {
        "index": 2,
        "label": "Stage 2",
        "durationMs": 15000,
        "spawnIntervalMs": 940,
        "speedMin": 88,
        "speedMax": 110,
        "correctChance": 0.6,
        "bonusChance": 0.1,
        "shieldChance": 0.05,
        "trapChance": 0.07,
    },
    {
        "index": 3,
        "label": "Stage 3",
        "durationMs": 15000,
        "spawnIntervalMs": 820,
        "speedMin": 104,
        "speedMax": 130,
        "correctChance": 0.5,
        "bonusChance": 0.12,
        "shieldChance": 0.04,
        "trapChance": 0.1,
    },
    {
        "index": 4,
        "label": "Stage 4",
        "durationMs": 14500,
        "spawnIntervalMs": 690,
        "speedMin": 126,
        "speedMax": 154,
        "correctChance": 0.42,
        "bonusChance": 0.14,
        "shieldChance": 0.04,
        "trapChance": 0.13,
    },
    {
        "index": 5,
        "label": "Stage 5",
        "durationMs": 14000,
        "spawnIntervalMs": 560,
        "speedMin": 148,
        "speedMax": 180,
        "correctChance": 0.34,
        "bonusChance": 0.16,
        "shieldChance": 0.03,
        "trapChance": 0.16,
    },
)
CV_CHALLENGE_DISTRACTOR_POOL = (
    "Java",
    "Spring",
    "Kotlin",
    "Swift",
    "Objective-C",
    "Angular",
    "Vue",
    "PHP",
    ".NET",
    "C#",
    "Ruby on Rails",
    "Laravel",
    "Elixir",
    "Phoenix",
    "Scala",
    "Spark",
    "TensorFlow",
    "PyTorch",
    "Rust",
    "Go",
    "Terraform",
    "Ansible",
    "Helm",
    "RabbitMQ",
    "Kafka",
    "Selenium",
    "Unity",
    "Unreal Engine",
    "Salesforce",
    "WordPress",
    "Joomla",
    "Perl",
    "Hadoop",
)
CV_CHALLENGE_SMART_DISTRACTORS = {
    "react": ("React Native", "Next.js", "Vue", "Angular"),
    "react native": ("React", "Flutter", "Swift", "Kotlin"),
    "next.js": ("Nuxt", "React", "Remix", "Angular"),
    "node": ("Node-RED", "Deno", "Bun", "NestJS"),
    "nodejs": ("Node-RED", "Deno", "Bun", "NestJS"),
    "node.js": ("Node-RED", "Deno", "Bun", "NestJS"),
    "typescript": ("JavaScript", "Flow", "ReasonML", "CoffeeScript"),
    "javascript": ("TypeScript", "Flow", "Elm", "ReasonML"),
    "python": ("Django", "Flask", "FastAPI", "Pandas"),
    "django": ("Flask", "FastAPI", "Ruby on Rails", "Laravel"),
    "fastapi": ("Flask", "Express", "Django", "NestJS"),
    "docker": ("Podman", "Kubernetes", "Helm", "Terraform"),
    "kubernetes": ("Docker Swarm", "Nomad", "Helm", "OpenShift"),
    "postgresql": ("MySQL", "SQLite", "MariaDB", "MongoDB"),
    "mysql": ("PostgreSQL", "MariaDB", "SQLite", "MongoDB"),
    "mongodb": ("PostgreSQL", "MySQL", "Redis", "Cassandra"),
    "redis": ("Memcached", "RabbitMQ", "MongoDB", "PostgreSQL"),
    "graphql": ("REST", "gRPC", "Apollo Client", "Relay"),
    "aws": ("GCP", "Azure", "CloudFormation", "Terraform"),
    "gcp": ("AWS", "Azure", "Terraform", "Cloud Run"),
    "terraform": ("CloudFormation", "Pulumi", "Ansible", "Helm"),
    "ansible": ("Terraform", "Puppet", "Chef", "Helm"),
}
CV_CHALLENGE_DAILY_GOAL_TEMPLATES = (
    {"type": "accuracy_min", "target": 75, "label": "Finish with 75%+ accuracy"},
    {"type": "lives_left_min", "target": 2, "label": "Finish with 2+ lives"},
    {"type": "max_streak_min", "target": 6, "label": "Reach a x3 combo"},
    {"type": "bonus_taps_min", "target": 2, "label": "Catch 2 bonus tokens"},
    {"type": "mistakes_max", "target": 2, "label": "Keep mistakes at 2 or less"},
    {"type": "shield_taps_min", "target": 1, "label": "Catch a shield token"},
)

CV_CHALLENGE_BLOCKING_MATCH_STATUSES = frozenset(
    {
        MATCH_STATUS_SHORTLISTED,
        MATCH_STATUS_CANDIDATE_DECISION_PENDING,
        MATCH_STATUS_MANAGER_INTERVIEW_REQUESTED,
        MATCH_STATUS_INTERVIEW_QUEUED,
        MATCH_STATUS_INVITED,
        MATCH_STATUS_ACCEPTED,
    }
)


def _normalize_skill_token(value: str) -> str:
    return inventory_normalize_skill_token(value)


def _display_skill(value: str) -> str:
    return inventory_display_skill(value)


def _clean_skill_list(values: list[str] | None) -> list[str]:
    return inventory_display_skill_list(values or [])


def _daily_seed(*parts: str) -> str:
    payload = "::".join(str(part or "") for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _build_daily_goals(*, seed: str, correct_skills: list[str]) -> list[dict[str, Any]]:
    rng = random.Random(int(seed, 16))
    score_target = max(12, min(24, len(correct_skills) * 4 + 2))
    candidates = list(CV_CHALLENGE_DAILY_GOAL_TEMPLATES) + [
        {
            "type": "score_min",
            "target": score_target,
            "label": f"Score at least {score_target} points",
        }
    ]
    selected = rng.sample(candidates, k=min(3, len(candidates)))
    return [
        {
            "type": item["type"],
            "target": item["target"],
            "label": item["label"],
        }
        for item in selected
    ]


def _build_daily_run(
    *,
    candidate_profile_id: str,
    candidate_profile_version_id: Optional[str],
    correct_skills: list[str],
) -> dict[str, Any]:
    date_label = datetime.now(timezone.utc).date().isoformat()
    seed = _daily_seed(
        date_label,
        candidate_profile_id,
        candidate_profile_version_id or "",
        "|".join(correct_skills),
    )
    return {
        "dateLabel": date_label,
        "seed": seed,
        "goals": _build_daily_goals(seed=seed, correct_skills=correct_skills),
    }


def _resolve_stage_config(snapshot_stage_config: Any) -> list[dict[str, Any]]:
    base_config = [dict(stage) for stage in CV_CHALLENGE_STAGE_CONFIG]
    if not isinstance(snapshot_stage_config, list) or len(snapshot_stage_config) < len(base_config):
        return base_config

    resolved: list[dict[str, Any]] = []
    for index, stage in enumerate(snapshot_stage_config):
        fallback = dict(base_config[index] if index < len(base_config) else base_config[-1])
        if isinstance(stage, dict):
            fallback.update(stage)
        fallback["index"] = index + 1
        fallback["label"] = str(fallback.get("label") or f"Stage {index + 1}")
        resolved.append(fallback)
    return resolved


def _distractor_is_blocked(
    skill: str,
    *,
    all_cv_skills: list[str],
    source_text: str | None,
) -> bool:
    normalized = _normalize_skill_token(skill)
    if not normalized:
        return True
    normalized_cv_skills = {_normalize_skill_token(item) for item in all_cv_skills}
    if normalized in normalized_cv_skills:
        return True
    return text_contains_skill(source_text, skill)


def _build_distractor_skills(
    *,
    all_cv_skills: list[str],
    source_text: str | None,
) -> list[str]:
    seen = set()
    result: list[str] = []

    def add(skill: str) -> None:
        normalized = _normalize_skill_token(skill)
        if normalized in seen or _distractor_is_blocked(
            skill,
            all_cv_skills=all_cv_skills,
            source_text=source_text,
        ):
            return
        seen.add(normalized)
        result.append(_display_skill(skill))

    for skill in all_cv_skills:
        normalized = _normalize_skill_token(skill)
        for related in CV_CHALLENGE_SMART_DISTRACTORS.get(normalized, ()):
            add(related)

    for skill in CV_CHALLENGE_DISTRACTOR_POOL:
        add(skill)

    return result[:18]


def _merge_distractor_skills(
    *,
    preferred_skills: list[str] | None,
    fallback_skills: list[str] | None,
    all_cv_skills: list[str],
    source_text: str | None,
) -> list[str]:
    seen = set()
    result: list[str] = []

    def add_many(values: list[str] | None) -> None:
        for raw_value in values or []:
            normalized = _normalize_skill_token(raw_value)
            if not normalized or normalized in seen:
                continue
            if _distractor_is_blocked(
                raw_value,
                all_cv_skills=all_cv_skills,
                source_text=source_text,
            ):
                continue
            seen.add(normalized)
            result.append(_display_skill(raw_value))
            if len(result) >= 18:
                return

    add_many(preferred_skills)
    if len(result) < 18:
        add_many(fallback_skills)
    return result[:18]


@dataclass(frozen=True)
class CandidateCvChallengeEligibility:
    eligible: bool
    reason_code: str
    title: str
    body: str
    launch_url: Optional[str]
    candidate_profile_id: Optional[str]
    candidate_profile_version_id: Optional[str]
    active_match_count: int
    source_text: Optional[str]
    all_cv_skills: list[str]
    correct_skills: list[str]
    distractor_skills: list[str]


class CandidateCvChallengeService:
    def __init__(self, session):
        self.session = session
        self.settings = get_settings()
        self.users = UsersRepository(session)
        self.profiles = CandidateProfilesRepository(session)
        self.matches = MatchingRepository(session)
        self.attempts = CandidateCvChallengeAttemptsRepository(session)

    @property
    def launch_url(self) -> str:
        return f"{self.settings.app_base_url.rstrip('/')}/webapp/cv-challenge"

    def build_eligibility_for_user_id(self, user_id) -> CandidateCvChallengeEligibility:
        profile = self.profiles.get_active_by_user_id(user_id)
        if profile is None:
            return CandidateCvChallengeEligibility(
                eligible=False,
                reason_code="candidate_profile_missing",
                title="CV Challenge is locked",
                body="Create and finish your candidate profile in Helly first, then this challenge will unlock.",
                launch_url=None,
                candidate_profile_id=None,
                candidate_profile_version_id=None,
                active_match_count=0,
                source_text=None,
                all_cv_skills=[],
                correct_skills=[],
                distractor_skills=[],
            )

        if profile.state not in CANDIDATE_READY_LIKE_STATES:
            return CandidateCvChallengeEligibility(
                eligible=False,
                reason_code="candidate_not_ready",
                title="Finish your profile first",
                body="The challenge unlocks after your CV, summary, questions and verification are complete.",
                launch_url=None,
                candidate_profile_id=str(profile.id),
                candidate_profile_version_id=str(profile.current_version_id) if profile.current_version_id else None,
                active_match_count=0,
                source_text=None,
                all_cv_skills=[],
                correct_skills=[],
                distractor_skills=[],
            )

        active_matches = self.matches.list_active_for_candidate(profile.id)
        blocking_matches = [
            match
            for match in active_matches
            if getattr(match, "status", None) in CV_CHALLENGE_BLOCKING_MATCH_STATUSES
        ]
        if blocking_matches:
            return CandidateCvChallengeEligibility(
                eligible=False,
                reason_code="candidate_has_active_matches",
                title="You already have live opportunities",
                body="The challenge is meant for the waiting period. Right now Helly already has active roles or interview steps for you.",
                launch_url=None,
                candidate_profile_id=str(profile.id),
                candidate_profile_version_id=str(profile.current_version_id) if profile.current_version_id else None,
                active_match_count=len(blocking_matches),
                source_text=None,
                all_cv_skills=[],
                correct_skills=[],
                distractor_skills=[],
            )

        version = self.profiles.get_current_version(profile)
        source_text = getattr(version, "extracted_text", None) or getattr(version, "transcript_text", None) or ""
        all_cv_skills = _clean_skill_list(candidate_version_full_hard_skills(version))
        if len(all_cv_skills) < MIN_CV_CHALLENGE_SKILL_COUNT:
            return CandidateCvChallengeEligibility(
                eligible=False,
                reason_code="skills_not_enough",
                title="Need a bit more CV detail",
                body="Helly could not extract enough clear technologies from your CV yet to build a fair challenge.",
                launch_url=None,
                candidate_profile_id=str(profile.id),
                candidate_profile_version_id=str(version.id) if version is not None else None,
                active_match_count=0,
                source_text=source_text,
                all_cv_skills=all_cv_skills,
                correct_skills=all_cv_skills,
                distractor_skills=[],
            )

        distractor_skills = _build_distractor_skills(
            all_cv_skills=all_cv_skills,
            source_text=source_text,
        )
        return CandidateCvChallengeEligibility(
            eligible=True,
            reason_code="eligible",
            title="Helly CV Challenge",
            body=(
                "While Helly is looking for strong matches, try a short challenge. "
                "Tap only the technologies that really appear in your CV and ignore the rest."
            ),
            launch_url=self.launch_url,
            candidate_profile_id=str(profile.id),
            candidate_profile_version_id=str(version.id) if version is not None else None,
            active_match_count=0,
            source_text=source_text,
            all_cv_skills=all_cv_skills,
            correct_skills=all_cv_skills,
            distractor_skills=distractor_skills,
        )

    def build_dashboard_card(self, user_id) -> Dict[str, Any]:
        eligibility = self.build_eligibility_for_user_id(user_id)
        return {
            "eligible": eligibility.eligible,
            "title": eligibility.title,
            "body": eligibility.body,
            "launchUrl": eligibility.launch_url,
            "correctSkillCount": len(eligibility.correct_skills),
            "activeMatchCount": eligibility.active_match_count,
            "reasonCode": eligibility.reason_code,
        }

    def _serialize_attempt(self, attempt, *, include_progress: bool) -> Dict[str, Any]:
        payload = {
            "id": str(attempt.id),
            "status": attempt.status,
            "score": int(attempt.score or 0),
            "livesLeft": int(attempt.lives_left or 0),
            "stageReached": int(attempt.stage_reached or 1),
            "won": bool(attempt.won),
            "startedAt": attempt.started_at.isoformat() if attempt.started_at else None,
            "finishedAt": attempt.finished_at.isoformat() if attempt.finished_at else None,
        }
        if include_progress:
            payload["progress"] = dict(attempt.result_json or {})
            payload["resumable"] = bool(attempt.result_json)
        else:
            payload["result"] = dict(attempt.result_json or {})
        return payload

    def build_invitation_payload(self, user_id) -> Optional[Dict[str, Any]]:
        eligibility = self.build_eligibility_for_user_id(user_id)
        if not eligibility.eligible or not eligibility.candidate_profile_id or not eligibility.launch_url:
            return None
        return {
            "entityType": "candidate_profile",
            "entityId": eligibility.candidate_profile_id,
            "text": (
                "While we are matching you with open roles, want to try a quick challenge?\n\n"
                "Helly CV Challenge tests how well you know your own CV.\n\n"
                "Tap the skills that appear in your CV and avoid the ones that do not."
            ),
            "launchUrl": eligibility.launch_url,
        }

    def bootstrap_for_candidate(self, user_id) -> Dict[str, Any]:
        eligibility = self.build_eligibility_for_user_id(user_id)
        if not eligibility.eligible:
            return {
                "eligible": False,
                "title": eligibility.title,
                "body": eligibility.body,
                "reasonCode": eligibility.reason_code,
            }

        profile_id = UUID(eligibility.candidate_profile_id)
        active_attempt = self.attempts.get_latest_active_for_candidate_profile(profile_id)
        last_completed = self.attempts.get_latest_completed_for_candidate_profile(profile_id)
        best_completed = self.attempts.get_best_completed_for_candidate_profile(profile_id)
        active_snapshot = dict(active_attempt.skills_snapshot_json or {}) if active_attempt is not None else {}

        challenge_all_cv_skills = _clean_skill_list(
            active_snapshot.get("allCvSkills") or eligibility.all_cv_skills
        )
        challenge_correct_skills = _clean_skill_list(
            active_snapshot.get("correctSkills") or eligibility.correct_skills
        )
        challenge_distractor_skills = _merge_distractor_skills(
            preferred_skills=active_snapshot.get("distractorSkills"),
            fallback_skills=eligibility.distractor_skills,
            all_cv_skills=challenge_all_cv_skills,
            source_text=eligibility.source_text,
        )
        challenge_stage_config = _resolve_stage_config(active_snapshot.get("stageConfig"))
        challenge_total_lives = int(active_snapshot.get("totalLives") or CV_CHALLENGE_TOTAL_LIVES)
        challenge_daily_run = dict(
            active_snapshot.get("dailyRun")
            or _build_daily_run(
                candidate_profile_id=eligibility.candidate_profile_id,
                candidate_profile_version_id=eligibility.candidate_profile_version_id,
                correct_skills=challenge_correct_skills,
            )
        )

        if active_attempt is None:
            active_attempt = self.attempts.create(
                candidate_profile_id=profile_id,
                candidate_profile_version_id=UUID(eligibility.candidate_profile_version_id)
                if eligibility.candidate_profile_version_id
                else None,
                skills_snapshot_json={
                    "allCvSkills": challenge_all_cv_skills,
                    "correctSkills": challenge_correct_skills,
                    "distractorSkills": challenge_distractor_skills,
                    "stageConfig": challenge_stage_config,
                    "totalLives": challenge_total_lives,
                    "dailyRun": challenge_daily_run,
                },
            )

        return {
            "eligible": True,
            "attempt": self._serialize_attempt(active_attempt, include_progress=True),
            "lastResult": (
                self._serialize_attempt(last_completed, include_progress=False)
                if last_completed is not None
                else None
            ),
            "bestResult": (
                self._serialize_attempt(best_completed, include_progress=False)
                if best_completed is not None
                else None
            ),
            "challenge": {
                "title": "Helly CV Challenge",
                "subtitle": "Tap only the skills that appear in your CV.",
                "totalLives": challenge_total_lives,
                "allCvSkills": challenge_all_cv_skills,
                "correctSkills": challenge_correct_skills,
                "distractorSkills": challenge_distractor_skills,
                "stages": challenge_stage_config,
                "dailyRun": challenge_daily_run,
            },
        }

    def save_attempt_progress(
        self,
        *,
        user_id,
        attempt_id: str,
        score: int,
        lives_left: int,
        stage_reached: int,
        progress_json: Optional[dict] = None,
    ) -> Dict[str, Any]:
        profile = self.profiles.get_active_by_user_id(user_id)
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found.")

        attempt = self.attempts.get_by_id(UUID(attempt_id))
        if attempt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge attempt not found.")
        if str(attempt.candidate_profile_id) != str(profile.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        if attempt.finished_at is not None:
            return {
                "attempt": self._serialize_attempt(attempt, include_progress=False),
            }

        updated = self.attempts.save_progress(
            attempt,
            score=score,
            lives_left=lives_left,
            stage_reached=stage_reached,
            progress_json=progress_json or {},
        )
        return {
            "attempt": self._serialize_attempt(updated, include_progress=True),
        }

    def finish_attempt(
        self,
        *,
        user_id,
        attempt_id: str,
        score: int,
        lives_left: int,
        stage_reached: int,
        won: bool,
        result_json: Optional[dict] = None,
    ) -> Dict[str, Any]:
        eligibility = self.build_eligibility_for_user_id(user_id)
        if not eligibility.candidate_profile_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found.")

        attempt = self.attempts.get_by_id(UUID(attempt_id))
        if attempt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge attempt not found.")
        if str(attempt.candidate_profile_id) != eligibility.candidate_profile_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        if attempt.finished_at is not None:
            return {
                "attempt": self._serialize_attempt(attempt, include_progress=False)
            }

        finished = self.attempts.mark_finished(
            attempt,
            score=score,
            lives_left=lives_left,
            stage_reached=stage_reached,
            won=won,
            result_json=result_json or {},
        )
        return {
            "attempt": self._serialize_attempt(finished, include_progress=False)
        }
