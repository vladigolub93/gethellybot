from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from src.candidate_profile.states import CANDIDATE_READY_LIKE_STATES
from src.config.settings import get_settings
from src.db.repositories.candidate_profiles import CandidateProfilesRepository
from src.db.repositories.cv_challenge import CandidateCvChallengeAttemptsRepository
from src.db.repositories.matching import MatchingRepository
from src.db.repositories.users import UsersRepository


MIN_CV_CHALLENGE_SKILL_COUNT = 3
CV_CHALLENGE_TOTAL_LIVES = 3
CV_CHALLENGE_STAGE_CONFIG = (
    {"index": 1, "label": "Stage 1", "durationMs": 18000, "spawnIntervalMs": 1300, "speedMin": 72, "speedMax": 92},
    {"index": 2, "label": "Stage 2", "durationMs": 18000, "spawnIntervalMs": 1000, "speedMin": 98, "speedMax": 124},
    {"index": 3, "label": "Stage 3", "durationMs": 18000, "spawnIntervalMs": 760, "speedMin": 130, "speedMax": 162},
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


def _normalize_skill_token(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _display_skill(value: str) -> str:
    normalized = _normalize_skill_token(value)
    display_map = {
        "aws": "AWS",
        "gcp": "GCP",
        "node": "Node.js",
        "nodejs": "Node.js",
        "node.js": "Node.js",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "react": "React",
        "vue": "Vue",
        "angular": "Angular",
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "mongodb": "MongoDB",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "graphql": "GraphQL",
        "redis": "Redis",
        "python": "Python",
        "django": "Django",
        "fastapi": "FastAPI",
        "flask": "Flask",
        "java": "Java",
        "spring": "Spring",
        "php": "PHP",
        "swift": "Swift",
        "kotlin": "Kotlin",
        "rust": "Rust",
        "go": "Go",
        ".net": ".NET",
        "c#": "C#",
    }
    if normalized in display_map:
        return display_map[normalized]
    if normalized.endswith(".js"):
        return normalized[:-3].title() + ".js"
    words = normalized.split()
    return " ".join(word.upper() if len(word) <= 3 else word.capitalize() for word in words)


def _clean_skill_list(values: list[str] | None) -> list[str]:
    seen = set()
    result: list[str] = []
    for raw_value in values or []:
        normalized = _normalize_skill_token(raw_value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(_display_skill(normalized))
    return result


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
                correct_skills=[],
                distractor_skills=[],
            )

        active_matches = self.matches.list_active_for_candidate(profile.id)
        if active_matches:
            return CandidateCvChallengeEligibility(
                eligible=False,
                reason_code="candidate_has_active_matches",
                title="You already have live opportunities",
                body="The challenge is meant for the waiting period. Right now Helly already has active roles or interview steps for you.",
                launch_url=None,
                candidate_profile_id=str(profile.id),
                candidate_profile_version_id=str(profile.current_version_id) if profile.current_version_id else None,
                active_match_count=len(active_matches),
                correct_skills=[],
                distractor_skills=[],
            )

        version = self.profiles.get_current_version(profile)
        summary = getattr(version, "summary_json", None) or {}
        correct_skills = _clean_skill_list(summary.get("skills") or [])
        if len(correct_skills) < MIN_CV_CHALLENGE_SKILL_COUNT:
            return CandidateCvChallengeEligibility(
                eligible=False,
                reason_code="skills_not_enough",
                title="Need a bit more CV detail",
                body="Helly could not extract enough clear technologies from your CV yet to build a fair challenge.",
                launch_url=None,
                candidate_profile_id=str(profile.id),
                candidate_profile_version_id=str(version.id) if version is not None else None,
                active_match_count=0,
                correct_skills=correct_skills,
                distractor_skills=[],
            )

        normalized_correct = {_normalize_skill_token(skill) for skill in correct_skills}
        distractor_skills = [
            skill
            for skill in CV_CHALLENGE_DISTRACTOR_POOL
            if _normalize_skill_token(skill) not in normalized_correct
        ]

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
            correct_skills=correct_skills,
            distractor_skills=distractor_skills[:18],
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

        if active_attempt is None:
            active_attempt = self.attempts.create(
                candidate_profile_id=profile_id,
                candidate_profile_version_id=UUID(eligibility.candidate_profile_version_id)
                if eligibility.candidate_profile_version_id
                else None,
                skills_snapshot_json={
                    "correctSkills": eligibility.correct_skills,
                    "distractorSkills": eligibility.distractor_skills,
                    "stageConfig": list(CV_CHALLENGE_STAGE_CONFIG),
                    "totalLives": CV_CHALLENGE_TOTAL_LIVES,
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
            "challenge": {
                "title": "Helly CV Challenge",
                "subtitle": "Tap only the skills that appear in your CV.",
                "totalLives": CV_CHALLENGE_TOTAL_LIVES,
                "correctSkills": eligibility.correct_skills,
                "distractorSkills": eligibility.distractor_skills,
                "stages": list(CV_CHALLENGE_STAGE_CONFIG),
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
